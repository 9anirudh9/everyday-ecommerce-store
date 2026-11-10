"""Render immutable dispatch inputs and review text locally; never approve a run."""
import json
import os
from pathlib import Path

from release_gate import ROOT, approval_statement

FIELDS = {'environment': 'TARGET_ENVIRONMENT', 'application_sha': 'APPLICATION_SHA',
          'artifact_sha256': 'ARTIFACT_SHA256', 'ci_run_id': 'CI_RUN_ID',
          'staging_smoke_run_id': 'STAGING_SMOKE_RUN_ID', 'operation': 'RELEASE_OPERATION',
          'rollback_version_id': 'ROLLBACK_VERSION_ID', 'migration_review_sha256': 'MIGRATION_REVIEW_SHA256',
          'authorization_run_id': 'GITHUB_RUN_ID'}


if __name__ == '__main__':
    policy = json.loads((ROOT / 'config/release-policy.json').read_text())
    request = {key: os.environ.get(value, '') for key, value in FIELDS.items()}
    folder = Path('outputs/p0-10/authorization'); folder.mkdir(parents=True, exist_ok=True)
    (folder / 'request.json').write_text(json.dumps(request))
    statement = approval_statement(policy, request)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write('Review the run inputs and artifact before personally approving. '
                      'Solo profile requires this exact environment review comment:\n\n```text\n'
                      + statement + '\n```\n')
    print(statement)
