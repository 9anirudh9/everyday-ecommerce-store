# P0 local CI checks

`.github/workflows/checks.yml` defines the stable **P0 checks** job on pull
requests, pushes to `main`/`feature/p0-*`, and explicit workflow dispatch. It
uses immutable official action commits, `contents: read`, no persisted checkout
credentials and no deployment secrets. There is no `pull_request_target` or
scheduled trigger. Obsolete checks for the same ref can be cancelled; release
workflows need separate non-cancelling concurrency.

The hosted runner is Ubuntu, Node 22, pnpm 11.25.0, Python 3.13 and the pinned
Python dependency closure. It installs the Chrome channel because the current
browser fixtures explicitly use that channel. These authored Linux setup steps
are **NOT RUN** until an approved GitHub workflow executes. Local Windows
results do not establish Ubuntu/package-download compatibility.

With existing dependencies/browser installed, run from the repository root:

```powershell
.sites-runtime/qa-venv/Scripts/python.exe scripts/ci_checks.py --baseline-sha cfc24790c2180607971ed1b14df4696136eda7d6 --report-dir outputs/p0-10/ci-local
```

Use an empty output directory on every invocation. The runner checks agents,
lint, TypeScript, the production build and its provenance, commerce/catalog
domain contracts, data ownership, smoke safety, its own cleanup/artifact
contracts, and the full isolated local D1 matrix. It allocates a distinct
namespace and starts an owned process group. Normal completion, test failure,
timeout and handled interruption stop that process tree and verify that its
listener closed. Cleanup removes only its exact stale operation lock after
checking the recorded owner PID. The local database remains ignored.

`scripts/ci_compare.py` executes the separate paired baseline/candidate journeys
against isolated local D1. The immutable baseline comes from the pull request
base, previous push SHA, or explicit manual input. `baseline-summary.json`
contains source identity and changed paths; a source diff is not an A/B PASS.
Executed comparison evidence is recorded separately in
`comparison/comparison.json` and the named `baseline-compare` step.

`ci-summary.json` records schema 1, application SHA, dirty state, exact source
archive digest, test-source/runtime/build identities and each named step's
status, exit and log. A failed prerequisite stops later checks and leaves them
NOT RUN. A dirty local run can test tooling, but it does not establish a clean
committed release candidate; the release monitor must enforce that boundary.

Actions uploads only the runner's explicit `publish/` allowlist: sanitized
summary, baseline identity, per-file source hashes, logs, JUnit, matrix/paired
results, per-test evidence and sanitized failure diagnostics. The artifact index
records each uploaded file's hash. It excludes dependency/build directories,
source ZIP, guest fixture manifests, database files and environment state. Raw
logs/traces stay local; guest capability strings are scrubbed before copying to
the upload directory. Artifacts expire after seven days.

Configure the stable **P0 checks** status in the repository's required branch
rules only after owner approval. YAML alone does not activate a ruleset,
reviewer protection, staging environment, production deployment integration or
workflow entitlement. This workflow performs no deployment and grants no new
third-party access.

On Windows the runner creates each child suspended, assigns it to a
kill-on-close Job Object, then resumes it. This contains descendants even if
the launcher exits. The venv's delegated Python PID must be observed in that
owned job before its fixture lock can be removed. POSIX runners retain their
process group and signal the whole group after leader exit; comparison cleanup
also handles SIGTERM. The real Windows launcher/listener/lock regressions are
executed locally; POSIX/GitHub-hosted execution remains separately unverified.

Paired-side result JSON, screenshots, accessibility snapshots and sanitized
traces are included by an explicit pattern allowlist. The monitor verifies all
twenty side records, trace CRCs and matching outcomes. JSON sanitation changes
bytes: the comparison wrapper retains both the original raw digest and the
published sanitized digest, and the upload index binds the latter files.
