# Owner-controlled hosted activation

All steps below are PLANNED, not executed by the local implementation task.
No approval is inferred from this document or from a configuration boolean.

1. Review the final source archive and exact task branch. Separately approve
   commit/push, any PR/main merge, and any hosted run that consumes plan minutes.
   Check the repository's plan, visibility, Actions entitlement and storage cost;
   local code cannot establish charges or available reviewer protections.
2. Protect `main` with fresh code-owner/last-push reviews and the stable required
   **P0 checks** job. Enforce restrictions on admins; disallow bypass, deletion
   and force pushes. `.github/CODEOWNERS` names the owner. A solo owner cannot
   self-approve their own review when self-review prevention is enabled; arrange
   a separately approved trusted initiator/reviewer rather than weakening gates.
3. Create separate protected GitHub `staging` and `production` environments with
   the owner as the sole User reviewer, self-review prevention, protected-branch-only
   deployments and no administrator bypass. Verify actual metadata/entitlements.
   The current documented REST read omits proof of the bypass setting: resolve
   that supported-read integration and review it before enabling publication.
4. Approve creation of a dedicated staging Worker and D1, including account,
   resource names, budget and retention. Record the real production/staging
   resource and D1 identities and prove they differ. No automatic schema reset
   or hosted seed endpoint is supplied. Migrations/fixtures on hosted staging
   need a separate approved setup and disposable test-data policy.
5. Copy `config/staging.example.json` to ignored `.sites-runtime/staging/input.json`
   and fill verified IDs/URL. With a verified local build, run:

   ```text
   python scripts/staging_config.py --config .sites-runtime/staging/input.json
   ```

   This only renders `.sites-runtime/staging/wrangler.json`. It rejects production
   D1/Worker reuse, removes routes and binds only the separate staging DB. The
   `provisioning_approved` marker is a local configuration prerequisite, not
   permission to create/deploy resources. No credentials belong in either file.
6. Approve a least-privilege provider bridge after reviewing its concrete code,
   identity, repository scopes, data flow and cost. Native Sites-to-GitHub
   publication is currently unintegrated. Do not invent a Sites REST endpoint
   or persist the short-lived source credential. The bridge needs only the
   specific provider publish resource and GitHub Deployments write/Actions read;
   no repository administration write or all-account Cloudflare token.
7. If necessary, separately authorize repository protection metadata read access
   as `RELEASE_PROTECTION_READ_TOKEN`. Its use is restricted to trusted protected
   release/smoke code; PR checks receive no release secret. Missing read access
   blocks validation. Grant no scope before reviewing the exact permissions.
8. After live configuration/bridge proof and independent review, update the
   protected policy with the exact allowlisted origins, resources, D1s and
   bridge identity. Only then enable an environment. Use a successful clean
   main-branch CI artifact; request staging authorization for its exact SHA/hash.
9. After the separately authorized staging publication, invoke reusable smoke
   directly through `needs` or a verified external provider event. Retain the
   passing receipt and isolated staging journey evidence. A failed/unknown run
   blocks production. Test that a deliberately failing smoke holds promotion.
10. Request separate production authorization for the same candidate and fresh
    staging receipt. After the approved publication, require the production
    read-only smoke receipt and independent Watchtower review. Perform an
    authorized rollback drill using the runbook before claiming REL-08 PASS.

No scheduled regression is configured. Any later schedule, paid service,
integration permission or P1 work requires its own owner instruction.
