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
from urllib.request import urlopen

from qa_provenance import verified_build, build_identity

ROOT = Path(__file__).resolve().parents[1]


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
    args = parser.parse_args()
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
               'browser_engine': args.browser, 'build_provenance': build, 'server_start': server, 'runs': []}
    for locale in ('en', 'fr'):
        for viewport in ('desktop', 'mobile'):
            folder = report / f'{locale}-{viewport}'
            folder.mkdir(parents=True, exist_ok=True)
            # Readiness is an actual D1 health check, not an assertion retry.
            # It also separates successive browser processes from local pool teardown.
            with urlopen(args.base_url.rstrip('/') + '/api/health', timeout=15) as response:
                if response.status != 200 or json.load(response) != {'status': 'ok'}:
                    raise ValueError('Target health probe failed before browser launch.')
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
            record = {'locale': locale, 'viewport': viewport, 'exit_code': result.returncode}
            if (folder / 'junit.xml').exists():
                suites = ET.parse(folder / 'junit.xml').getroot()
                record.update({key: sum(int(s.attrib.get(key, 0)) for s in suites.iter('testsuite'))
                               for key in ('tests', 'failures', 'errors', 'skipped')})
            summary['runs'].append(record)
            print(locale, viewport, record, flush=True)
    summary['source_unchanged_during_run'] = before == fingerprint()
    summary['build_unchanged_during_run'] = build['build'] == build_identity()
    summary['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (report / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return int(any(r['exit_code'] for r in summary['runs']) or not summary['source_unchanged_during_run'] or not summary['build_unchanged_during_run'])


if __name__ == '__main__':
    sys.exit(main())
