"""Deterministic request-guard and readiness-failure regressions; no network writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python-playwright'))
sys.path.insert(0, str(ROOT / 'scripts'))
from framework.safety import diagnostic_path, request_policy
import run_qa_matrix as matrix


class SmokeContracts(unittest.TestCase):
    origin = 'https://shop.example'
    challenge = '/cdn-cgi/challenge-platform/h/g/jsd/oneshot/abc/0.123:proof'

    def test_challenge_is_blocked_and_classified(self):
        self.assertEqual(request_policy('POST', self.origin + self.challenge, self.origin), 'blocked-infrastructure')

    def test_challenge_lookalikes_cannot_hide_application_writes(self):
        urls = ['https://other.example' + self.challenge,
                self.origin + '.evil.example' + self.challenge,
                self.origin + '/api/cart/items?next=' + self.challenge,
                self.origin + '/api/orders', self.origin + self.challenge + '?override=true',
                self.origin + '/cdn-cgi/challenge-platform/application',
                self.origin + self.challenge.replace('/h/g/', '/h/x/'),
                'http://shop.example' + self.challenge]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(request_policy('POST', url, self.origin, True), 'blocked-write')
        self.assertEqual(request_policy('PATCH', self.origin + self.challenge, self.origin), 'blocked-write')

    def test_local_writes_need_matching_loopback_and_explicit_permission(self):
        base = 'http://127.0.0.1:8790'
        self.assertEqual(request_policy('POST', base + '/api/cart/items', base, True), 'local-write')
        for url, allow in [(base + '/api/cart/items', False), ('http://127.0.0.1:8791/api/cart/items', True),
                           ('http://localhost:8790/api/cart/items', True), ('https://shop.example/api/cart/items', True)]:
            self.assertEqual(request_policy('POST', url, base, allow), 'blocked-write')

    def test_diagnostic_paths_omit_query_and_challenge_proof(self):
        self.assertEqual(diagnostic_path(self.origin + '/api/cart?secret=example'), '/api/cart')
        self.assertEqual(diagnostic_path(self.origin + self.challenge), '/cdn-cgi/challenge-platform/<redacted>')

    def test_readiness_failure_is_retained_and_remaining_cases_not_run(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.sites-runtime') as directory:
            identity = {'sha256': 'test', 'files': {}}
            with patch.object(sys, 'argv', ['matrix', '--base-url', 'http://127.0.0.1:8790', '--smoke', '--report-dir', directory]), \
                    patch.object(matrix, 'fingerprint', return_value=identity), \
                    patch.object(matrix, 'verified_build', return_value={'build': identity}), \
                    patch.object(matrix, 'build_identity', return_value=identity), \
                    patch.object(matrix, 'urlopen', side_effect=OSError('deliberate probe failure')), \
                    patch.object(matrix.subprocess, 'check_output', return_value='test-head'), \
                    patch.object(matrix.subprocess, 'run') as runner:
                self.assertEqual(matrix.main(), 1)
                runner.assert_not_called()
            result = json.loads((Path(directory) / 'results.json').read_text())
            self.assertEqual([r['status'] for r in result['runs']], ['FAIL', 'NOT RUN', 'NOT RUN', 'NOT RUN'])
            self.assertEqual(result['runs'][0]['phase'], 'readiness')

    def test_public_smoke_requires_matching_deployment_record(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.sites-runtime') as directory:
            path = Path(directory) / 'deployment.json'
            path.write_text(json.dumps({'url': self.origin, 'sites_sha': 'a' * 40,
                                        'version_id': 'version-test', 'deployment_id': 'deployment-test'}))
            self.assertEqual(matrix.deployment_identity(path, self.origin)['sites_sha'], 'a' * 40)
            with self.assertRaises(ValueError):
                matrix.deployment_identity(path, 'https://other.example')

    def test_teardown_errors_retain_redacted_browser_artifacts(self):
        parent = ROOT / 'outputs' / 'p0-07-09-completion' / 'guard-probes'
        parent.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='probe-', dir=parent))
        probe = directory / 'test_probe.py'
        probe.write_text('''
import pytest

@pytest.fixture
def page(guest):
    return guest[1]

def prepare(page, base_url):
    page.route(base_url + '/', lambda route: route.fulfill(body='<html><body>Guard probe</body></html>', content_type='text/html'))
    page.goto(base_url + '/')

def test_deliberate_write_violation(page, base_url):
    prepare(page, base_url)
    page.evaluate("fetch('/api/cart/items', {method:'POST',body:'{}'}).catch(() => null)")

def test_deliberate_page_error(page, base_url):
    prepare(page, base_url)
    with page.expect_event('pageerror'):
        page.evaluate("setTimeout(() => {throw new Error('guest:' + 'f'.repeat(64))}, 0)")

def test_known_challenge_is_blocked_without_failure(page, base_url):
    prepare(page, base_url)
    page.evaluate("fetch('/cdn-cgi/challenge-platform/h/g/jsd/oneshot/abc', {method:'POST'}).catch(() => null)")
''', encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'python-playwright'))
        command = [sys.executable, '-m', 'pytest', '-p', 'conftest', '-c', str(ROOT / 'python-playwright/pytest.ini'),
                   '--confcutdir', str(directory), '--rootdir', str(directory), str(probe), '-q',
                   '--base-url', 'https://127.0.0.1:19876', '--browser', 'chromium',
                   '--artifacts-dir', str(directory / 'artifacts'), '--junitxml', str(directory / 'junit.xml')]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        # These two synthetic tests must fail teardown. No endpoint is allowed to receive a write.
        (directory / 'runner.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        self.assertEqual(result.returncode, 1, result.stdout[-4000:])
        junit = ET.parse(directory / 'junit.xml')
        self.assertEqual(len(junit.findall('.//error')), 2)
        evidence = list((directory / 'artifacts').glob('*/evidence.json'))
        self.assertEqual(len(evidence), 3)
        failed_records = 0
        classified_challenges = 0
        for path in evidence:
            record = json.loads(path.read_text())
            if not record['failed']:
                self.assertEqual(record['blocked_infrastructure'], 1)
                self.assertFalse(record['violations'])
                classified_challenges += 1
                continue
            failed_records += 1
            self.assertTrue(record['violations'] or record['page_errors'])
            self.assertGreater((path.parent / 'failure.png').stat().st_size, 0)
            self.assertNotIn('f' * 64, path.read_text())
            with zipfile.ZipFile(path.parent / 'trace.zip') as archive:
                self.assertIsNone(archive.testzip())
                self.assertFalse(any(('f' * 64).encode() in archive.read(name) for name in archive.namelist()))
        self.assertEqual((failed_records, classified_challenges), (2, 1))
        print('Retained intentional-failure diagnostics:', directory.relative_to(ROOT))


if __name__ == '__main__':
    unittest.main(verbosity=2)
