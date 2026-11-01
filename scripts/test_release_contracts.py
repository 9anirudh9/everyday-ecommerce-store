"""Local release rejection/monitor contracts. All provider/API records here are synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import release_gate as gate
import release_monitor as monitor
import post_deploy_smoke as smoke
import staging_config as staging
from qa_provenance import ROOT

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
APP, TREE, DIGEST = 'a' * 40, 'b' * 40, 'c' * 64


def policy():
    result = json.loads((ROOT / 'config/release-policy.json').read_text())
    result['trusted_bridge_logins'] = ['approved-provider[bot]']
    result['environments']['staging'].update(enabled=True, url='https://everyday-shop-staging.test.workers.dev',
                                           project_id='staging-resource', database_id='d1-stage')
    result['environments']['production'].update(enabled=True, database_id='d1-prod')
    return result


def approval(environment='staging'):
    env = policy()['environments'][environment]
    return {'schema': 1, 'repository': policy()['repository'], 'environment': environment,
            'application_sha': APP, 'source_tree': TREE, 'artifact_sha256': DIGEST,
            'provider': env['provider'], 'project_id': env['project_id'], 'operation': 'publish',
            'authorization_run_id': '100', 'authorization_attempt': 1,
            'issued_utc': (NOW - timedelta(minutes=1)).isoformat(),
            'expires_utc': (NOW + timedelta(minutes=20)).isoformat()}


def event(environment='staging'):
    p = policy(); env = p['environments'][environment]
    return {'repository': {'full_name': p['repository']},
            'deployment': {'sha': APP, 'environment': environment, 'creator': {'login': 'approved-provider[bot]'},
                           'payload': {'schema': 'everyday-release-v1', 'artifact_sha256': DIGEST,
                                       'authorization_run_id': '100', 'authorization_attempt': 1,
                                       'provider': {'kind': env['provider'], 'project_id': env['project_id'],
                                                    'source_sha': 'd' * 40, 'source_tree': TREE,
                                                    'version_id': 'provider-version-exact', 'deployment_id': 'provider-deployment-exact'}}},
            'deployment_status': {'state': 'success', 'environment_url': env['url'],
                                  'creator': {'login': 'approved-provider[bot]'}}}


def matrix(record):
    return {'url': record['url'], 'deployment': record, 'head': 'e' * 40,
            'source_unchanged_during_run': True, 'finished_utc': NOW.isoformat(),
            'runs': [{'locale': lang, 'viewport': view, 'status': 'PASS', 'exit_code': 0,
                      'tests': 5, 'failures': 0, 'errors': 0, 'skipped': 0}
                     for lang in ('en', 'fr') for view in ('desktop', 'mobile')]}


class ReleaseContracts(unittest.TestCase):
    def test_repository_defaults_block_all_publication(self):
        configured = json.loads((ROOT / 'config/release-policy.json').read_text())
        for name in ('staging', 'production'):
            with self.assertRaises(ValueError): gate.policy_environment(configured, name)

    def test_environment_needs_actual_owner_review_and_no_bypass(self):
        valid = {'protection_rules': [{'type': 'required_reviewers', 'prevent_self_review': True,
                                      'reviewers': [{'type': 'User', 'reviewer': {'login': '9anirudh9'}}]}],
                 'can_admins_bypass': False,
                 'deployment_branch_policy': {'protected_branches': True, 'custom_branch_policies': False}}
        gate.verify_environment_protection(valid, '9anirudh9')
        variants = [deepcopy(valid) for _ in range(4)]
        variants[0]['protection_rules'] = []
        variants[1]['protection_rules'][0]['prevent_self_review'] = False
        variants[2]['can_admins_bypass'] = True
        variants[3]['deployment_branch_policy'] = None
        for data in variants:
            with self.assertRaises(ValueError): gate.verify_environment_protection(data, '9anirudh9')
        missing_control = deepcopy(valid); del missing_control['can_admins_bypass']
        with self.assertRaisesRegex(ValueError, 'not exposed'):
            gate.verify_environment_protection(missing_control, '9anirudh9')
        for extra in [{'type': 'User', 'reviewer': {'login': 'other-maintainer'}},
                      {'type': 'Team', 'reviewer': {'slug': 'other-team'}}]:
            mixed = deepcopy(valid); mixed['protection_rules'][0]['reviewers'].append(extra)
            with self.assertRaisesRegex(ValueError, 'sole User'):
                gate.verify_environment_protection(mixed, '9anirudh9')
        team = deepcopy(valid); team['protection_rules'][0]['reviewers'][0]['type'] = 'Team'
        with self.assertRaisesRegex(ValueError, 'sole User'):
            gate.verify_environment_protection(team, '9anirudh9')

    def test_feature_or_unprotected_workflow_cannot_forge_promotion_evidence(self):
        protection = {'required_pull_request_reviews': {'require_code_owner_reviews': True,
                      'required_approving_review_count': 1, 'dismiss_stale_reviews': True,
                      'require_last_push_approval': True}, 'required_status_checks': {'strict': True, 'contexts': ['P0 checks']},
                      'enforce_admins': {'enabled': True}, 'allow_force_pushes': {'enabled': False},
                      'allow_deletions': {'enabled': False}}
        class Reader:
            def request(self, path):
                if path.startswith('/branches/'):
                    return {'protected': True, 'commit': {'sha': '1' * 40}}
                if path.startswith('/compare/'):
                    value = path.split('/compare/')[1].split('...')[0]
                    return {'merge_base_commit': {'sha': value if value == APP else '2' * 40}}
                raise AssertionError(path)
            def protection_request(self, path): return protection
        valid = {'repository': {'full_name': policy()['repository']}, 'status': 'completed', 'conclusion': 'success',
                 'path': '.github/workflows/checks.yml', 'head_branch': 'main', 'head_sha': APP, 'event': 'push'}
        gate.trusted_run(Reader(), valid, policy(), '.github/workflows/checks.yml', APP)
        for wrong in [{**valid, 'head_branch': 'feature/forged'}, {**valid, 'event': 'pull_request'},
                      {**valid, 'head_sha': '9' * 40}]:
            with self.assertRaises(ValueError): gate.trusted_run(Reader(), wrong, policy(), '.github/workflows/checks.yml')
        protection['enforce_admins']['enabled'] = False
        with self.assertRaises(ValueError): gate.trusted_run(Reader(), valid, policy(), '.github/workflows/checks.yml')

    def test_staging_cannot_reuse_production_resource_database_or_url(self):
        for key in ('database_id', 'project_id', 'url'):
            p = policy(); p['environments']['staging'][key] = p['environments']['production'][key]
            with self.subTest(key=key), self.assertRaises(ValueError): gate.policy_environment(p, 'staging')

    def test_authorization_chain_checks_real_run_fields_and_staging_candidate(self):
        p = policy()
        protection = {'required_pull_request_reviews': {'require_code_owner_reviews': True,
                      'required_approving_review_count': 1, 'dismiss_stale_reviews': True,
                      'require_last_push_approval': True}, 'required_status_checks': {'strict': True, 'contexts': ['P0 checks']},
                      'enforce_admins': {'enabled': True}, 'allow_force_pushes': {'enabled': False}, 'allow_deletions': {'enabled': False}}
        environment = {'protection_rules': [{'type': 'required_reviewers', 'prevent_self_review': True,
                                           'reviewers': [{'type': 'User', 'reviewer': {'login': p['owner_login']}}]}],
                       'can_admins_bypass': False,
                       'deployment_branch_policy': {'protected_branches': True, 'custom_branch_policies': False}}
        class Reader:
            feature = False
            wrong_candidate = False
            def run(self, run_id):
                names = {'100': 'release-authorize.yml', '200': 'checks.yml', '300': 'post-deploy-smoke.yml'}
                return {'id': int(run_id), 'repository': {'full_name': p['repository']}, 'head_sha': APP,
                        'head_branch': 'feature/forged' if self.feature and str(run_id) == '200' else 'main',
                        'path': '.github/workflows/' + names[str(run_id)], 'event': 'workflow_dispatch',
                        'status': 'completed', 'conclusion': 'success', 'run_attempt': 1,
                        'created_at': (NOW - timedelta(minutes=2)).isoformat()}
            def request(self, path):
                if path.startswith('/environments/'): return environment
                if path.startswith('/branches/'): return {'protected': True, 'commit': {'sha': APP}}
                if path.startswith('/compare/'): return {'merge_base_commit': {'sha': APP}}
                if path.startswith('/git/commits/'): return {'tree': {'sha': TREE}}
                raise AssertionError(path)
            def protection_request(self, path): return protection
            def artifact_json(self, run, prefix, filename):
                if filename == 'ci-summary.json': return {'status': 'PASS', 'application_sha': APP, 'artifact_sha256': DIGEST, 'dirty_status': ''}
                if filename == 'monitor.json': return {'status': 'PASS', 'promotion_ready': True, 'application_sha': APP, 'artifact_sha256': DIGEST}
                return {'status': 'PASS', 'environment': 'staging', 'application_sha': 'f' * 40 if self.wrong_candidate else APP,
                        'artifact_sha256': DIGEST, 'url': p['environments']['staging']['url'],
                        'finished_utc': NOW.isoformat(), 'tests': 20, 'harness_sha': APP}
        request = {'environment': 'production', 'application_sha': APP, 'artifact_sha256': DIGEST,
                   'authorization_run_id': '100', 'ci_run_id': '200', 'staging_smoke_run_id': '300'}
        reader = Reader(); result = gate.authorize(reader, p, request, NOW)
        self.assertEqual(result['environment'], 'production')
        reader.feature = True
        with self.assertRaises(ValueError): gate.authorize(reader, p, request, NOW)
        reader.feature = False; reader.wrong_candidate = True
        with self.assertRaises(ValueError): gate.authorize(reader, p, request, NOW)

    def test_exact_approval_and_separate_environment(self):
        gate.validate_approval(approval(), policy(), 'staging', APP, DIGEST, NOW)
        for name, sha, digest in [('production', APP, DIGEST), ('staging', 'f' * 40, DIGEST), ('staging', APP, 'f' * 64)]:
            with self.assertRaises(ValueError): gate.validate_approval(approval(), policy(), name, sha, digest, NOW)

    def test_expired_future_and_excessive_approvals_are_rejected(self):
        for start, end in [(-120, -1), (1, 20), (-1, 61)]:
            data = approval(); data['issued_utc'] = (NOW + timedelta(minutes=start)).isoformat()
            data['expires_utc'] = (NOW + timedelta(minutes=end)).isoformat()
            with self.assertRaises(ValueError): gate.validate_approval(data, policy(), 'staging', APP, DIGEST, NOW)

    def test_verified_success_keeps_github_and_provider_sources_distinct(self):
        record = gate.deployment_from_event(event(), policy(), approval(), NOW)
        self.assertEqual(record['application_sha'], APP)
        self.assertEqual(record['sites_sha'], 'd' * 40)
        self.assertEqual(record['status'], 'succeeded')

    def test_failed_or_unknown_provider_deployment_never_passes(self):
        for state in ('failure', 'error', 'pending', 'in_progress', ''):
            data = event(); data['deployment_status']['state'] = state
            with self.subTest(state=state), self.assertRaises(ValueError): gate.deployment_from_event(data, policy(), approval(), NOW)

    def test_url_and_provider_mismatch_are_blocked_before_browser_launch(self):
        variants = [event() for _ in range(5)]
        variants[0]['deployment_status']['environment_url'] = 'https://evil.example'
        variants[1]['deployment']['payload']['provider']['project_id'] = 'production-resource'
        variants[2]['deployment']['payload']['provider']['source_tree'] = 'e' * 40
        variants[3]['deployment']['payload']['provider']['source_sha'] = ''
        variants[4]['deployment']['payload']['provider']['deployment_id'] = ''
        for data in variants:
            with self.assertRaises(ValueError): gate.deployment_from_event(data, policy(), approval(), NOW)

    def test_unapproved_bridge_or_repository_is_blocked(self):
        for key in ('creator', 'repository', 'attempt'):
            data = event()
            if key == 'creator': data['deployment_status']['creator']['login'] = 'unapproved[bot]'
            if key == 'repository': data['repository']['full_name'] = 'someone/fork'
            if key == 'attempt': data['deployment']['payload']['authorization_attempt'] = 2
            with self.assertRaises(ValueError): gate.deployment_from_event(data, policy(), approval(), NOW)

    def test_rollback_requires_saved_version_and_migration_review(self):
        data = approval(); data['operation'] = 'rollback'
        with self.assertRaises(ValueError): gate.validate_approval(data, policy(), 'staging', APP, DIGEST, NOW)
        data.update(rollback_version_id='known-good', migration_review_sha256='f' * 64)
        gate.validate_approval(data, policy(), 'staging', APP, DIGEST, NOW)
        with self.assertRaises(ValueError): gate.deployment_from_event(event(), policy(), data, NOW)
        provider_event = event(); provider_event['deployment']['payload']['provider']['version_id'] = 'known-good'
        self.assertEqual(gate.deployment_from_event(provider_event, policy(), data, NOW)['operation'], 'rollback')

    def test_production_requires_fresh_same_candidate_staging_receipt(self):
        receipt = {'status': 'PASS', 'environment': 'staging', 'application_sha': APP, 'artifact_sha256': DIGEST,
                   'url': policy()['environments']['staging']['url'], 'finished_utc': NOW.isoformat(),
                   'tests': 20, 'harness_sha': 'e' * 40}
        gate.validate_staging_receipt(receipt, policy(), APP, DIGEST, NOW)
        for key, value in [('status', 'FAIL'), ('application_sha', 'f' * 40), ('tests', 0),
                           ('finished_utc', (NOW - timedelta(days=2)).isoformat())]:
            wrong = {**receipt, key: value}
            with self.assertRaises(ValueError): gate.validate_staging_receipt(wrong, policy(), APP, DIGEST, NOW)

    def test_smoke_failure_missing_sha_or_missing_matrix_cell_blocks_promotion(self):
        record = gate.deployment_from_event(event(), policy(), approval(), NOW)
        good = matrix(record); self.assertEqual(monitor.verify_smoke(record, good)['tests'], 20)
        variants = [deepcopy(good) for _ in range(4)]
        variants[0]['runs'][0]['exit_code'] = 1
        variants[1]['runs'] = []
        variants[2]['deployment']['sites_sha'] = ''
        variants[3]['runs'][0]['skipped'] = 1
        for data in variants:
            with self.assertRaises(ValueError): monitor.verify_smoke(record, data)

    def test_missing_ci_evidence_and_tampered_file_are_blocked(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.sites-runtime') as raw:
            folder = Path(raw); (folder / 'artifact-index.json').write_text(json.dumps({'files': []}))
            with self.assertRaises(ValueError): monitor.verify_ci(folder)
            (folder / 'ci-summary.json').write_text('{}')
            (folder / 'artifact-index.json').write_text(json.dumps({'files': [{'path': 'ci-summary.json', 'sha256': 'f' * 64}]}))
            with self.assertRaises(ValueError): monitor.verify_ci(folder)

    def test_ci_index_cannot_escape_or_duplicate_an_entry(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.sites-runtime') as raw:
            folder = Path(raw)
            for path in ('../secret.json', '/secret.json', '..\\secret.json'):
                (folder / 'artifact-index.json').write_text(json.dumps({'files': [{'path': path, 'sha256': DIGEST}]}))
                with self.assertRaises(ValueError): monitor.indexed_files(folder)

    def test_staging_renderer_refuses_production_binding_and_requires_provisioning(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.sites-runtime') as raw:
            root = Path(raw); (root / 'dist/server').mkdir(parents=True); (root / 'dist/client').mkdir()
            (root / 'dist/server/index.js').write_text('export default {}')
            built = {'main': 'index.js', 'assets': {'directory': '../client'}, 'compatibility_date': '2026-05-15'}
            data = {'schema': 1, 'environment': 'staging', 'provisioning_approved': True, 'account_id': 'a' * 32,
                    'database_id': '11111111-1111-4111-8111-111111111111',
                    'production_database_id': '22222222-2222-4222-8222-222222222222',
                    'worker_name': 'everyday-shop-staging', 'production_worker_name': 'production-worker',
                    'url': 'https://everyday-shop-staging.test.workers.dev'}
            rendered = staging.render(data, built, root)
            self.assertEqual(rendered['d1_databases'][0]['database_id'], data['database_id'])
            self.assertEqual(rendered['routes'], [])
            for wrong in [{**data, 'database_id': data['production_database_id']}, {**data, 'provisioning_approved': False}]:
                with self.assertRaises(ValueError): staging.render(wrong, built, root)

    def test_failed_deployment_creates_block_receipt_without_running_browser(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.sites-runtime') as raw:
            directory = Path(raw); source = directory / 'deployment.json'; config = directory / 'policy.json'
            source.write_text(json.dumps({'status': 'BLOCK'})); config.write_text(json.dumps(policy()))
            with patch.object(sys, 'argv', ['smoke', '--deployment', str(source), '--policy', str(config), '--report-dir', str(directory / 'report')]), \
                    patch.object(smoke.subprocess, 'run') as runner:
                self.assertEqual(smoke.main(), 1); runner.assert_not_called()
            receipt = json.loads((directory / 'report/smoke-receipt.json').read_text())
            self.assertEqual(receipt['status'], 'BLOCK')

    def test_workflow_yaml_and_security_boundaries(self):
        # Use an already installed, locked transitive parser; install nothing here.
        node = "const fs=require('fs'),p=require('path');const v=fs.readdirSync('node_modules/.pnpm').find(x=>x.startsWith('js-yaml@'));const y=require(p.resolve('node_modules/.pnpm',v,'node_modules/js-yaml'));console.log(JSON.stringify(y.load(fs.readFileSync(process.argv[1],'utf8'))))"
        workflows = {}
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            data = json.loads(subprocess.check_output(['node', '-e', node, str(path)], cwd=ROOT, text=True))
            workflows[path.name] = data
            self.assertNotIn('pull_request_target', data['on'])
            self.assertNotIn('schedule', data['on'])
            for job in data['jobs'].values():
                for step in job.get('steps', []):
                    if step.get('uses', '').startswith('actions/'):
                        self.assertRegex(step['uses'], r'^actions/[a-z-]+@[a-f0-9]{40}$')
                    self.assertNotIn('${{ inputs.', step.get('run', ''))
        self.assertEqual(workflows['checks.yml']['permissions'], {'contents': 'read'})
        self.assertIn('deployment_status', workflows['post-deploy-smoke.yml']['on'])
        self.assertIn('workflow_call', workflows['post-deploy-smoke.yml']['on'])
        self.assertFalse(workflows['release-authorize.yml']['concurrency']['cancel-in-progress'])
        self.assertFalse(workflows['post-deploy-smoke.yml']['concurrency']['cancel-in-progress'])


if __name__ == '__main__':
    (ROOT / '.sites-runtime').mkdir(exist_ok=True)
    unittest.main(verbosity=2)
