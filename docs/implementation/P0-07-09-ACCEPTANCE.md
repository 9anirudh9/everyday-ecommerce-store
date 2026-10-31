# P0-07–09 acceptance coverage

This maps the roadmap's local foundation requirements to executable checks.
Execution status and exact candidate hashes belong in the ignored run ledger,
`outputs/p0-07-09-completion/EXECUTION_REPORT.md`; this document is a coverage
index, not a claim that an arbitrary checkout passed. Hosted staging, recovery,
automatic CI and deployment approval remain separate gates.

| ID | Implementation and verification |
| --- | --- |
| API-01 | Legacy GET/POST `/api/shop` characterization in `test_read_contract.py` and `test_write_contract.py`. |
| API-02 | All 13 original IDs, rupee/paise prices and images checked; catalog pagination/filter/sort and product reads checked. |
| API-03 | REST add, absolute quantity, PATCH, DELETE, invalid quantity, stale revision and idempotency tests. |
| API-04 | Server-derived coupon preview and legacy coupon application tests; monetary/clock input cannot override pricing. |
| API-05 | Order create/replay/read, unique order IDs and other-guest 404 tests on disposable local D1. |
| API-06 | Shared error DTO, request ID, no-store headers, invalid ID/query, Origin errors and 405 tests. |
| API-07 | Separate guest contexts cannot read another cart/order. |
| API-08 | JSON shape assertions in typed `framework/api.py` and API contract tests. |
| API-09 | Eighteen wrong/missing/null Origin cases across six mutation methods/routes. |
| API-10 | Guest capability absent from JSON; sanitized diagnostic and trace regression; retained artifact scan. |
| DATA-01 | `scripts/test_data.py prepare` applies migrations and seeds one owned worker namespace. |
| DATA-02 | Idempotent seed/reset, namespace locks and active-port checks in `test_data_contracts.py`. |
| DATA-03 | Original 13 records unchanged; scenario IDs 201/202 remain separate from original IDs. |
| DATA-04 | CLI has no remote operation/reset endpoint; ownership/path/storage-redirection checks reject external targets. Browser/API writes require loopback and a valid owned manifest. |
| DATA-05 | Fresh cookie contexts per test; guest isolation API tests. |
| DATA-06 | Deterministic low/out-of-stock and expired-coupon recipes; pure coupon clock injection; existing domain boundary tests. No request-controlled production clock. |
| DATA-07 | Immutable migration ledger; additive migration preserves old cart/order rows in `test_data_contracts.py`. |
| DATA-08 | Distinct namespace databases/guest identities and reset isolation; prior two-worker 68-case xdist execution retained. |
| AUTO-01 | Page/component objects use roles and labels; localized browser journeys exercise them. |
| AUTO-02 | Selective test IDs preserve language and cart hooks; semantic locators remain preferred. |
| AUTO-03 | Fresh guest fixtures; mutation gate verifies each worker's URL, namespace, port and database. |
| AUTO-04 | Home, Catalog, Product, Cart and Checkout objects in `framework/pages.py`. |
| AUTO-05 | API contract cases and local browser cart/checkout journeys share session-bound clients. |
| AUTO-06 | JUnit/HTML, per-case request evidence, screenshots/redacted traces on call/guard/page-error failure; forced teardown regressions verify artifacts. |
| AUTO-07 | smoke/regression/e2e/destructive markers; public matrix accepts smoke only and requires deployment identity. |
| AUTO-08 | Assertions/events replace fixed sleeps; no automatic blind retries. |
| AUTO-09 | English/French × desktop/mobile matrix; selectable Chrome, Firefox and WebKit; browser versions retained. Mobile dimensions are viewport evidence. |
| AUTO-10 | 51 purposeful pytest functions expand to 68 local cases. Standalone guard/data contract checks supplement this suite. |

Supporting sources: `python-playwright/tests/api/`, `python-playwright/tests/e2e/`,
`python-playwright/tests/smoke/`, `scripts/test_smoke_contracts.py`,
`scripts/test_data_contracts.py`, and the retained original P0-07–09 release
evidence. The controlled guard comparison reproduces the old harness failure
and verifies its repair against the same intercepted page; it is not a
randomized customer experiment or a new application deployment.

Remaining hosted increments: protected staging seed/reset and recovery have
not been provisioned or run; no production reset endpoint is introduced.
P0-10 CI, automatic deployment smoke and protected release workflows remain
open. Local evidence cannot close those hosted gates or authorize P1.
