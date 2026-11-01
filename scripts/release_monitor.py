"""Deterministic independent evidence checks; no model, publish or repository writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile


REQUIRED_STEPS = {'agents', 'lint', 'typecheck', 'build', 'commerce-domain', 'catalog-domain',
                  'data-contracts', 'smoke-contracts', 'ci-contracts', 'release-contracts',
                  'fixture-prepare', 'local-matrix', 'baseline-compare', 'baseline-summary', 'source-archive'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def indexed_files(directory):
    index = read_json(directory / 'artifact-index.json')
    paths = {}
    for row in index['files']:
        relative = PurePosixPath(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts and '\\' not in row['path'], 'Unsafe evidence path')
        require(row['path'] not in paths and sha(row['sha256']), 'Duplicate path or invalid evidence digest')
        path = directory.joinpath(*relative.parts)
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()), 'Evidence path escaped bundle')
        require(file_digest(path) == row['sha256'], 'Evidence digest mismatch: ' + row['path'])
        paths[row['path']] = path
    return paths


def junit_counts(path):
    root = ET.parse(path).getroot()
    suites = list(root.iter('testsuite'))
    require(bool(suites), 'Missing JUnit suite')
    return {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}


def verify_ci(directory, promotion=False):
    paths = indexed_files(directory)
    for name in ('ci-summary.json', 'source/candidate-manifest.json', 'matrix/results.json',
                 'comparison/comparison.json', 'comparison/comparison-summary.json', 'comparison/junit.xml'):
        require(name in paths, 'Missing indexed evidence: ' + name)
    summary = read_json(paths['ci-summary.json'])
    require(summary['schema'] == 1 and summary['status'] == 'PASS', 'CI did not pass')
    require(sha(summary['application_sha'], 40) and sha(summary['artifact_sha256']), 'Missing immutable candidate identity')
    for key in ('source', 'runtime', 'build'):
        identity = summary[key]
        expected = hashlib.sha256(json.dumps(identity['files'], sort_keys=True).encode()).hexdigest()
        require(identity['sha256'] == expected, 'Invalid ' + key + ' file-map fingerprint')
    require(summary.get('cleanup', {}).get('status') == 'PASS' and summary['cleanup'].get('server_stopped') is True, 'Local server cleanup unverified')
    if promotion:
        require(not summary.get('dirty_status', '').strip(), 'Uncommitted source cannot be promoted')
    rows = summary['steps']
    names = [r['name'] for r in rows]
    require(len(names) == len(set(names)) and REQUIRED_STEPS.issubset(names), 'Missing or duplicate required CI check')
    for row in rows:
        require(row['status'] == 'PASS' and row['exit_code'] == 0, 'Failed or unexecuted CI check: ' + row['name'])
    manifest = read_json(paths['source/candidate-manifest.json'])
    require(manifest['head'] == summary['application_sha'] and manifest['archive_sha256'] == summary['artifact_sha256'], 'Candidate archive identity mismatch')
    source_files = {row['path']: row['sha256'] for row in manifest['files']}
    require(len(source_files) == len(manifest['files']), 'Duplicate source archive entry')
    for name, digest in summary['source']['files'].items():
        require(source_files.get(name) == digest, 'Tested source not present in candidate archive: ' + name)
    matrix = read_json(paths['matrix/results.json'])
    require(matrix['head'] == summary['application_sha'] and matrix['source'] == summary['source'], 'Matrix source identity mismatch')
    require(matrix['source_unchanged_during_run'] is True and matrix['build_unchanged_during_run'] is True, 'Source/build changed during tests')
    require(matrix['build_provenance']['build'] == summary['build'], 'Test build differs from candidate build')
    require({(r['locale'], r['viewport']) for r in matrix['runs']} == {('en', 'desktop'), ('en', 'mobile'), ('fr', 'desktop'), ('fr', 'mobile')}
            and len(matrix['runs']) == 4, 'Incomplete locale/viewport coverage')
    executed = 0
    for row in matrix['runs']:
        name = 'matrix/' + row['locale'] + '-' + row['viewport'] + '/junit.xml'
        require(name in paths, 'Missing matrix JUnit record')
        counts = junit_counts(paths[name])
        require(row['exit_code'] == 0 and counts['tests'] > 0 and all(counts[k] == 0 for k in ('failures', 'errors', 'skipped')), 'Matrix check failed or skipped')
        require(all(counts[k] == row[k] for k in counts), 'JUnit and matrix counts disagree')
        executed += counts['tests']
    paired = read_json(paths['comparison/comparison.json'])
    wrapper = read_json(paths['comparison/comparison-summary.json'])
    require(wrapper['status'] == 'PASS' and wrapper['baseline_sha'] == summary['baseline_sha']
            and wrapper['candidate_sha'] == summary['application_sha'], 'Comparison source mismatch')
    require(wrapper.get('published_comparison_file_sha256') == file_digest(paths['comparison/comparison.json']), 'Published comparison digest mismatch')
    require(paired['counts'] == {'PASS': 10, 'REGRESSION': 0, 'INCONCLUSIVE': 0}
            and len(paired['cases']) == 10 and all(c['comparison']['status'] == 'PASS' for c in paired['cases']), 'Behavioral comparison incomplete or regressed')
    require(paired['source_unchanged_during_run'] and paired['test_file_unchanged_during_run'], 'Comparison source changed')
    require(paired['baseline']['source_commit'] == summary['baseline_sha'] and paired['candidate']['head'] == summary['application_sha'], 'Paired checkout mismatch')
    expected_cases = {f'api_{product}_{method}' for product in (43, 46) for method in ('card', 'paypal', 'pay-later')}
    expected_cases |= {f'ui_{locale}_{viewport}' for locale in ('en', 'fr') for viewport in ('desktop', 'mobile')}
    require({c['name'] for c in paired['cases']} == expected_cases, 'Missing or duplicate paired journey')
    for case in paired['cases']:
        outcomes = []
        for side in ('A', 'B'):
            prefix = 'comparison/' + case['name'] + '/' + side + '/'
            require(prefix + 'result.json' in paths and prefix + 'trace.zip' in paths, 'Missing paired-side execution evidence')
            execution = read_json(paths[prefix + 'result.json'])
            require(execution['status'] == 'PASS' and execution['side'] == side and execution['trace_redacted'] is True
                    and execution['checks'] and all(r['status'] == 'PASS' for r in execution['checks']), 'Paired side did not pass')
            with zipfile.ZipFile(paths[prefix + 'trace.zip']) as archive:
                require(archive.testzip() is None, 'Paired trace CRC failure')
            outcomes.append(execution['outcome'])
        require(all(outcomes[0][key] == outcomes[1][key] for key in ('subtotal', 'discount', 'total', 'method', 'cart_after')),
                'Paired outcome regression')
    comparison_counts = junit_counts(paths['comparison/junit.xml'])
    require(comparison_counts == {'tests': 10, 'failures': 0, 'errors': 0, 'skipped': 0}, 'Comparison JUnit failed')
    return {'schema': 1, 'status': 'PASS', 'application_sha': summary['application_sha'],
            'artifact_sha256': summary['artifact_sha256'], 'matrix_cases': executed,
            'comparison_cases': 10, 'source_clean': not summary.get('dirty_status', '').strip(),
            'promotion_ready': not summary.get('dirty_status', '').strip()}


def verify_smoke(record, matrix):
    require(record['status'] == 'succeeded', 'Provider deployment did not succeed')
    require(record.get('environment') in ('staging', 'production') and sha(record.get('application_sha'), 40)
            and sha(record.get('sites_sha'), 40) and sha(record.get('artifact_sha256'))
            and record.get('deployment_id') and record.get('version_id') and sha(matrix.get('head'), 40),
            'Missing immutable smoke identity')
    require(matrix['url'] == record['url'] and matrix['deployment']['sites_sha'] == record['sites_sha']
            and matrix['deployment']['version_id'] == record['version_id']
            and matrix['deployment']['deployment_id'] == record['deployment_id'], 'Smoke/deployment identity mismatch')
    require(matrix['source_unchanged_during_run'] is True, 'Smoke harness changed during execution')
    require(len(matrix['runs']) == 4 and {(r['locale'], r['viewport']) for r in matrix['runs']} ==
            {('en', 'desktop'), ('en', 'mobile'), ('fr', 'desktop'), ('fr', 'mobile')}, 'Incomplete smoke matrix')
    require(all(r['exit_code'] == 0 and r.get('status') == 'PASS' and r['tests'] > 0
                and not any(r[k] for k in ('failures', 'errors', 'skipped')) for r in matrix['runs']), 'Smoke failed, skipped or not run')
    return {'schema': 1, 'status': 'PASS', 'environment': record['environment'],
            'application_sha': record['application_sha'], 'artifact_sha256': record['artifact_sha256'],
            'provider_sha': record['sites_sha'], 'version_id': record['version_id'],
            'deployment_id': record['deployment_id'], 'url': record['url'],
            'tests': sum(r['tests'] for r in matrix['runs']), 'harness_sha': matrix['head'],
            'finished_utc': matrix['finished_utc']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('ci', 'smoke'))
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--deployment', type=Path)
    parser.add_argument('--matrix', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--promotion', action='store_true')
    args = parser.parse_args()
    try:
        result = verify_ci(args.bundle.resolve(), args.promotion) if args.kind == 'ci' else verify_smoke(read_json(args.deployment), read_json(args.matrix))
    except Exception as error:
        result = {'schema': 1, 'status': 'BLOCK', 'reason': type(error).__name__ + ': ' + str(error)}
    result['reviewed_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    # Keep the upload index complete after adding the independent monitor result.
    if args.kind == 'ci' and args.bundle and args.output.resolve().is_relative_to(args.bundle.resolve()):
        index_path = args.bundle / 'artifact-index.json'
        if index_path.is_file():
            index = read_json(index_path); relative = args.output.resolve().relative_to(args.bundle.resolve()).as_posix()
            index['files'] = [r for r in index['files'] if r['path'] != relative]
            index['files'].append({'path': relative, 'sha256': file_digest(args.output)})
            index_path.write_text(json.dumps(index, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
