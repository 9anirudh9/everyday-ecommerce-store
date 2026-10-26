# P0-01 navigation/cart-badge slice — browser execution report

Date: 2026-10-26. Scope: the existing local navigation/cart-badge slice only.
The complete P0-01 roadmap and P0 release gate remain open.

## Executed candidate

- Branch: `feature/p0-01-navigation-cart-badge`.
- HEAD: `f860e97c9aa2bf71197ec69dbf98238fbc7137c8` plus uncommitted local changes.
  HEAD alone does not identify the tested source or the live deployment.
- Final test interval: 2026-10-26 15:58:42–16:00:31 UTC.
- Target: `http://127.0.0.1:8787`, locally served production build.
- Python Playwright package: 1.64.0; bundled driver:
  1.64.0-beta-1791568591000; installed Chrome: 155.0.8059.40; headless.
- English/French × 1366×900 desktop / 390×844 mobile layout; desktop Chrome user
  agent at both sizes, not physical mobile devices.
- Source fingerprint: `54ba29f7125a2ca96f310fd7225b1f06e69fbac6988b582eea3366f55469a712`.
- Build fingerprint: `b235d5c391ffafa518c6a7a01480aae409631449ae63c38a80d0f4c61850828a`.
- Test-file SHA-256: `60eeed92a2f1a66d5ac9244f34ec347234ba4d70029eeaafeb37509377a01e3c`.
- Runner confirmed source files remained unchanged during execution.

## Isolation

Every test creates a fresh browser context with service workers blocked. All
browser `/api/**` requests are intercepted before navigation. Only the local
`/api/shop` endpoint and explicit mock operations are accepted; unexpected APIs,
methods and writes abort. Cart state is an independent in-memory fixture for each
test; successful mock mutations survive document navigation within that test.
No cart request falls through to D1. Fixtures use products 43 and 46, quantities
0–10, and fictional checkout details. Card fields are not included in the
checkout API body.

The Worker additionally uses `.sites-runtime/p0-01-browser-d1` as a separate local
storage directory. Existing `.wrangler/state` and production data are outside
the fixture. No package or browser installation was needed. Pytest was unavailable;
the reproducible suite uses Python's standard unittest runner with installed
Playwright, without claiming the separate pytest smoke suite ran.

## Results

**52 executed, 52 PASS, 0 FAIL, 0 errors, 0 skipped.** Each of the following 13
scenarios ran in all four language/viewport combinations.

| Scenario | Status | Evidence established |
| --- | --- | --- |
| Canonical navigation and active state | PASS | Actual navigation, current link semantics and underline; product-detail Shop state; no false active link on Search |
| Quantity sum and navigation/reload | PASS | Quantities 2+3 display 5; mock fixture retained after native navigation and reload |
| Pending load then empty | PASS | No numeric badge before controlled GET release; accessible loading; zero only after success |
| Load failure and retry | PASS | HTTP 503, network abort, malformed JSON, invalid quantity and null item; unavailable label/marker; retry restores count |
| Add/update/remove and failed write | PASS | Exact absolute-quantity POST bodies; shared badge follows successes; failed write preserves count; zero removes |
| Quantity boundaries | PASS | Quantity 10 displays correctly and Increase is disabled; minimum boundary also checked during mutation scenario |
| First-visit language dialog | PASS | Existing dialog test IDs work; selection dismisses dialog and persists after reload |
| Mock checkout clears shared badge | PASS | Fictional delivery/card/review/confirmation; expiry formatting; success clears badge to zero |
| Responsive layout/hit target | PASS | Visible badge, no horizontal document overflow, Cart ≥44×44 CSS pixels, unobscured center and successful click |
| Header keyboard navigation | PASS | Tab order, visible focus outline and Enter activation to Shop |
| Language switch with cart | PASS | Selected language survives reload while quantity remains correct |
| Delayed stale GET after add | PASS | An older response cannot replace a newer successful mutation's count |
| Focus refresh preserves checkout fields | PASS | Held successful read and failed read/retry retain unsaved delivery and card form values |

Unexpected console/page errors: **0** in the observed tests. Deliberately induced
All 16 deliberately induced failed-resource diagnostics are retained separately and matched one-for-one to
the mocked request's URL, failure kind and exact browser message. The browser
console API does not expose an exact request ID, so this is a bounded match by
URL, kind and count; any extra or missing diagnostic fails the case.

| Supporting check | Status | Limit |
| --- | --- | --- |
| Production build | PASS | Direct package script entry point; `pnpm` is not on PATH |
| TypeScript | PASS | `tsc --noEmit --incremental false` |
| Scoped ESLint | PASS | 0 errors, 4 existing image warnings |
| Working-tree whitespace check | PASS | `git diff --check`; Git also reports line-ending conversion notices |
| Independent Watchtower review | PASS, bounded browser scope | Round 2 verified 52/52 results, source/build/test hashes, 52 artifact sets and 16 deliberate diagnostics; full P0-01/release remains BLOCKED. |
| Canonical repository-wide lint | NOT RUN | Not rerun here; earlier audit failure is not cleared by scoped lint |
| Controlled original baseline A vs candidate B | NOT RUN | The initial diagnostic is not baseline A; comparison remains INCONCLUSIVE |
| Real API/D1/cart-cookie/session E2E | NOT RUN | Mock tests do not establish backend persistence or session isolation |
| Production/staging post-deployment smoke | NOT RUN | No deployment was performed |
| Complete P0-01 / P0 release | BLOCKED | Remaining roadmap implementation and full acceptance/release evidence are outstanding |

## Defects found and repaired

The initial 40-test diagnostic had 28 passes and 12 failures. Eight failures
exposed two application defects, each reproduced at all four configurations:

1. Cart had `aria-current` but lacked the visible active indicator. Added the
   corresponding Cart styling in `app/globals.css`.
2. A delayed pre-mutation GET could overwrite the updated count. Added a request
   version counter in `app/cart-provider.tsx` so newer reads, successful mutations
   and lifecycle cleanup invalidate superseded responses.

The other four failures were the test harness incorrectly classifying an
intentionally failed POST's 503 diagnostic after its failure flag had been reset.
The harness now matches each deliberate failure to a single observed diagnostic.

Watchtower's first independent review then found that background refreshes
unmounted checkout forms. A focused four-case diagnostic reproduced unsaved
delivery-field loss in all language/viewport combinations. The cart provider now
remembers whether a first successful load occurred; subsequent refreshes can
show a pending or unavailable badge while keeping forms mounted. On background
failure the page marks displayed items as potentially outdated, shows a retry,
and prevents cart/order writes until recovery. The focused repair run passed 4/4.
The final browser test directly checks the unsaved delivery name and cardholder
name through refresh and retry; every individual field was not asserted.

The final suite added first-visit-dialog, mock-checkout and focus-refresh
scenarios and passed all 52 cases. No blind retries were used.

## Evidence and reproduction

- [Machine-readable final results](../outputs/p0-01-browser/candidate-2/results.json)
- [JUnit](../outputs/p0-01-browser/candidate-2/junit.xml)
- [Full final runner output](../outputs/p0-01-browser/candidate-2.log)
- [Initial diagnostic results](../outputs/p0-01-browser/initial/results.json)
- [Focused form-loss diagnostic](../outputs/p0-01-browser/focus-diagnostic/results.json)
- [Focused repair run](../outputs/p0-01-browser/focus-repair/results.json)
- [Final candidate build output](../outputs/p0-01-browser/candidate-2-build.log)
- Per-test `page.png`, `accessibility.txt`, `evidence.json`, and `trace.zip` live
  under each test directory in `outputs/p0-01-browser/candidate-2/`.
- [Runner and assertions](tests/regression/test_p0_navigation.py)
- [Local launch and test commands](README.md#local-p0-01-browser-regression)

Artifacts are local and ignored by Git. Browser verification is now executable
without installing dependencies or using a shared database. Mocks prove client
behavior under the supplied API contract; they do not verify the real API.

NAV-01/02/04/06/07/08 have evidence only for the routes/controls in this slice.
NAV-03 has mock-backed browser evidence. Custom 404/return navigation (NAV-05),
hamburger menu and its focus restoration, remaining roadmap increments, full
accessibility audit and baseline visual comparison remain open. Do not mark the
whole P0-01 task or its increments complete from this report.

No commit, push, PR, deployment, third-party authorization or production writes
were performed. Estimated/actual model usage and monetary cost: UNKNOWN.
