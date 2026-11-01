"""Run and verify public-safe smoke immediately after a verified provider deployment."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ci_checks import export_evidence
from qa_provenance import ROOT
from release_gate import origin, policy_environment
from release_monitor import require, sha, junit_counts, verify_smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployment', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=ROOT / 'config/release-policy.json')
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    report = args.report_dir.resolve(); report.mkdir(parents=True, exist_ok=True)
    (report / 'logs').mkdir(exist_ok=True)
    receipt = {'schema': 1, 'status': 'BLOCK', 'finished_utc': datetime.now(timezone.utc).isoformat()}
    record = None
    try:
        record = json.loads(args.deployment.read_text(encoding='utf-8'))
        env = policy_environment(json.loads(args.policy.read_text()), record.get('environment'))
        require(record.get('status') == 'succeeded' and origin(record.get('url')) == origin(env['url'])
                and record.get('project_id') == env['project_id'], 'Unverified provider deployment')
        require(sha(record.get('application_sha'), 40) and sha(record.get('sites_sha'), 40)
                and sha(record.get('artifact_sha256')), 'Missing deployment source/artifact identity')
        command = [sys.executable, str(ROOT / 'scripts/run_qa_matrix.py'), '--base-url', record['url'],
                   '--smoke', '--deployment-record', str(args.deployment.resolve()), '--report-dir', str(report / 'matrix')]
        with (report / 'logs/smoke.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode == 0, 'Smoke runner failed; promotion is held')
        matrix = json.loads((report / 'matrix/results.json').read_text())
        for row in matrix['runs']:
            counts = junit_counts(report / 'matrix' / (row['locale'] + '-' + row['viewport']) / 'junit.xml')
            require(all(counts[k] == row[k] for k in counts), 'Smoke JUnit and JSON disagree')
        receipt = verify_smoke(record, matrix)
        receipt['matrix_sha256'] = hashlib.sha256((report / 'matrix/results.json').read_bytes()).hexdigest()
    except Exception as error:
        receipt['reason'] = str(error) if isinstance(error, (ValueError, KeyError, FileNotFoundError)) else type(error).__name__
    receipt['reviewed_utc'] = datetime.now(timezone.utc).isoformat()
    (report / 'smoke-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    try:
        export_evidence(report)
        index_path = report / 'publish/artifact-index.json'; index = json.loads(index_path.read_text())
        for name, data in [('smoke-receipt.json', receipt), ('deployment.json', record)]:
            if data is None: continue
            path = report / 'publish' / name
            path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            index['files'].append({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        index_path.write_text(json.dumps(index, indent=2), encoding='utf-8')
    except Exception:
        receipt.update(status='BLOCK', reason='Artifact export failed; no smoke PASS is promotable')
        (report / 'smoke-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        safe = report / 'publish/smoke-receipt.json'
        if safe.parent.exists(): safe.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))
    return int(receipt['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
