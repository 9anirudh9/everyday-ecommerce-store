"""Execute the existing paired commerce journeys on two owned local D1 databases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import signal
import subprocess
import sys
import uuid

from qa_provenance import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-sha', required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    if len(args.baseline_sha) != 40 or any(c not in '0123456789abcdef' for c in args.baseline_sha):
        parser.error('Use an immutable full baseline Git SHA.')
    from ci_checks import start_owned, wait_server, stop_tree, owned_pids
    report = args.report_dir.resolve()
    report.mkdir(parents=True, exist_ok=True)
    run_id = 'release-ab-' + uuid.uuid4().hex[:12]
    baseline = ROOT / '.sites-runtime' / run_id
    baseline.parent.mkdir(parents=True, exist_ok=True)
    record = {'scope': 'executed local baseline/candidate comparison, not customer traffic',
              'baseline_sha': args.baseline_sha, 'candidate_sha': subprocess.check_output(
                  ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'started_utc': datetime.now(timezone.utc).isoformat(), 'status': 'FAIL'}
    processes, handles, leases = [], [], []
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Comparison interrupted')
    previous_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        subprocess.run(['git', 'cat-file', '-e', args.baseline_sha + '^{commit}'], cwd=ROOT, check=True)
        subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(ROOT), str(baseline)],
                       check=True, capture_output=True)
        subprocess.run(['git', 'config', 'core.autocrlf', 'false'], cwd=baseline, check=True)
        subprocess.run(['git', 'checkout', '--detach', args.baseline_sha], cwd=baseline,
                       check=True, capture_output=True)
        for name in ('pnpm-lock.yaml', 'package.json'):
            if (baseline / name).read_bytes() != (ROOT / name).read_bytes():
                raise ValueError('Baseline dependency inputs differ; prepare separately approved dependencies before comparison.')
        subprocess.run(['node', '-e', "require('node:fs').symlinkSync(process.argv[1],process.argv[2],process.platform==='win32'?'junction':'dir')",
                        str(ROOT / 'node_modules'), str(baseline / 'node_modules')], check=True)
        (baseline / '.sites-runtime').mkdir(exist_ok=True)
        with (report / 'baseline-build.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, str(baseline / 'scripts/build_qa.py')], cwd=baseline,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        # Reserve distinct ports together, then hand them to each owned local server.
        ports = []
        for _ in range(2):
            lease = socket.socket(); lease.bind(('127.0.0.1', 0)); leases.append(lease)
            ports.append(lease.getsockname()[1])
        for lease in leases: lease.close()
        for label, checkout, port in zip(('A', 'B'), (baseline, ROOT), ports):
            subprocess.run([sys.executable, str(checkout / 'scripts/test_data.py'), 'prepare',
                            '--run-id', run_id, '--worker', label, '--port', str(port)], cwd=checkout,
                           check=True, capture_output=True)
            log = (report / (label + '-server.log')).open('w', encoding='utf-8'); handles.append(log)
            command = [sys.executable, str(checkout / 'scripts/test_data.py'), 'serve', '--run-id', run_id, '--worker', label]
            process = start_owned(command, cwd=checkout, stdout=log, stderr=subprocess.STDOUT)
            namespace = checkout / '.sites-runtime/test-data' / run_id / label
            processes.append((process, namespace, port))
            wait_server(process, port, namespace=namespace)
        command = [sys.executable, str(ROOT / 'python-playwright/tests/regression/compare_commerce.py'),
                   '--baseline-root', str(baseline), '--baseline-ref', args.baseline_sha, '--baseline-modern',
                   '--baseline-url', f'http://127.0.0.1:{ports[0]}',
                   '--candidate-url', f'http://127.0.0.1:{ports[1]}', '--report-dir', str(report)]
        with (report / 'comparison.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        record['runner_exit_code'] = result.returncode
        paired = json.loads((report / 'comparison.json').read_text(encoding='utf-8'))
        # This runner's inherited intentional-change labels describe its original migration,
        # not automatically approved changes for a new release.
        record['legacy_labels_are_not_new_change_approvals'] = True
        record['comparison'] = paired['counts']
        record['comparison_file_sha256'] = hashlib.sha256((report / 'comparison.json').read_bytes()).hexdigest()
        if result.returncode or paired['counts'] != {'PASS': 10, 'REGRESSION': 0, 'INCONCLUSIVE': 0}:
            raise ValueError('Paired compatibility execution did not pass all ten cases.')
        record['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as error:
        record['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        for process, namespace, port in reversed(processes):
            try:
                if namespace.resolve().is_relative_to((ROOT / '.sites-runtime/test-data').resolve()):
                    stop_tree(process, namespace, port)
                else:
                    stop_tree(process, port=port)
                    require_root = (baseline / '.sites-runtime/test-data').resolve()
                    if not namespace.resolve().is_relative_to(require_root):
                        raise ValueError('Baseline cleanup escaped its owned fixture root')
                    lock = namespace / 'operation.lock'
                    if lock.is_file():
                        if not lock.read_text().strip().isdigit() or int(lock.read_text().strip()) not in owned_pids(process) or process.poll() is None:
                            raise ValueError('Refusing to remove another baseline owner lock')
                        lock.unlink()
            except Exception as error:
                record['status'] = 'FAIL'; record.setdefault('cleanup_errors', []).append(str(error))
        for handle in handles: handle.close()
        for lease in leases: lease.close()
        signal.signal(signal.SIGTERM, previous_term)
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (report / 'comparison-summary.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if k not in ('error', 'cleanup_errors')}))
    return int(record['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
