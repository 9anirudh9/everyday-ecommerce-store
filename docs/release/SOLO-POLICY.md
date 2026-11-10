# Solo maintainer policy v1 — LOCAL PROPOSAL

Scope: 9anirudh9/everyday-ecommerce-store, owner 9anirudh9 (User 75884753).
Selecting this proposal authorizes local preparation only. Activation, settings,
commit, push, merge, provisioning, deployment and charges remain unapproved.

The default release policy remains strict. The separate
`config/release-policy.solo-proposal.json` selects `solo-maintainer-v1` and pins
the SHA-256 of this document. Both environments stay disabled. Adoption requires
a reviewed, separately approved source change to the trusted default policy;
there is deliberately no workflow input that switches policy profiles.

## Controls and accepted tradeoff proposed for owner review

Main still requires a pull request, strict up-to-date `P0 checks` pinned to GitHub
Actions App 15368, resolved conversations, administrator enforcement, no review
bypass allowances, no deletion and no force push. Required approvals become zero;
required code-owner and last-push approvals become false. Stale-review dismissal
remains true. CODEOWNERS remains useful routing documentation, not a merge veto.
GitHub PR authors cannot approve their own PR. This profile removes enforced
human approval, code-owner veto and last-pusher separation. An owner may merge
their own passing PR. Independent Watchtower coding review remains required by
the operating procedure; GitHub does not enforce it as a second human reviewer.
The deterministic CI evidence monitor is not a substitute for that review.

Staging and production retain the owner as sole User reviewer and protected
branches only. `prevent_self_review=false` permits the owner to request and then
manually approve the deployment job. This is an explicit manual decision, not
second-person separation. Other protected branches would also be eligible at
the environment layer; the workflow separately requires refs/heads/main.

Administrator environment bypass must still be disabled. The documented REST
schema does not establish that setting; no supported read adapter is implemented.
Missing proof is BLOCKED, even if a UI screenshot exists. Payloads do not invent
`can_admins_bypass`. Synthetic test values are never hosted proof.

## Exact-artifact owner decision

The solo validator reads GitHub review history for the authorization run. Require
owner User ID/login/type as actor, triggering actor and approver; exactly one
approved target environment decision matching its live ID and name. Missing,
rejected, ambiguous or mismatched decisions block. An agent using owner credentials
must never submit this approval. Account identity cannot prove a human operated it.

The owner must personally enter the exact `APPROVE {canonical JSON}` comment
displayed by the workflow's preflight job. It binds environment, operation, full
application SHA, archive SHA-256, CI and staging run IDs, rollback version and
migration digest, authorization run ID/attempt, profile and this document digest.
It is not replaced by a configuration boolean, local report or Watchtower verdict.
Production needs its own decision and fresh passing staging evidence for the same
candidate. The receipt retains reviewer, requester, environment and comment digest;
event consumption re-fetches and verifies the actual GitHub decision.

GitHub's documented history lacks approval timestamps and attempt IDs. Therefore
solo permits initial attempt 1 only; reruns require a new dispatch and decision.
The existing maximum one-hour TTL starts at run creation, including waiting time,
and is never renewed at job startup. Late approval blocks. Provider evidence reads
may fail or be delayed: failure blocks, never fabricates consent.

## Activation roadmap — all remote steps pending separate approval

1. Review local diff, tests, independent Watchtower objections and exact file hashes.
   Review strict/solo alternatives and explicitly accept the lost protections.
2. Prepare a minimal reviewed bootstrap source patch: main currently lacks workflows
   and CODEOWNERS. Obtain separate exact commit/push and PR/main merge approvals.
   No bootstrap merge can claim protection that did not exist. Do not merge the
   entire stale feature branch without review. Run main CI after authorized merge.
3. Review/approve adoption of the solo default policy with the final document hash.
   Verify actual public visibility/entitlement. Public current plans support these
   controls without a paid upgrade; exact account plan remains UNKNOWN.
4. Obtain distinct settings approval for the solo payloads under
   `config/github-protection/solo-maintainer-v1/`. Save before/after readbacks and
   apply main protections after bootstrap. No collaborator invitation is needed.
5. Separately approve environment creation/settings and disable administrator bypass.
   Develop and independently review a supported primary-source bypass read adapter.
   Until verified, release activation remains BLOCKED; do not enable environments.
6. Separately approve staging resources, isolated D1, least-privilege provider bridge
   and any read credential. Verify identities, costs and smoke routing, then review
   a source change enabling only verified environments. No production data writes.
7. Request an exact staging release decision via fresh dispatch; run smoke and
   independent Watchtower review. Deliberately failing smoke must block promotion.
8. Request a distinct exact production decision, then read-only smoke and independent
   Watchtower review after authorized deployment. Separately authorize rollback drill.
   REL-01–10 and P0 remain incomplete until real evidence exists. Stop before P1.

Reversal is a separately approved source/settings change back to strict payloads,
with an independent author/reviewer arrangement first. Stop pending release jobs;
do not casually delete environments or their secrets. Retain sanitized readbacks.
The owner can edit repository policy: admin enforcement does not prevent policy edits.

## Primary sources checked 2026-11-09

- [Protected branches and public-plan availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Branch REST schema and permissions](https://docs.github.com/en/rest/branches/branch-protection)
- [PR author approval restriction](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)
- [Environment reviewer/self-review/bypass behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [Environment REST schema and public-plan availability](https://docs.github.com/en/rest/deployments/environments)
- [Review-history schema: state, comment, user and environments](https://docs.github.com/en/rest/actions/workflow-runs#get-the-review-history-for-a-workflow-run)

Administration write is needed for settings; Administration read for branch metadata
and Actions read for workflow reviews. No new token or permission is authorized.
No paid plan, resources, deployment, external service or usage charges are approved.
