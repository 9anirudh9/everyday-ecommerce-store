"""Run the reusable pytest suite with SHA-bound locale/viewport evidence.

Run with the Python environment containing python-playwright/requirements.txt.
This command neither builds nor starts servers; use owned local test data for
writes. For a public read-only smoke, pass --smoke and omit the manifest.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from qa_provenance import verified_build, build_identity

ROOT = Path(__file__).resolve().parents[1]
HEALTH_USER_AGENT = 'Mozilla/5.0 (compatible; EverydayShopQA/1.0; read-only health probe)'


def deployment_identity(path, base_url):
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('url', '').rstrip('/') != base_url.rstrip('/'):
        raise ValueError('Deployment record URL must match the target exactly.')
    for field in ('sites_sha', 'version_id', 'deployment_id'):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError('Deployment record must identify ' + field)
    if len(record['sites_sha']) != 40 or any(c not in '0123456789abcdef' for c in record['sites_sha']):
        raise ValueError('Deployment record needs a full source SHA.')
    return {**record, 'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fingerprint():
    files = {}
    for directory in ('app', 'lib', 'db', 'drizzle', 'components', 'scripts', 'python-playwright'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and path.suffix in ('.py', '.ts', '.tsx', '.sql', '.mjs', '.css', '.ini', '.txt'):
                files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), 'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--browser', choices=('chromium', 'firefox', 'webkit'), default='chromium')
    parser.add_argument('--deployment-record', type=Path, help='Sanitized provider-verified URL/SHA/version/deployment JSON for public smoke')
    args = parser.parse_args()
    public = urlsplit(args.base_url).hostname not in ('127.0.0.1', 'localhost')
    if public and (not args.smoke or args.manifest):
        parser.error('Public targets support read-only --smoke without a manifest only.')
    if public and not args.deployment_record:
        parser.error('Public smoke requires --deployment-record for the target identity.')
    deployment = deployment_identity(args.deployment_record, args.base_url) if args.deployment_record else None
    report = args.report_dir.resolve()
    report.mkdir(parents=True, exist_ok=True)
    before = fingerprint()
    build = verified_build()
    server = None
    if args.manifest:
        server = json.loads((args.manifest.resolve().parent / 'server.json').read_text(encoding='utf-8'))
        if server['url'] != args.base_url or server['build_sha256'] != build['build']['sha256']:
            raise ValueError('The server was not started from the verified build.')
    summary = {'scope': 'pytest locale/viewport matrix', 'url': args.base_url,
               'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'dirty_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
               'started_utc': datetime.now(timezone.utc).isoformat(), 'source': before,
               'browser_engine': args.browser, 'build_provenance': build, 'server_start': server,
               'deployment': deployment, 'health_user_agent': HEALTH_USER_AGENT, 'runs': []}
    combinations = [(locale, viewport) for locale in ('en', 'fr') for viewport in ('desktop', 'mobile')]
    stopped = False
    try:
        for locale, viewport in combinations:
            if stopped:
                summary['runs'].append({'locale': locale, 'viewport': viewport, 'status': 'NOT RUN', 'exit_code': None})
                continue
            folder = report / f'{locale}-{viewport}'
            folder.mkdir(parents=True, exist_ok=True)
            # Readiness is an actual D1 health check, not an assertion retry.
            # It also separates successive browser processes from local pool teardown.
            try:
                probe = Request(args.base_url.rstrip('/') + '/api/health', headers={'User-Agent': HEALTH_USER_AGENT})
                with urlopen(probe, timeout=15) as response:
                    if response.status != 200 or json.load(response) != {'status': 'ok'}:
                        raise ValueError('Target health probe failed before browser launch.')
            except Exception as error:
                summary['runs'].append({'locale': locale, 'viewport': viewport, 'status': 'FAIL',
                                        'phase': 'readiness', 'exit_code': 1, 'tests': 0,
                                        'error_type': type(error).__name__, 'message': str(error)})
                stopped = True
                continue
            command = [sys.executable, '-m', 'pytest', '-c', 'pytest.ini',
                       *(['tests/smoke', '-m', 'smoke'] if args.smoke else ['tests/api', 'tests/e2e', 'tests/smoke']),
                       '-q', '--base-url', args.base_url, '--browser', args.browser,
                       '--locale', locale, '--viewport-mode', viewport,
                       '--artifacts-dir', str(folder / 'artifacts'), '--junitxml', str(folder / 'junit.xml'),
                       '--html', str(folder / 'report.html'), '--self-contained-html']
            if args.manifest:
                command += ['--test-data-manifest', str(args.manifest.resolve())]
            with (folder / 'runner.log').open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT / 'python-playwright', stdout=log, stderr=subprocess.STDOUT)
            record = {'locale': locale, 'viewport': viewport, 'exit_code': result.returncode,
                      'status': 'PASS' if result.returncode == 0 else 'FAIL'}
            if (folder / 'junit.xml').exists():
                suites = ET.parse(folder / 'junit.xml').getroot()
                record.update({key: sum(int(s.attrib.get(key, 0)) for s in suites.iter('testsuite'))
                               for key in ('tests', 'failures', 'errors', 'skipped')})
            summary['runs'].append(record)
            print(locale, viewport, record, flush=True)
    finally:
        summary['source_unchanged_during_run'] = before == fingerprint()
        summary['build_unchanged_during_run'] = build['build'] == build_identity()
        summary['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (report / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return int(any(r['exit_code'] for r in summary['runs']) or not summary['source_unchanged_during_run'] or not summary['build_unchanged_during_run'])


if __name__ == '__main__':
    sys.exit(main())
