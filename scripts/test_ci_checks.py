"""CI runner failure, cleanup and artifact boundary contracts; no package installs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import ci_checks as ci


class CiContracts(unittest.TestCase):
    def setUp(self):
        (ci.ROOT / '.sites-runtime').mkdir(exist_ok=True)

    def test_artifact_allowlist_excludes_local_database_manifest_and_source_archive(self):
        with tempfile.TemporaryDirectory(dir=ci.ROOT / '.sites-runtime') as raw:
            report = Path(raw)
            (report / 'source').mkdir()
            (report / 'matrix').mkdir()
            (report / 'ci-summary.json').write_text(json.dumps({'status': 'FAIL'}))
            (report / 'source/candidate-manifest.json').write_text(json.dumps({'files': []}))
            (report / 'source/candidate-source.zip').write_bytes(b'not-for-upload')
            (report / 'manifest.json').write_text(json.dumps({'cookie': 'a' * 64}))
            (report / 'database.sqlite').write_bytes(b'not-for-upload')
            copied = ci.export_evidence(report)
            self.assertEqual({x['path'] for x in copied}, {'ci-summary.json', 'source/candidate-manifest.json'})
            self.assertFalse((report / 'publish/manifest.json').exists())
            self.assertFalse((report / 'publish/database.sqlite').exists())
            self.assertFalse((report / 'publish/source/candidate-source.zip').exists())

    def test_logs_and_trace_cookie_capabilities_are_sanitized(self):
        with tempfile.TemporaryDirectory(dir=ci.ROOT / '.sites-runtime') as raw:
            report = Path(raw)
            (report / 'logs').mkdir()
            (report / 'logs/failure.log').write_text('guest:' + 'a' * 64 + ' __Host-everyday-guest=' + 'b' * 64 + ' raw:' + 'c' * 64)
            folder = report / 'matrix/en-desktop/artifacts/failure'
            folder.mkdir(parents=True)
            with zipfile.ZipFile(folder / 'trace.zip', 'w') as archive:
                archive.writestr('trace.trace', json.dumps({'name': '__Host-everyday-guest', 'value': 'd' * 64}))
                archive.writestr('error.txt', 'raw:' + 'e' * 64)
            ci.export_evidence(report)
            published = report / 'publish'
            for letter in 'abc':
                self.assertNotIn(letter * 64, (published / 'logs/failure.log').read_text())
            with zipfile.ZipFile(published / 'matrix/en-desktop/artifacts/failure/trace.zip') as archive:
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    self.assertNotIn(b'd' * 64, archive.read(name))
                    self.assertNotIn(b'e' * 64, archive.read(name))

    def test_published_index_hash_matches_actual_summary(self):
        with tempfile.TemporaryDirectory(dir=ci.ROOT / '.sites-runtime') as raw:
            report = Path(raw)
            (report / 'ci-summary.json').write_text(json.dumps({'status': 'PASS', 'artifact_bundle': {'status': 'PASS'}}))
            ci.export_evidence(report)
            index = json.loads((report / 'publish/artifact-index.json').read_text())
            for entry in index['files']:
                self.assertEqual(entry['sha256'], ci.digest(report / 'publish' / entry['path']))

    def test_sanitized_comparison_retains_distinct_raw_and_published_digests(self):
        with tempfile.TemporaryDirectory(dir=ci.ROOT / '.sites-runtime') as raw:
            report = Path(raw); (report / 'comparison').mkdir()
            paired = report / 'comparison/comparison.json'; paired.write_text(json.dumps({'amount': '₹749'}, ensure_ascii=False), encoding='utf-8')
            original = ci.digest(paired)
            (report / 'comparison/comparison-summary.json').write_text(json.dumps({'comparison_file_sha256': original}))
            ci.export_evidence(report)
            wrapped = json.loads((report / 'publish/comparison/comparison-summary.json').read_text())
            self.assertEqual(wrapped['comparison_file_sha256'], original)
            self.assertEqual(wrapped['published_comparison_file_sha256'], ci.digest(report / 'publish/comparison/comparison.json'))
            self.assertNotEqual(wrapped['comparison_file_sha256'], wrapped['published_comparison_file_sha256'])

    def test_baseline_summary_does_not_claim_source_delta_is_behavior_execution(self):
        with tempfile.TemporaryDirectory(dir=ci.ROOT / '.sites-runtime') as raw:
            def fake_git(*args):
                if args[:2] == ('rev-parse', '--verify'): return 'a' * 40
                if args == ('rev-parse', 'HEAD'): return 'b' * 40
                if args[:2] == ('diff', '--name-only'): return 'app/shop.tsx'
                if args == ('status', '--porcelain'): return ''
                raise AssertionError(args)
            with patch.object(ci, 'git', side_effect=fake_git):
                record = ci.baseline_summary('a' * 40, Path(raw) / 'baseline.json')
            self.assertEqual(record['identity_summary_status'], 'PASS')
            self.assertNotEqual(record['behavioral_comparison']['status'], 'PASS')

    def test_baseline_rejects_untrusted_ref_or_shell_like_input(self):
        for value in ('main', 'abc', 'a' * 40 + ';echo unsafe', '../HEAD'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ci.resolve_baseline(value)

    def test_server_cleanup_terminates_owned_child_and_removes_only_owned_lock(self):
        with tempfile.TemporaryDirectory(dir=ci.ROOT / '.sites-runtime') as raw:
            # A real grandchild owns the listener; stopping only the root would leak it.
            with ci.socket.socket() as lease:
                lease.bind(('127.0.0.1', 0)); port = lease.getsockname()[1]
            child = "import socket,sys,time;s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen();time.sleep(30)"
            parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ',sys.argv[1]]);time.sleep(30)'
            process = ci.start_owned([sys.executable, '-c', parent, str(port)])
            try:
                ci.wait_server(process, port)
                ci.stop_tree(process, port=port)
                self.assertIsNotNone(process.poll())
                self.assertFalse(ci.listening(port))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_cleanup_rejects_foreign_namespace(self):
        with self.assertRaises(ValueError):
            ci.stop_tree(None, ci.ROOT / 'app')

    def test_cleanup_kills_listening_descendant_after_parent_exits(self):
        with ci.socket.socket() as lease:
            lease.bind(('127.0.0.1', 0)); port = lease.getsockname()[1]
        child = "import socket,sys,time;s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen();time.sleep(30)"
        parent = ('import subprocess,sys,socket,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ',sys.argv[1]])\n'
                  'for _ in range(300):\n'
                  ' try:\n'
                  '  connection=socket.create_connection(("127.0.0.1",int(sys.argv[1])),0.1);connection.close();break\n'
                  ' except OSError:time.sleep(0.01)\n')
        process = ci.start_owned([sys.executable, '-c', parent, str(port)])
        try:
            self.assertEqual(process.wait(timeout=10), 0)
            self.assertTrue(ci.listening(port), 'Synthetic descendant did not start')
            ci.stop_tree(process, port=port)
            self.assertFalse(ci.listening(port))
        finally:
            ci.stop_tree(process, port=port)

    def test_fixture_lock_owned_by_launcher_descendant_is_verified(self):
        base = ci.ROOT / '.sites-runtime/test-data'; base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as raw:
            namespace = Path(raw)
            with ci.socket.socket() as lease:
                lease.bind(('127.0.0.1', 0)); port = lease.getsockname()[1]
            child = ("import socket,sys,time,os,pathlib;pathlib.Path(sys.argv[2]).write_text(str(os.getpid()));"
                     "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen();time.sleep(30)")
            if os.name == 'nt':
                parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ',sys.argv[1],sys.argv[2]]);time.sleep(30)'
            else:
                # POSIX venv executables preserve their PID instead of using a redirector.
                parent = child
            process = ci.start_owned([sys.executable, '-c', parent, str(port), str(namespace / 'operation.lock')])
            try:
                ci.wait_server(process, port, namespace=namespace)
                self.assertTrue((namespace / 'operation.lock').is_file())
                ci.stop_tree(process, namespace, port)
                self.assertFalse((namespace / 'operation.lock').exists())
            finally:
                ci.stop_tree(process, port=port)

    def test_failed_step_retains_summary_and_skips_remaining_checks(self):
        report = ci.ROOT / 'outputs/p0-10' / ('runner-contract-' + str(os.getpid()))
        if report.exists():
            report = report.with_name(report.name + '-' + os.urandom(3).hex())
        fake_identity = {'sha256': 'test', 'files': {}}
        with patch.object(sys, 'argv', ['ci', '--baseline-sha', 'a' * 40, '--report-dir', str(report)]), \
                patch.object(ci, 'git', side_effect=lambda *a: 'a' * 40 if a[0] == 'rev-parse' else ''), \
                patch.object(ci, 'fingerprint', return_value=fake_identity), \
                patch.object(ci, 'runtime_inputs', return_value=fake_identity), \
                patch.object(ci, 'run_logged', return_value=7) as command:
            self.assertEqual(ci.main(), 1)
            self.assertEqual(command.call_count, 1)
        summary = json.loads((report / 'ci-summary.json').read_text())
        self.assertEqual(summary['status'], 'FAIL')
        self.assertEqual(summary['steps'][0]['status'], 'FAIL')
        self.assertTrue(all(s['status'] == 'NOT RUN' for s in summary['steps'][1:]))
        self.assertEqual(summary['cleanup']['status'], 'PASS')
        self.assertEqual(json.loads((report / 'publish/ci-summary.json').read_text())['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main(verbosity=2)
