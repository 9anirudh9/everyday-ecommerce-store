"""Read-only release authorization/provenance checks. This tool never deploys."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
import zipfile

from release_monitor import require, sha

ROOT = Path(__file__).resolve().parents[1]
MAX_ARTIFACT = 64 * 1024 * 1024


def timestamp(raw):
    value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    require(value.tzinfo is not None, 'Timestamp needs a timezone')
    return value.astimezone(timezone.utc)


def origin(raw):
    require(isinstance(raw, str), 'Missing target URL')
    url = urlsplit(raw)
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password
            and url.port in (None, 443) and url.path in ('', '/') and not url.query and not url.fragment,
            'Target must be a bare HTTPS origin')
    require(url.hostname != 'localhost' and '.' in url.hostname, 'Local/non-public target is forbidden')
    try:
        ipaddress.ip_address(url.hostname)
    except ValueError:
        pass
    else:
        raise ValueError('Literal IP targets are forbidden')
    return raw.rstrip('/')


def policy_environment(policy, name):
    require(policy.get('schema') == 1 and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', policy['repository']), 'Invalid release policy')
    require(name in ('staging', 'production'), 'Unknown release environment')
    env = policy['environments'][name]
    require(env.get('enabled') is True, name + ' release integration is disabled/unverified')
    origin(env.get('url'))
    require(isinstance(env.get('project_id'), str) and env['project_id'], 'Missing provider resource identity')
    require(env.get('database_id') and policy['environments']['production'].get('database_id'), 'D1 isolation identities not verified')
    stage = policy['environments']['staging']; prod = policy['environments']['production']
    require(stage.get('database_id') and stage['database_id'] != prod['database_id'], 'Staging and production D1 must be distinct')
    require(stage.get('url') and origin(stage['url']) != origin(prod['url']), 'Staging URL cannot be production')
    require(stage.get('project_id') and stage['project_id'] != prod['project_id'], 'Staging resource cannot be production')
    require(60 <= policy['approval_ttl_seconds'] <= 3600, 'Approval lifetime must be 60–3600 seconds')
    return env


def verify_environment_protection(data, owner):
    reviewers = [r for r in data.get('protection_rules', []) if r.get('type') == 'required_reviewers']
    require(len(reviewers) == 1 and reviewers[0].get('prevent_self_review') is True, 'Environment needs required review and self-review prevention')
    allowed = reviewers[0].get('reviewers', [])
    require(len(allowed) == 1 and allowed[0].get('type') == 'User'
            and allowed[0].get('reviewer', {}).get('login') == owner,
            'Owner must be the sole User reviewer; GitHub permits any listed reviewer to approve')
    # The documented REST response may omit this control. Never invent proof or
    # treat the UI setting as established: an unsupported/missing read path blocks activation.
    require('can_admins_bypass' in data, 'Environment bypass state is not exposed by verified provider metadata; activation blocked')
    require(data['can_admins_bypass'] is False, 'Administrator environment bypass must be disabled')
    branch = data.get('deployment_branch_policy') or {}
    require(branch.get('protected_branches') is True and branch.get('custom_branch_policies') is False, 'Environment must restrict deployments to protected branches')


def successful_run(run, policy, path, sha_value=None):
    require(run.get('repository', {}).get('full_name') == policy['repository'], 'Workflow repository mismatch')
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success', 'Required workflow did not succeed')
    direct = run.get('path', '').split('@')[0] == path
    references = [r for r in run.get('referenced_workflows', [])
                  if r.get('path', '').startswith(policy['repository'] + '/' + path + '@') and sha(r.get('sha'), 40)]
    require(direct or len(references) == 1, 'Unexpected workflow identity')
    if sha_value is not None:
        require(run.get('head_sha') == sha_value, 'Workflow candidate SHA mismatch')


def verify_branch_protection(data):
    reviews = data.get('required_pull_request_reviews') or {}
    require(reviews.get('require_code_owner_reviews') is True and reviews.get('required_approving_review_count', 0) >= 1
            and reviews.get('dismiss_stale_reviews') is True and reviews.get('require_last_push_approval') is True,
            'Protected release branch needs fresh code-owner and last-push reviews')
    bypass = reviews.get('bypass_pull_request_allowances') or {}
    require(not any(bypass.get(key) for key in ('users', 'teams', 'apps')), 'Pull-request review bypass is forbidden')
    checks = data.get('required_status_checks') or {}
    names = set(checks.get('contexts', [])) | {r.get('context') for r in checks.get('checks', [])}
    require(checks.get('strict') is True and 'P0 checks' in names, 'P0 checks must be required on the up-to-date release branch')
    require(data.get('enforce_admins', {}).get('enabled') is True, 'Branch administrator bypass must be disabled')
    require(data.get('allow_force_pushes', {}).get('enabled') is False
            and data.get('allow_deletions', {}).get('enabled') is False, 'Protected history must be retained')


def protected_source(reader, policy, value):
    require(sha(value, 40), 'Missing protected source identity')
    branch_name = quote(policy['release_branch'], safe='')
    branch = reader.request('/branches/' + branch_name)
    require(branch.get('protected') is True and sha(branch.get('commit', {}).get('sha'), 40), 'Release branch is not protected')
    verify_branch_protection(reader.protection_request('/branches/' + branch_name + '/protection'))
    comparison = reader.request('/compare/' + value + '...' + branch['commit']['sha'])
    require(comparison.get('merge_base_commit', {}).get('sha') == value, 'Evidence source is not in protected release history')


def trusted_run(reader, run, policy, path, sha_value=None):
    successful_run(run, policy, path, sha_value)
    require(run.get('head_branch') == policy['release_branch'] and run.get('event') != 'pull_request',
            'PR/feature workflow evidence cannot authorize release promotion')
    # A path/success claim from a PR or arbitrary feature workflow is insufficient.
    # Only immutable revisions in owner-reviewed protected release history qualify.
    protected_source(reader, policy, run.get('head_sha'))
    for reference in run.get('referenced_workflows', []):
        protected_source(reader, policy, reference.get('sha'))


def validate_approval(approval, policy, name, app_sha, artifact_sha, now):
    env = policy_environment(policy, name)
    require(approval.get('schema') == 1 and approval.get('environment') == name, 'Approval environment mismatch')
    require(approval.get('application_sha') == app_sha and approval.get('artifact_sha256') == artifact_sha,
            'Approval does not identify the exact candidate')
    require(sha(app_sha, 40) and sha(artifact_sha) and sha(approval.get('source_tree'), 40), 'Invalid immutable approval identity')
    issued, expires = timestamp(approval['issued_utc']), timestamp(approval['expires_utc'])
    require(issued <= now < expires and expires - issued <= timedelta(seconds=policy['approval_ttl_seconds']), 'Approval expired, future-dated or too long')
    require(approval.get('repository') == policy['repository'] and approval.get('provider') == env['provider']
            and approval.get('project_id') == env['project_id'], 'Approval provider/repository mismatch')
    require(approval.get('operation') in ('publish', 'rollback'), 'Unknown release operation')
    if approval['operation'] == 'rollback':
        require(approval.get('rollback_version_id') and sha(approval.get('migration_review_sha256')), 'Rollback needs exact saved version and migration compatibility review')
    return env


def deployment_from_event(event, policy, approval, now):
    require(event.get('repository', {}).get('full_name') == policy['repository'], 'Deployment repository mismatch')
    deployment, status = event['deployment'], event['deployment_status']
    trusted = policy.get('trusted_bridge_logins', [])
    require(trusted and deployment.get('creator', {}).get('login') in trusted
            and status.get('creator', {}).get('login') in trusted, 'Deployment bridge identity is not approved')
    require(status.get('state') == 'success', 'Deployment did not succeed; smoke cannot pass')
    payload = deployment.get('payload')
    require(isinstance(payload, dict) and payload.get('schema') == 'everyday-release-v1', 'Missing trusted provider provenance')
    name = deployment.get('environment')
    env = validate_approval(approval, policy, name, deployment.get('sha'), payload.get('artifact_sha256'), now)
    require(origin(status.get('environment_url')) == origin(env['url']), 'Deployment URL is not allowlisted for this environment')
    provider = payload.get('provider')
    require(isinstance(provider, dict) and provider.get('kind') == env['provider']
            and provider.get('project_id') == env['project_id'], 'Provider resource mismatch')
    require(provider.get('source_tree') == approval['source_tree'] and sha(provider.get('source_sha'), 40), 'Provider source tree is not the approved source')
    for key in ('version_id', 'deployment_id'):
        value = provider.get(key)
        require(isinstance(value, str) and 0 < len(value) <= 250 and '\n' not in value and '\r' not in value, 'Missing provider ' + key)
    require(payload.get('authorization_run_id') == approval['authorization_run_id']
            and payload.get('authorization_attempt') == approval['authorization_attempt'], 'Wrong authorization run/attempt')
    if approval['operation'] == 'rollback':
        require(provider['version_id'] == approval['rollback_version_id'], 'Rollback selected the wrong saved version')
    return {'schema': 1, 'environment': name, 'url': origin(env['url']), 'status': 'succeeded',
            'application_sha': deployment['sha'], 'artifact_sha256': payload['artifact_sha256'],
            'sites_sha': provider['source_sha'], 'version_id': provider['version_id'],
            'deployment_id': provider['deployment_id'], 'project_id': provider['project_id'],
            'authorization_run_id': approval['authorization_run_id'], 'operation': approval['operation'],
            'verified_utc': now.isoformat()}


def validate_staging_receipt(receipt, policy, app_sha, artifact_sha, now):
    require(receipt.get('status') == 'PASS' and receipt.get('environment') == 'staging', 'Successful staging smoke is required')
    require(receipt.get('application_sha') == app_sha and receipt.get('artifact_sha256') == artifact_sha,
            'Staging smoke belongs to a different candidate')
    require(origin(receipt['url']) == origin(policy['environments']['staging']['url']), 'Staging smoke URL mismatch')
    age = now - timestamp(receipt['finished_utc'])
    require(timedelta(0) <= age <= timedelta(seconds=policy['staging_evidence_ttl_seconds']), 'Staging evidence is stale')
    require(receipt.get('tests', 0) > 0 and sha(receipt.get('harness_sha'), 40), 'Staging smoke was not executed')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubReader:
    """GET-only access; credentials never follow artifact-storage redirects."""
    def __init__(self, repository, token):
        require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'Invalid repository')
        require(bool(token), 'GITHUB_TOKEN is required for provider evidence reads')
        self.repository, self.token = repository, token

    def protection_request(self, path):
        token = os.environ.get('RELEASE_PROTECTION_READ_TOKEN')
        if not token:
            return self.request(path)  # Fail closed if the built-in token lacks metadata permission.
        return GitHubReader(self.repository, token).request(path)

    def request(self, path, binary=False):
        require(path.startswith('/') and '..' not in path, 'Invalid GitHub API path')
        request = Request('https://api.github.com/repos/' + self.repository + path,
                          headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                                   'User-Agent': 'EverydayShop-Release-Gate', 'X-GitHub-Api-Version': '2022-11-28'})
        try:
            response = build_opener(NoRedirect()).open(request, timeout=30)
        except HTTPError as error:
            if not binary or error.code != 302:
                raise ValueError('GitHub evidence request failed with HTTP ' + str(error.code)) from None
            target = error.headers.get('Location', ''); parsed = urlsplit(target)
            require(parsed.scheme == 'https' and not parsed.username and not parsed.password
                    and parsed.hostname and any(parsed.hostname.endswith('.' + domain) or parsed.hostname == domain
                                                for domain in ('github.com', 'githubusercontent.com', 'blob.core.windows.net')),
                    'Unexpected artifact storage redirect')
            # Deliberately omit Authorization on the signed artifact URL.
            response = build_opener(NoRedirect()).open(Request(target), timeout=30)
        with response:
            data = response.read(MAX_ARTIFACT + 1)
        require(len(data) <= MAX_ARTIFACT, 'Evidence exceeds artifact size limit')
        return data if binary else json.loads(data)

    def run(self, run_id):
        require(str(run_id).isdigit(), 'Workflow run ID must be numeric')
        return self.request('/actions/runs/' + str(run_id))

    def artifact_json(self, run, name_prefix, filename):
        records = self.request('/actions/runs/' + str(run['id']) + '/artifacts?per_page=100')
        require(records.get('total_count', 0) <= 100, 'Ambiguous artifact listing')
        candidates = [r for r in records.get('artifacts', []) if r['name'] == name_prefix and not r.get('expired')]
        require(len(candidates) == 1, 'Required immutable workflow artifact is absent or ambiguous')
        raw = self.request('/actions/artifacts/' + str(candidates[0]['id']) + '/zip', binary=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist(); require(len(names) == len(set(names)), 'Duplicate evidence entry')
            require(sum(i.file_size for i in archive.infolist()) <= 256 * 1024 * 1024, 'Expanded evidence too large')
            require(archive.testzip() is None, 'Artifact CRC failure')
            require(filename in names and archive.getinfo(filename).file_size < 4 * 1024 * 1024, 'Missing evidence JSON')
            return json.loads(archive.read(filename))


def authorize(reader, policy, request, now):
    name, app_sha, digest = request['environment'], request['application_sha'], request['artifact_sha256']
    env = policy_environment(policy, name)
    require(sha(app_sha, 40) and sha(digest), 'Use full candidate SHA and SHA-256 digest')
    verify_environment_protection(reader.request('/environments/' + quote(name, safe='')), policy['owner_login'])
    current = reader.run(request['authorization_run_id'])
    require(current.get('event') == 'workflow_dispatch' and current.get('head_branch') == policy['release_branch']
            and current.get('path', '').split('@')[0] == '.github/workflows/release-authorize.yml', 'Authorization must run from the protected release branch')
    require(current.get('repository', {}).get('full_name') == policy['repository'], 'Authorization repository mismatch')
    protected_source(reader, policy, current.get('head_sha'))
    require(timedelta(0) <= now - timestamp(current['created_at']) < timedelta(seconds=policy['approval_ttl_seconds']), 'Request expired while waiting for approval; request a new approval')
    ci = reader.run(request['ci_run_id']); trusted_run(reader, ci, policy, '.github/workflows/checks.yml', app_sha)
    name_prefix = 'p0-checks-' + app_sha + '-' + str(ci['run_attempt'])
    summary = reader.artifact_json(ci, name_prefix, 'ci-summary.json')
    monitor = reader.artifact_json(ci, name_prefix, 'monitor.json')
    require(summary.get('status') == 'PASS' and summary.get('application_sha') == app_sha
            and summary.get('artifact_sha256') == digest and not summary.get('dirty_status', '').strip(), 'CI artifact identity or clean source mismatch')
    require(monitor.get('status') == 'PASS' and monitor.get('promotion_ready') is True
            and monitor.get('application_sha') == app_sha and monitor.get('artifact_sha256') == digest, 'Independent CI evidence monitor did not pass')
    commit = reader.request('/git/commits/' + app_sha)
    tree = commit['tree']['sha']; require(sha(tree, 40), 'Missing source tree identity')
    if name == 'production':
        smoke = reader.run(request.get('staging_smoke_run_id', ''))
        trusted_run(reader, smoke, policy, '.github/workflows/post-deploy-smoke.yml')
        receipt = reader.artifact_json(smoke, 'p0-smoke-' + str(smoke['id']) + '-' + str(smoke['run_attempt']), 'smoke-receipt.json')
        validate_staging_receipt(receipt, policy, app_sha, digest, now)
        protected_source(reader, policy, receipt['harness_sha'])
    operation = request.get('operation', 'publish')
    approval = {'schema': 1, 'repository': policy['repository'], 'environment': name,
                'application_sha': app_sha, 'artifact_sha256': digest, 'source_tree': tree,
                'provider': env['provider'], 'project_id': env['project_id'], 'operation': operation,
                'authorization_run_id': str(current['id']), 'authorization_attempt': int(current['run_attempt']),
                'ci_run_id': str(ci['id']), 'issued_utc': now.isoformat(),
                'expires_utc': (timestamp(current['created_at']) + timedelta(seconds=policy['approval_ttl_seconds'])).isoformat(),
                'rollback_version_id': request.get('rollback_version_id'),
                'migration_review_sha256': request.get('migration_review_sha256')}
    validate_approval(approval, policy, name, app_sha, digest, now)
    return approval


def verified_event(reader, policy, event, now):
    payload = event['deployment'].get('payload')
    require(isinstance(payload, dict), 'Provider payload missing')
    run = reader.run(payload.get('authorization_run_id', ''))
    trusted_run(reader, run, policy, '.github/workflows/release-authorize.yml')
    require(run['head_branch'] == policy['release_branch'] and run['event'] == 'workflow_dispatch', 'Authorization ran from untrusted context')
    require(int(run['run_attempt']) == payload.get('authorization_attempt'), 'Authorization attempt mismatch')
    approval = reader.artifact_json(run, 'p0-approval-' + str(run['id']) + '-' + str(run['run_attempt']), 'approval.json')
    return deployment_from_event(event, policy, approval, now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('authorize', 'event'))
    parser.add_argument('--policy', type=Path, default=ROOT / 'config/release-policy.json')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding='utf-8'))
        data = json.loads(args.input.read_text(encoding='utf-8'))
        reader = GitHubReader(policy['repository'], os.environ.get('GITHUB_TOKEN'))
        now = datetime.now(timezone.utc)
        result = authorize(reader, policy, data, now) if args.action == 'authorize' else verified_event(reader, policy, data, now)
    except Exception as error:
        # Do not print HTTP bodies, response objects, tokens or signed artifact URLs.
        result = {'status': 'BLOCK', 'reason': str(error) if isinstance(error, (ValueError, KeyError)) else type(error).__name__}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'BLOCK' if result.get('status') == 'BLOCK' else 'VERIFIED', 'output': str(args.output)}))
    return int(result.get('status') == 'BLOCK')


if __name__ == '__main__':
    sys.exit(main())
