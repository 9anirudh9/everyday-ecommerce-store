# P0-10 release controls

This repository supplies local/CI implementation, not proof that hosted controls
are active. See [CI.md](CI.md), [ACTIVATION.md](ACTIVATION.md) and
[ROLLBACK.md](ROLLBACK.md). Runtime results and candidate archive identity are
recorded in ignored `outputs/p0-10/EXECUTION_REPORT.md`.

## Flow and trust

1. `checks.yml` runs on pull requests, approved pushes and explicit dispatch.
   It builds the candidate, runs the full owned-D1 matrix, and executes the
   existing ten paired commerce journeys against an immutable baseline clone.
   The baseline uses a separate database; dependency input mismatch blocks reuse.
2. `release_monitor.py` independently verifies actual JUnit/matrix/comparison
   artifacts, source/archive hashes and cleanup. It is a deterministic evidence
   checker, not an always-running AI Watchtower. The coding task also requires
   an independent Watchtower source/evidence review.
3. After separately authorized merge to protected `main`, a main-branch CI run
   supplies release-eligible evidence. PR/feature runs remain useful checks but
   cannot authorize promotion. The owner reviews `release-authorize.yml` for one
   environment, Git SHA, source archive digest and operation. The owner must be
   the sole User reviewer because GitHub permits any listed reviewer to approve.
   The tool reads
   actual repository protections and rejects missing proof. An environment name
   or a JSON `approved: true` field is not authorization.
4. The authorization artifact expires no later than one hour after the request
   was created. An approval wait that exceeds that lifetime needs a new request.
   Production requires a fresh passing staging receipt for the same candidate
   and digest. A materially changed SHA/digest invalidates earlier approvals.
5. A separately approved provider bridge publishes the exact source, verifies
   provider metadata/tree identity and emits the event envelope below. A deploy
   job must directly call the reusable `post-deploy-smoke.yml` after success;
   external trusted App events can use `deployment_status`. Posting a status
   with `GITHUB_TOKEN` alone cannot be relied on to start another workflow.
6. Post-deploy smoke checks the provider identity and short-lived authorization
   before accessing an allowlisted host. It uses the protected default-branch
   test harness and records its SHA separately from the deployed provider SHA.
   All hosted application writes remain forbidden. Failed/missing/skipped smoke
   produces BLOCK and cannot become a production-promotion receipt.

Staging and production authorization/smoke workflows serialize by environment;
they do not cancel a release halfway through. The external provider bridge must
also hold a per-environment lease and deduplicate request/deployment IDs; this
repository cannot serialize an unintegrated provider's own controls.

## Default state and honest blockers

`config/release-policy.json` disables both release environments and has an empty
trusted bridge allowlist. No cloud token is added, no resource is provisioned,
and no deploy command is executed by these scripts. Production remains on its
existing Sites hosting. Native Sites publication currently has no verified
GitHub event bridge, so automated protection cannot be claimed for that path.
Direct provider administration remains an external control to restrict/audit.

GitHub's documented environment REST response does not establish the
`can_admins_bypass` setting. The validator explicitly blocks if that proof is
missing; the positive decision tests use a synthetic extended metadata fixture,
not a real GitHub response. A supported, independently verified read path or an
explicitly reviewed future integration is required before hosted activation.
Naming the environment in YAML cannot establish that control. No exception or
weaker default is silently enabled.

The branch verifier currently supports classic protected-branch metadata. It
requires fresh code-owner/last-push review, strict `P0 checks`, enforcement on
administrators, no review bypass and no force-push/deletion. Rulesets-only
repositories need an independently reviewed equivalent metadata adapter.
An optional `RELEASE_PROTECTION_READ_TOKEN` may be needed if the built-in token
cannot read these protections; creating/granting that read-only credential needs
separate approval. No privileged token is made available to PR checks.

## Provider event envelope

The bridge must use authenticated GitHub deployment/status records, not raw
untrusted JSON sent to an arbitrary URL. `deployment.sha` is the tested GitHub
commit. `deployment.payload` must contain:

```json
{
  "schema": "everyday-release-v1",
  "artifact_sha256": "<exact tested source archive digest>",
  "authorization_run_id": "<successful owner-authorization workflow run ID>",
  "authorization_attempt": 1,
  "provider": {
    "kind": "<configured provider>",
    "project_id": "<exact configured resource ID>",
    "source_sha": "<full provider source commit>",
    "source_tree": "<verified tree equal to approved GitHub source tree>",
    "version_id": "<provider-returned saved version ID>",
    "deployment_id": "<provider-returned deployment ID>"
  }
}
```

`deployment.environment` must be exactly `staging` or `production`;
`deployment_status.environment_url` must equal that environment's configured
HTTPS origin. Both record creators must match the separately approved bridge
identity. The authorization artifact is fetched from its successful protected
workflow run/attempt, not accepted from a caller's assertion. Provider and GitHub
Git histories may differ; verified source-tree equality binds them.

The current workflow does not implement provider publishing or a native Sites
API substitute. Do not fake a saved version, deployment, staging receipt or
rollback result. REL-04–08 hosted execution remains NOT RUN until the necessary
configuration, access and exact-artifact owner approvals exist.

## Sources checked for this implementation

- [GitHub token event behavior](https://docs.github.com/en/actions/concepts/security/github_token)
- [Protected environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [Deployment-status trigger](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#deployment_status)
- [Branch protection REST metadata](https://docs.github.com/en/rest/branches/branch-protection)
- [Separate Cloudflare D1 environments](https://developers.cloudflare.com/d1/configuration/environments/)
- [Windows job containment](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
