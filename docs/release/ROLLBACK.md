# Rollback and failed-smoke runbook

Status: locally validated decision rules; hosted rollback NOT RUN.

1. Hold promotion on deployment failure, missing identity, failed/unknown smoke,
   a regression or independent-review BLOCK. Retain sanitized JUnit/results,
   request IDs, trace, target URL, GitHub SHA, provider SHA/version/deployment
   and the exact artifact hash. A build PASS does not override a smoke failure.
2. Select an actual known-good saved provider version from verified release
   records. Obtain its exact source/archive identity and previous smoke evidence.
   The source must remain in protected history and CI artifacts must still be
   available; expired artifacts require fresh verification, not guessed metadata.
3. Review live schema/migration compatibility and backup/recovery availability.
   Migrations 0000/0001 are additive and immutable, but source inspection is not
   proof of hosted schema or backup state. Capture the compatibility review as
   an artifact and SHA-256. Prefer forward repair; never execute a production
   reset, destructive down migration or real customer/payment test.
4. Obtain separate owner approval for rollback to that exact saved version,
   SHA/hash, environment and compatibility-review digest. A prior publish
   approval or failed smoke does not authorize rollback. Use the protected
   authorization request with `operation=rollback`, `rollback_version_id` and
   `migration_review_sha256`; stale approval must be requested again.
5. The separately approved provider operator/bridge deploys only the selected
   saved version and emits its actual metadata. The validator rejects a different
   version, resource, SHA/tree or environment. This repository supplies no
   automatic destructive rollback command or substitute Sites API.
6. Run the same post-deployment smoke immediately against the rollback's new
   deployment ID and existing saved version. A rollback is incomplete until
   that exact URL/SHA has passing smoke and independent review. Failed rollback
   smoke keeps promotion blocked; preserve the incident and decide the next
   exact action with the owner.

Both a failed-smoke rejection and a rollback-version mismatch are executed
local contract tests. They are simulated provider records, not hosted incident
or rollback evidence. Production cart/order writes are excluded from smoke.
