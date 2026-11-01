"""Finite local CI checks, owned D1 lifecycle and a sanitized evidence allowlist.

No command installs dependencies, publishes a deployment, or accesses remote D1.
The authored GitHub workflow installs pinned dependencies before invoking this.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

from qa_provenance import build_identity, runtime_inputs
from run_qa_matrix import fingerprint

ROOT = Path(__file__).resolve().parents[1]
CORE_STEPS = ('agents', 'lint', 'typecheck', 'build', 'commerce-domain',
              'catalog-domain', 'data-contracts', 'smoke-contracts',
              'ci-contracts', 'release-contracts', 'fixture-prepare', 'local-matrix', 'baseline-compare', 'baseline-summary')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def redact_text(value):
    value = re.sub(r'(__Host-everyday-guest=)[a-f0-9]{64}', r'\1<redacted>', value)
    return re.sub(r'guest:[a-f0-9]{64}', 'guest:<redacted>', value)


def redact_log(value):
    # Error introspection can print a capability without its cookie name.
    # Digests stay available in structured provenance rather than opaque log text.
    return re.sub(r'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', '<redacted-hex64>', redact_text(value))


def private_capability(data):
    return bool(re.search(rb'guest:[a-f0-9]{64}|__Host-everyday-guest=[a-f0-9]{64}', data))


def process_options():
    if os.name == 'nt':
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    return {'start_new_session': True}


def start_owned(command, **options):
    flags = process_options()
    if os.name == 'nt':
        flags['creationflags'] |= 0x4  # CREATE_SUSPENDED: assign containment before child code executes.
    process = subprocess.Popen(command, **options, **flags)
    if os.name == 'nt':
        from windows_job import contain_and_resume
        process._qa_job = contain_and_resume(process)
    return process


def owned_pids(process):
    values = set(getattr(process, '_qa_owned_pids', set())) | {process.pid}
    handle = getattr(process, '_qa_job', None)
    if os.name == 'nt' and handle is not None:
        from windows_job import job_pids
        values |= job_pids(handle)
    process._qa_owned_pids = values
    return values


def remember_owner(process, namespace):
    lock = namespace / 'operation.lock'
    if lock.is_file():
        owner = lock.read_text().strip()
        if not owner.isdigit() or int(owner) not in owned_pids(process):
            raise RuntimeError('Fixture lock owner is not in the owned process group/job')


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.2):
            return True
    except OSError:
        return False


def stop_tree(process, namespace=None, port=None):
    """Stop only the process group created by this runner, then verify its port."""
    if process is not None:
        if os.name == 'nt':
            handle = getattr(process, '_qa_job', None)
            if handle is None:
                if process.poll() is None:
                    raise RuntimeError('Refusing to terminate an uncontained Windows process')
            else:
                from windows_job import close_job
                try: owned_pids(process)
                finally:
                    close_job(handle); process._qa_job = None
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                raise RuntimeError('Contained Windows job did not terminate')
            process.wait(timeout=5)
    if port is not None:
        deadline = time.monotonic() + 5
        while listening(port) and time.monotonic() < deadline:
            time.sleep(0.1)
        if listening(port):
            raise RuntimeError('Owned CI server port remained open after cleanup')
    if namespace is not None:
        owned_root = (ROOT / '.sites-runtime/test-data').resolve()
        resolved = namespace.resolve()
        if not resolved.is_relative_to(owned_root):
            raise ValueError('Cleanup namespace escaped owned test data')
        lock = resolved / 'operation.lock'
        if lock.is_file():
            owner = lock.read_text().strip()
            if process is None or not owner.isdigit() or int(owner) not in owned_pids(process) or process.poll() is None:
                raise RuntimeError('Refusing to remove another process operation lock')
            lock.unlink()


def wait_server(process, port, timeout=35, namespace=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Owned CI server exited before readiness')
        if listening(port):
            if namespace is not None: remember_owner(process, namespace)
            return
        time.sleep(0.1)
    raise TimeoutError('Owned CI server did not start before the readiness deadline')


def run_logged(command, log, timeout=1200):
    process = start_owned(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    try:
        return process.wait(timeout=timeout)
    finally:
        stop_tree(process)


def resolve_baseline(raw_sha):
    if not raw_sha or raw_sha == '0' * 40:
        raw_sha = git('rev-parse', 'HEAD^')
    if not re.fullmatch(r'[a-f0-9]{40}', raw_sha):
        raise ValueError('Baseline must be an immutable full Git SHA')
    return git('rev-parse', '--verify', raw_sha + '^{commit}')


def baseline_summary(raw_sha, output):
    candidate = git('rev-parse', 'HEAD')
    baseline = resolve_baseline(raw_sha)
    changed = git('diff', '--name-only', baseline, candidate).splitlines()
    record = {'baseline_sha': baseline, 'candidate_sha': candidate,
              'candidate_dirty': git('status', '--porcelain'),
              'changed_paths': changed,
              'identity_summary_status': 'PASS',
              'behavioral_comparison': {'status': 'REFER TO EXECUTION',
                  'report': 'comparison/comparison.json',
                  'reason': 'This file is only a source delta. The separate baseline-compare step executes paired journeys.'}}
    output.write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def export_evidence(report):
    """Copy only explicitly selected reports; local manifests and DBs never qualify."""
    target = report / 'publish'
    target.mkdir(parents=True, exist_ok=True)
    selected = [report / 'ci-summary.json', report / 'baseline-summary.json',
                report / 'source/candidate-manifest.json']
    selected += list((report / 'logs').glob('*.log'))
    for pattern in ('results.json', '*/junit.xml', '*/report.html',
                    '*/artifacts/*/evidence.json', '*/artifacts/*/failure.png',
                    '*/artifacts/*/trace.zip'):
        selected += list((report / 'matrix').glob(pattern))
    selected += list((report / 'comparison').glob('*.json'))
    selected += list((report / 'comparison').glob('*.xml'))
    for pattern in ('*/[AB]/result.json', '*/[AB]/*.png', '*/[AB]/*-accessibility.txt', '*/[AB]/trace.zip'):
        selected += list((report / 'comparison').glob(pattern))
    copied = []
    redactor = None
    for source in selected:
        if not source.is_file():
            continue
        if source.is_symlink() or not source.resolve().is_relative_to(report.resolve()):
            raise ValueError('Artifact source escapes the report root')
        destination = target / source.relative_to(report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == '.zip':
            if redactor is None:
                spec = importlib.util.spec_from_file_location('ci_trace_redactor', ROOT / 'python-playwright/tests/regression/redact_trace.py')
                redactor = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(redactor)
            # Never put unsanitized input in the directory uploaded by Actions.
            with tempfile.TemporaryDirectory(dir=report) as temporary:
                staged = Path(temporary) / 'trace.zip'
                staged.write_bytes(source.read_bytes())
                redactor.redact_trace(staged)
                with zipfile.ZipFile(staged) as archive, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as sanitized:
                    if archive.testzip() is not None:
                        raise ValueError('Invalid diagnostic trace archive')
                    for entry in archive.infolist():
                        data = archive.read(entry.filename)
                        try:
                            data = redact_log(data.decode('utf-8')).encode('utf-8')
                        except UnicodeDecodeError:
                            pass
                        if private_capability(data):
                            raise ValueError('Private guest capability remains in trace')
                        sanitized.writestr(entry, data)
        elif source.suffix == '.png':
            destination.write_bytes(source.read_bytes())
        else:
            text = redact_text(source.read_text(encoding='utf-8', errors='replace'))
            # JSON cookie objects are handled by the existing recursive redactor.
            if source.suffix == '.json':
                if redactor is None:
                    spec = importlib.util.spec_from_file_location('ci_trace_redactor', ROOT / 'python-playwright/tests/regression/redact_trace.py')
                    redactor = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(redactor)
                text = json.dumps(redactor.redact(json.loads(text)), indent=2)
            else:
                text = redact_log(text)
            data = text.encode('utf-8')
            if private_capability(data):
                raise ValueError('Private guest capability remains in evidence')
            destination.write_bytes(data)
        copied.append({'path': destination.relative_to(target).as_posix(), 'sha256': digest(destination)})
    paired = target / 'comparison/comparison.json'
    wrapper = target / 'comparison/comparison-summary.json'
    if paired.is_file() and wrapper.is_file():
        # Sanitizing/canonicalizing JSON changes bytes; retain raw and published identities.
        record = json.loads(wrapper.read_text(encoding='utf-8'))
        record['published_comparison_file_sha256'] = digest(paired)
        wrapper.write_text(json.dumps(record, indent=2), encoding='utf-8')
        for row in copied:
            if row['path'] == 'comparison/comparison-summary.json': row['sha256'] = digest(wrapper)
    (target / 'artifact-index.json').write_text(json.dumps({'files': copied}, indent=2), encoding='utf-8')
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', type=Path, default=ROOT / 'outputs/p0-10/ci')
    parser.add_argument('--baseline-sha', default='')
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    report = args.report_dir.resolve()
    if not report.is_relative_to((ROOT / 'outputs').resolve()):
        parser.error('Reports must stay under this repository outputs directory')
    if report.exists() and any(report.iterdir()):
        parser.error('Use a new empty report directory to prevent stale evidence')
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged local port')
    report.mkdir(parents=True, exist_ok=True)
    (report / 'logs').mkdir()
    (ROOT / '.sites-runtime').mkdir(exist_ok=True)
    summary = {'schema': 1, 'scope': 'local isolated CI; no hosted deployment',
               'application_sha': git('rev-parse', 'HEAD'), 'source_tree': git('rev-parse', 'HEAD^{tree}'), 'dirty_status': git('status', '--porcelain'),
               'started_utc': utc_now(), 'source': fingerprint(), 'runtime': runtime_inputs(),
               'artifact_sha256': None, 'build': None, 'status': 'FAIL', 'steps': []}
    process = None
    server_log = None
    namespace = None
    failure = None
    baseline_sha = None

    def step(name, command=None, function=None):
        path = report / 'logs' / (name + '.log')
        record = {'name': name, 'status': 'FAIL', 'exit_code': 1,
                  'log': path.relative_to(report).as_posix(), 'started_utc': utc_now()}
        summary['steps'].append(record)
        try:
            if function is not None:
                function()
                path.write_text('PASS: ' + name + '\n', encoding='utf-8')
                code = 0
            else:
                with path.open('w', encoding='utf-8') as log:
                    code = run_logged(command, log)
            record.update(status='PASS' if code == 0 else 'FAIL', exit_code=code)
            if code:
                raise RuntimeError(name + ' failed; inspect ' + str(path.relative_to(report)))
        except Exception as error:
            record['error'] = redact_text(str(error))
            raise
        finally:
            record['finished_utc'] = utc_now()

    def interrupted(signum, frame):
        raise KeyboardInterrupt('CI interrupted')

    old_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        baseline_sha = resolve_baseline(args.baseline_sha)
        summary['baseline_sha'] = baseline_sha
        step('agents', [sys.executable, 'scripts/validate_agents.py'])
        step('lint', ['node', 'node_modules/eslint/bin/eslint.js', '.', '--ignore-pattern', 'dist', '--ignore-pattern', '.next'])
        step('typecheck', ['node', 'node_modules/typescript/bin/tsc', '--noEmit'])
        step('build', [sys.executable, 'scripts/build_qa.py'])
        summary['build'] = build_identity()
        step('commerce-domain', ['node', 'scripts/test-commerce.mjs'])
        step('catalog-domain', ['node', 'scripts/test-catalog.mjs'])
        step('data-contracts', [sys.executable, 'scripts/test_data_contracts.py'])
        step('smoke-contracts', [sys.executable, 'scripts/test_smoke_contracts.py'])
        step('ci-contracts', [sys.executable, 'scripts/test_ci_checks.py'])
        step('release-contracts', [sys.executable, 'scripts/test_release_contracts.py'])
        run_id = 'ci-' + summary['application_sha'][:10] + '-' + str(os.getpid())
        namespace = ROOT / '.sites-runtime/test-data' / run_id / 'main'
        step('fixture-prepare', [sys.executable, 'scripts/test_data.py', 'prepare', '--run-id', run_id, '--worker', 'main', '--port', str(args.port)])
        server_log = (report / 'logs/server.log').open('w', encoding='utf-8')
        process = start_owned([sys.executable, 'scripts/test_data.py', 'serve', '--run-id', run_id, '--worker', 'main'],
                              cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT)
        wait_server(process, args.port, namespace=namespace)
        step('local-matrix', [sys.executable, 'scripts/run_qa_matrix.py', '--base-url', f'http://127.0.0.1:{args.port}',
                             '--manifest', str(namespace / 'manifest.json'), '--report-dir', str(report / 'matrix')])
        stop_tree(process, namespace, args.port)
        process = None
        server_log.close()
        server_log = None
        step('baseline-compare', [sys.executable, 'scripts/ci_compare.py', '--baseline-sha', baseline_sha,
                                  '--report-dir', str(report / 'comparison')])
        step('baseline-summary', function=lambda: baseline_summary(baseline_sha, report / 'baseline-summary.json'))
        step('source-archive', [sys.executable, 'scripts/candidate_manifest.py', '--output-dir', str(report / 'source'), '--name', 'candidate-source.zip'])
        summary['artifact_sha256'] = json.loads((report / 'source/candidate-manifest.json').read_text())['archive_sha256']
        if summary['source'] != fingerprint() or summary['runtime'] != runtime_inputs() or summary['build'] != build_identity():
            raise RuntimeError('Source/runtime/build changed during CI')
        summary['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as error:
        failure = error
        summary['error'] = redact_text(str(error))
    finally:
        try:
            stop_tree(process, namespace, args.port if process is not None else None)
            summary['cleanup'] = {'status': 'PASS', 'server_stopped': True}
        except Exception as error:
            summary.update(status='FAIL', cleanup={'status': 'FAIL', 'error': str(error)})
        if server_log is not None:
            server_log.close()
        signal.signal(signal.SIGTERM, old_term)
        completed = {r['name'] for r in summary['steps']}
        for name in (*CORE_STEPS, 'source-archive'):
            if name not in completed:
                summary['steps'].append({'name': name, 'status': 'NOT RUN', 'exit_code': None, 'log': None})
        summary['finished_utc'] = utc_now()
        summary['artifact_bundle'] = {'status': 'PASS', 'directory': 'publish'}
        (report / 'ci-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        try:
            export_evidence(report)
        except Exception as error:
            summary.update(status='FAIL', artifact_bundle={'status': 'FAIL', 'error': str(error)})
            (report / 'ci-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            # A bundle failure cannot leave a stale passing summary for an uploader.
            safe_summary = report / 'publish/ci-summary.json'
            if safe_summary.parent.exists():
                safe_summary.write_text(redact_text(json.dumps(summary, indent=2)), encoding='utf-8')
    print(json.dumps({'status': summary['status'], 'application_sha': summary['application_sha'], 'report': str(report)}))
    return int(summary['status'] != 'PASS' or failure is not None)


if __name__ == '__main__':
    sys.exit(main())
