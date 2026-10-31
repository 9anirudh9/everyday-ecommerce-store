# Everyday Shop — Agent-First Implementation & Quality-Gated Delivery Specification

**Version:** 1.0 (draft for owner approval)  
**Prepared:** 2026-10-26 (Asia/Kolkata)  
**Repository:** `9anirudh9/everyday-ecommerce-store` — https://github.com/9anirudh9/everyday-ecommerce-store  
**Live baseline:** https://everyday-shop-anirudh.cidirianirudh.chatgpt.site/  
**Application stack confirmed from repository:** React 19 + TypeScript, Vinext/Next-compatible routing, Cloudflare Workers, Cloudflare D1, Drizzle migrations, pnpm; **test stack to introduce:** Python + Playwright + pytest.  
**Owner:** project owner (final approver)  
**Decision status:** implementation blueprint and agent prompt pack prepared locally; **no repository files changed or pushed; no deployments performed.**

> **Prime directive:** Build and verify the agents first. Baseline-test all existing behavior. Implement every P0 workstream in dependency order without silently dropping an item. Stop at the P0→P1 approval gate and request the owner's decision. **Never push, merge, deploy, install/authorize an external application, request a paid service, or change production data before explicit owner approval of that specific action.** Local source edits and test work may be prepared for review; they are not permission to publish.

## 1. Scope, reality check, and project states

### 1.1 What was actually inspected (not assumed)

Read-only inspection of the repository README, tree, `package.json`, `app/shop.tsx`, `app/site-frame.tsx`, `app/search-form.tsx`, `app/search/page.tsx`, `app/api/shop/route.ts`, `app/language-provider.tsx`, `lib/products.ts`, `lib/search.ts`, `lib/shop-session.ts`, and the current D1 SQL migration; also loaded the public homepage's HTML text.

| Existing capability | Evidence in current source | Decision |
|---|---|---|
| 13 seeded products, stable existing IDs, Home/Accessories categories | `lib/products.ts` | Preserve IDs, names and current prices; extend catalog safely |
| Search suggestions and `/search?q=...` results, clear link and empty state | `app/search-form.tsx`, `lib/search.ts`, `app/shop.tsx` | Write characterization tests first; enhance filtering, sorting, accessibility |
| Cart GET/update/remove, quantities 1–10, persisted guest cart in D1 | `app/shop.tsx`, `app/api/shop/route.ts`, `lib/shop-session.ts` | Test before refactoring; add counters, line calculations, reliability |
| `EVERYDAY` 50% coupon and client-side persistence | `app/shop.tsx`; recalculated in server checkout | Keep compatibility; introduce server-side coupon policy and API |
| Three-step demo checkout, payment method UI and saved order | `app/shop.tsx`; `/api/shop` and D1 `orders` table | Preserve simulated payment only; improve validation, resilience, idempotency |
| English/French first-visit dialog and persistent cookie | `app/language-provider.tsx`, README | Preserve `language-english`, `language-french`, `language-switcher` test IDs |
| Current API surface | Primarily combined `GET/POST /api/shop` | Introduce REST-style endpoints gradually; keep old route until clients migrated |
| One large storefront component | `app/shop.tsx` (~20 KB) | Decompose without changing baseline behavior |
| Dedicated Python test suite / agent pack / deployment smoke workflow | Not found in inspected repository tree | New artifacts to implement; absence not proof of all external CI configuration |

**Unverified:** complete browser interaction flows, D1 staging access, current production build SHA, CI/deployment settings, error rates, admin permissions, and feasibility of local D1 in this execution environment. No successful smoke suite or agent execution is claimed in this document.

### 1.2 Meaning of statuses

- `PLANNED`: documented only; no claim of implementation.
- `DRAFTED_LOCAL`: working files exist locally, not published.
- `STATIC_VALIDATED`: structural/syntax checks passed; does **not** mean deployed or end-to-end tested.
- `EXECUTED`: automated test ran in a real controlled environment and report is attached.
- `READY_FOR_APPROVAL`: evidence complete, await owner.
- `APPROVED_TO_PUSH`: owner approved the specified branch/commit content and destination.
- `PUSHED`: push proven by remote SHA.
- `DEPLOYED`: environment URL and deployment SHA recorded.
- `POST_DEPLOY_SMOKE_PASS`: mandatory smoke passed against that deployment SHA/URL.
- `BLOCKED`: dependency, access, permission, failure, or missing owner approval.

**Current delivery status:** repository/source audit `EXECUTED` (read-only); this roadmap `DRAFTED_LOCAL`; agent definitions are supplied in the optional local pack and can be static-validated; runtime agent invocation and browser smoke `PLANNED/BLOCKED` pending an approved execution environment. P0 features remain `PLANNED`, regardless of whether partial functionality exists today.

### 1.3 Definition of P0 / P1 / P2

- **P0:** agents, approvals/release gates, baseline A/B comparison harness, homepage/navigation, catalog/search/filter/sort, product detail, guest cart, coupons, guest checkout, REST testing surface, deterministic data, stable hooks, Python Playwright suite, and smoke-on-every-deployment infrastructure. All P0 acceptance cases must be accounted for, including non-happy paths.
- **P1 (requires a fresh approval after P0):** customer authentication, order history/invoices, wishlist/reviews, enhanced localization, Automation Lab, dedicated failure scenario UI, and expanded accessibility/mobile work. P0 creates interfaces for eventual P1 integration but must not implement it pre-approval.
- **P2:** admin inventory dashboard, advanced payments simulation, multi-tab/conflict analytics, expanded AI-agent workflows, and further performance/scale exercises, if not already required as a P0 reliability acceptance case.
- **Compatibility rule:** features which already exist are **characterized, stabilized, and extended**, not rewritten merely for a cleaner architecture.

## 2. Mandatory execution sequence and change authority

```text
SOURCE AUDIT -> AGENT DEFINITIONS -> AGENT STATIC CHECK -> AGENT RUNTIME CHECK
    -> SNAPSHOT BASELINE A -> P0 CONTRACTS/DESIGN -> IMPLEMENT ONE P0 SLICE LOCALLY
    -> UNIT/API/PLAYWRIGHT TESTS -> COMPARE A VS B -> INDEPENDENT MONITOR REVIEW
    -> OWNER PUSH APPROVAL -> PUSH APPROVED CHANGE -> CI CHECKS
    -> OWNER DEPLOY APPROVAL -> STAGING DEPLOY -> AUTOMATIC STAGING SMOKE
    -> OWNER PRODUCTION APPROVAL -> PRODUCTION DEPLOY -> PRODUCTION READ-ONLY SMOKE
    -> RECORD RELEASE / ROLLBACK IF NEEDED -> NEXT P0 SLICE
    -> P0 FINAL AUDIT -> STOP AND ASK OWNER WHETHER TO START P1
```

**No blanket approval:** An approval for one push is not approval for later pushes, merges, production deployment, third-party permissions, or P1. If the owner only approves testing, stay read-only. If CI cannot be configured to run after deployment, **block deployment** rather than silently skipping smoke.

### 2.1 Exact owner approval format

Before a push, present:

```text
APPROVAL REQUEST — PUSH
Repository: 9anirudh9/everyday-ecommerce-store
Branch: feature/p0-<id>-<slug> (no direct push to main)
Change ID: P0-XX
Summary and files changed: ...
Local patch / commit SHA or archive checksum: ...
Tests run + pass/fail/skipped counts: ...
A-vs-B comparison: ...
Open defects / risk rating: ...
Third-party permissions or costs: none / details
Requested action: push only (not merge or deploy)
Please respond: APPROVE PUSH P0-XX [SHA] / REJECT / REQUEST CHANGES.
```

Likewise use separate `APPROVE STAGING DEPLOY [SHA]`, `APPROVE PRODUCTION DEPLOY [SHA]`, `APPROVE THIRD-PARTY [provider/scope]`, and `APPROVE P1 START`. Approval must match the specified target and artifact; any material revision invalidates a prior approval. Preserve approval evidence in the release log.

### 2.2 Quality gates on each slice

1. `lint`, TypeScript typecheck, build, and affected unit tests pass (as applicable).
2. Python smoke/regression relevant to the slice passes against candidate B.
3. Baseline contract tests run against A (or their original known failure is recorded), with side-by-side results.
4. No new unapproved external services, production writes, real payments, or leaked secrets.
5. `@WATCHTOWER` independently checks evidence and records PASS/BLOCK with reason.
6. Owner explicitly approves push; later approvals are required for staging and production deployment.
7. After **every** staging or production deployment, trigger smoke tied to deployed URL + commit SHA; no `smoke = unknown` release qualifies as done.
8. If candidate or post-deployment smoke fails, stop promotion, capture trace/report, file defect and roll back or hold release per environment policy.

## 3. Agent-first design: names, responsibilities, invocation, and validation

The agent prompts in the companion agent pack are **vendor-neutral role specifications**, not a claim that live cloud agents were created. They can be supplied to a coding-agent product after owner approval of its integration. Each invocation must have a bounded input, explicit output, and failure verdict.

| Call name | Role | Responsibilities and outputs | Permission boundary |
|---|---|---|---|
| `@CONDUCTOR` | Orchestration and cost governor | Build task graph, delegate smallest viable task, select model tier, maintain progress ledger | Cannot self-approve or publish |
| `@ATLAS` | Business Architect | User stories, rules, testable Gherkin acceptance, baseline comparison, dependency/risk decisions | No code merges |
| `@FORGE` | Lead Developer | Architecture decisions, typed contracts, clean implementation, migration, local evidence | Local code only until push approval |
| `@PROBE` | Baseline/A-B Test Analyst | Capture baseline A, candidate B, functional/visual/API diffs, attribution and known defects | Read-only prod; writes only disposable test state |
| `@SPEC` | Python Playwright QA Lead | Pytest fixtures/POM/API tests, coverage matrix, traces, regression evidence | Test changes local only until approved |
| `@SMOKE` | Deployment Smoke Guardian | Bind test to environment URL + deployed SHA, run smoke suite after every release, report verdict | Cannot promote a failed build |
| `@WATCHTOWER` | Independent Work Monitor | Audit **every transition** against task acceptance, tests, artifacts, cost, permissions and blockers | Must not mark own work as independently verified |
| `@PERMIT` | Approval and Third-Party Access Steward | Determine approvals, prepare exact setup steps, least-privilege scopes, keep approval ledger | Never grant its own approvals |

**Recommended command convention:** `@CONDUCTOR plan P0-02`, `@ATLAS specify P0-02`, `@FORGE implement P0-02 locally`, `@PROBE compare P0-02`, `@SPEC test P0-02`, `@WATCHTOWER audit P0-02`, `@PERMIT approval-check P0-02`, `@SMOKE verify deployment <SHA> <URL>`.

### 3.1 Per-step monitoring contract (`@WATCHTOWER`)

For *every* task/subtask, store a short record (`evidence/<id>.md`):

```yaml
step_id: P0-02.03
owner_agent: FORGE
baseline_ref: <baseline branch/SHA/evidence>
candidate_ref: <local patch/SHA>
acceptance: [criteria IDs]
tests: [{name: ..., status: PASS|FAIL|SKIP, artifact: ...}]
ab_result: PASS|FAIL|INCONCLUSIVE
security_review: PASS|FAIL|NOT_APPLICABLE
external_approval: NOT_NEEDED|PENDING|APPROVED
owner_push_approval: PENDING|APPROVED
smoke_status: NOT_DEPLOYED|PASS|FAIL
estimated_tokens: <integer>
actual_tokens: <integer or UNKNOWN>
defects: [ticket IDs]
monitor_verdict: PASS|BLOCK|NEEDS_EVIDENCE
next_action: <one concrete step>
```

Monitor fail-closed rules: a blank report is `NEEDS_EVIDENCE`; unknown agent execution is **not PASS**; source-code inspection is **not E2E execution**; a production smoke suite that writes orders is a defect; a changed SHA without renewed comparison is BLOCK; any unsanctioned third-party request or push is BLOCK. Invoke monitor via workflow step or explicit agent call, not imaginary always-on background activity.

### 3.2 Prove agents work before P0 code

- [ ] `AG-01`: agent manifest includes all eight unique call names, correct role, required input/output, disallowed actions, escalation route.
- [ ] `AG-02`: static checker validates all agent file paths, required sections, exact call names, and the invariant `no push without approval`.
- [ ] `AG-03`: dry-run a fictional task `P0-DRYRUN`; `@ATLAS` writes a 3-criterion story, `@FORGE` proposes a file-level plan, `@SPEC` creates a test matrix, `@PROBE` returns `INCONCLUSIVE` without execution data, and `@WATCHTOWER` correctly blocks unsupported PASS.
- [ ] `AG-04`: negative test: tell `@FORGE` to push without approval; agent must refuse that side effect and prepare an approval request instead.
- [ ] `AG-05`: negative test: missing third-party permission; `@PERMIT` must give ordered manual steps and block execution.
- [ ] `AG-06`: negative test: candidate smoke FAIL; `@SMOKE` must prevent promotion and provide triage/rollback steps.
- [ ] `AG-07`: validate cost routing and escalation rules against one easy, one medium and one security-sensitive task.
- [ ] `AG-08`: attach actual prompts, responses and checker output; **only then** mark agent runtime `EXECUTED`.

**Failure handling:** one repair attempt with exact failure context; escalate to reasoning model or human on second failure; never loop agents indefinitely.

## 4. Architecture blueprint (business architect + lead developer)

### 4.1 Preserve current stack, separate concerns

Do **not** replace Vinext/Cloudflare D1 with Python/FastAPI just to learn Python Playwright. Python is the test automation language; TypeScript remains the application language.

```text
Browser React pages + accessible components (app/, components/)
  -> typed client API adapter (lib/api-client/)
  -> route handlers /api/* (app/api/)
  -> application services (lib/services/): Catalog, Cart, Coupon, Checkout
  -> domain rules (lib/domain/): Money, Product, Cart, Pricing, CouponStrategy
  -> repository interfaces (lib/repositories/)
  -> D1 adapter with Drizzle/parameterized SQL (lib/infrastructure/d1/)
  -> D1 migrations and isolated seed data (drizzle/, scripts/)

Python test repository or /automation/python-playwright/
  -> pytest fixtures + config -> Page Objects / Component Objects
  -> API clients -> smoke/contract/regression/E2E suites -> traces/reports
```

Use these patterns intentionally:

- **Page Object + component objects:** Python Playwright pages (Home, Catalog, Product, Cart, Checkout), independent locators/assertions; tests retain business assertions rather than burying them inside page objects.
- **Repository pattern:** D1-specific persistence behind a narrow interface; transaction/idempotency concerns centralized.
- **Service layer:** cart updates, price totals, order placement and data access are not buried in JSX or route handlers.
- **Strategy/policy:** coupons and optional sort rules as explicit, testable functions; avoid nested UI conditions.
- **DTO + schema validation:** Zod or an existing validated schema tool, shared types and normalized error codes/statuses.
- **State-machine idea:** checkout step transition rules (`delivery -> payment -> review -> confirmed/failed`) with legal transitions tested.
- **Dependency injection at boundaries:** enable mocks/fakes in tests without introducing a heavyweight DI framework.
- **Feature flags / branch-by-abstraction:** keep A-compatible route and UI until B passes comparison, then remove temporary adapters in separate approved changes.
- **Financial correctness:** integer paise in API/storage, explicit rounding, inclusive tax/free shipping policy; keep existing INR visible prices the same.

### 4.2 ADRs and release invariants

Create `docs/adr/` with ADR-001 stack preservation, ADR-002 test-data isolation, ADR-003 coupon/pricing, ADR-004 smoke trigger, ADR-005 deployment approvals. Preserve `__Host-everyday-guest` session compatibility; preserve language cookie/test IDs and existing product IDs; ensure D1 migrations are additive and backed up. No real payment credentials, no actual financial transaction, and no production reset endpoints.

### 4.3 Working directories (proposed; not yet present)

```text
.agents/ or agents/              # agent specifications, manifest, monitoring templates
docs/implementation/            # this roadmap, stories, evidence ledger, ADRs
lib/domain/                      # entities, money and validation rules
lib/services/                    # business use cases
lib/repositories/                # persistence ports
lib/infrastructure/d1/          # persistence implementation
app/api/products/               # API endpoints
app/api/cart/                   # API endpoints
app/api/coupons/validate/        # server-side coupon policy
app/api/orders/                  # order APIs
scripts/test-data/              # local/CI-only seed and reset
python-playwright/pages/        # page/component objects
python-playwright/tests/smoke/  # per-deployment, side-effect-free
python-playwright/tests/api/    # API and contract
python-playwright/tests/e2e/    # disposable-data checkout
python-playwright/tests/regression/
.github/workflows/              # CI + post-deployment smoke once approved
```

## 5. A-vs-B verification: existing behavior against each implementation

**Two meanings must not be confused:**

1. **Mandatory A-vs-B regression comparison** (what this project always needs): A = untouched main/live baseline or pinned baseline deployment, B = staging candidate of the same feature. Run the **same** test contract and compare screenshots, results, API contracts and business outcomes. No randomized public traffic is required.
2. **Optional true A/B experiment:** random assignment of real users to feature variants with predeclared conversion/UX metrics, privacy and exposure controls. **Do not start** without explicit owner approval, traffic suitability, privacy review and enough users for meaningful results.

### 5.1 Baseline A capture before the first P0 change

- [ ] Record actual baseline commit SHA, deployment ID, URL, captured date/time, browser versions, language, viewport and DB fixture used.
- [ ] Record homepage/navigation, 13 product listing, search suggestions, search results, product `46`, cart, coupon, checkout, language switch, invalid product and error/retry surfaces.
- [ ] Capture DOM/accessibility snapshots, optional masked screenshots, console exceptions, failed requests, key HTTP response codes and trace recordings. Never publish real user data.
- [ ] Use read-only health/navigation smoke on public production; use isolated staging/test D1 for cart/order writes.
- [ ] Before refactor, create **characterization tests** for behavior already known in source, plus mark still-unverified cases as `UNKNOWN`.

### 5.2 Candidate B verification for each slice

| Comparison dimension | Pass condition |
|---|---|
| Routes, labels, localization | Expected navigation and accessible labels preserved or approved intentional change |
| Product catalog | Existing IDs, prices, categories and image links remain stable unless approved |
| Cart | Same seeded inputs yield correct items/qty/totals; state persists across refresh |
| Coupon | Existing EVERYDAY discount unchanged unless contract explicitly approved |
| Checkout | Simulated order flows continue working; no real payment or sensitive capture |
| Backend | Existing `/api/shop` contract remains until deprecation migration approved; new endpoints pass schema tests |
| Visual | No unintended breakage on desktop/mobile; intentional differences documented |
| Performance/safety | No new console exceptions, avoidable request failures, sensitive data logs, or blocked navigation |

Result categories: `PASS` (both correct and intended delta), `REGRESSION` (new failure), `BASELINE_DEFECT` (fails in A and B), `INTENTIONAL_CHANGE` (approved), `INCONCLUSIVE` (cannot execute or compare). `INCONCLUSIVE` blocks release of affected flow.

### 5.3 Evidence folder convention

`artifacts/<release-id>/<environment>/<browser>/{junit.xml,trace.zip,console.json,network.json,screenshots/,ab-comparison.md,smoke-result.json}`. Mask or omit secrets, personal data and payment form values. Retain test evidence for a documented period and avoid uncontrolled public artifact upload.

## 6. Mandatory smoke on every deployment

### 6.1 Smoke packs and safety

**Read-only public production smoke** (2–5 minutes target, **not a guaranteed runtime**): homepage returns, logo/navigation links, `/products` displays known `Plant Pot`, `/products/46` shows ₹1,499, `/search?q=plant` returns expected results, `/accessories` accessible, `/cart` accessible, language dialog/switch works in isolated fresh browser, no uncaught page exceptions. Do not modify the shared public database.

**Write-enabled staging smoke** (disposable D1/test user): all above **plus** add Plant Pot, adjust qty 1→2, apply EVERYDAY, validate ₹2,998 subtotal and ₹1,499 total, complete demo order with synthetic contact/address, verify order ID and cart clearing, test invalid coupon, and tear down isolated data. Use known test fixtures rather than assumptions about live database state.

**API smoke** (staging): health endpoint, GET products, GET product 46, guest cart access, coupon validate, order create+read, API wrong-input 400, and no ability to invoke `/api/test/reset` in production.

### 6.2 Trigger and gating

- Run PR smoke against ephemeral candidate preview where available; **post-deployment** smoke remains separately mandatory.
- Configure GitHub Actions `deployment_status` `success` event, or trusted Cloudflare deployment webhook / CI deployment job `needs: deploy`, passing immutable deployed URL and SHA. Cover **manual deployments too**, not just GitHub-triggered ones.
- Run smoke immediately after staging deployment and after production deployment; set release status PASS only when run ID, SHA, URL, time and report exist.
- **Fail closed** if post-deployment trigger did not run, report is missing, host mismatches expected environment, test timed out, or assertions fail.
- On failure: halt promotion, notify owner with the first failure and trace, open defect; roll back to previous known-good release only under approved rollback policy, then rerun smoke on the restored URL/SHA.
- Recommended CI gates: unique `lint`, `typecheck`, `build`, `unit`, `api-contract`, `playwright-smoke`, `watchtower-audit`; main protected with required PR review and status checks. GitHub environment protection capabilities vary by account/repository visibility; check actual entitlements before relying on manual environment reviewer gates.

**Suggested commands (paths after framework is created):**

```bash
# Application checks; these may need scripts added/adjusted after audit
pnpm lint
pnpm exec tsc --noEmit
pnpm build

# Python smoke for a URL under owner-authorized testing
cd python-playwright
python -m pytest tests/smoke -m smoke --base-url "$TARGET_URL" --junitxml=reports/smoke.xml --tracing=retain-on-failure

# Isolated B verification; A must be run with the matching baseline configuration
python -m pytest tests/regression -m 'not destructive' --base-url "$CANDIDATE_URL"
```

These are target commands, not claims they pass in the existing project.

## 7. Full P0 implementation backlog — business architecture + lead development

**Execution rule for every item below:** `@ATLAS` writes an acceptance contract; `@FORGE` prepares the smallest backward-compatible local patch and tests; `@SPEC` owns test evidence; `@PROBE` compares A to B; `@WATCHTOWER` signs independent evidence; `@PERMIT` checks approvals; `@CONDUCTOR` advances the ledger. All unchecked items remain open, even if current code partially implements them. Where P0 depends on a P1 feature, explicitly preserve its contract and mark the dependent behavior for the P1 gate—never report it silently complete.

### P0-01 — Homepage, navigation, layout and user orientation

**Business Architect (`@ATLAS`)**
- Objective: shoppers can discover products and orient themselves from any supported route, across desktop and mobile, without losing the cart or selected language.
- User journeys: landing → Shop; landing → Accessories; product → breadcrumbs → catalog; invalid route → 404 → Home; mobile menu → any route.
- Rules: logo always goes Home; navigation text conveys active state; cart counter represents total quantity, not number of distinct SKUs; announcements must not obscure content; language selection persists; all controls work with keyboard.
- Acceptance: `NAV-01` all canonical routes and logo work; `NAV-02` active page announced visually/accessibly; `NAV-03` cart badge equals sum of quantities; `NAV-04` product breadcrumbs work; `NAV-05` unknown routes show accessible 404 + return action; `NAV-06` mobile menu and language switch work on viewport 390×844; `NAV-07` keyboard access and focus visibility; `NAV-08` no hydration/console errors.

**Lead Developer (`@FORGE`)**
- Patterns: shared app shell, state selector for cart badge, accessible navigation component, error boundary + not-found route.
- Primary touchpoints: `app/site-frame.tsx`, `app/layout.tsx`, `app/globals.css`; new shared `components/navigation/` and `app/not-found.tsx` as appropriate.
- Increment 1: [ ] preserve logo/Home/Shop/Accessories/Cart links; [ ] active nav indicator and `aria-current`; [ ] cart item count; [ ] breadcrumbs; [ ] custom 404; [ ] keyboard tests.
- Increment 2: [ ] sticky header; [ ] responsive hamburger menu; [ ] badge feedback when cart changes; [ ] persisted language preference; [ ] dismissible announcement saved to session/cookie; [ ] helpful error recovery link.
- Increment 3: [ ] demo Help opens new tab with `rel="noopener noreferrer"`; [ ] skeleton for intentionally delayed page in test mode; [ ] test-only maintenance state; [ ] correct `aria-expanded`/focus restoration; [ ] mobile and French-long-text layouts.
- A/B guard: preserve existing navigation target paths and first-visit language dialog IDs; compare top-level layout and accessible tree.
- Tests: `test_nav_routes`, `test_nav_active`, `test_cart_badge`, `test_invalid_route`, `test_mobile_navigation`, `test_language_persist`, `test_nav_keyboard`.
- Done when: NAV-01…NAV-08 PASS in candidate B, existing baseline navigation remains functional, with screenshots at desktop and mobile widths.

### P0-02 — Product catalog, search, combined filters, sorting and pagination

**Business Architect (`@ATLAS`)**
- Objective: deterministic product discovery with clear feedback and shareable results.
- Business rules: search is case-insensitive, whitespace-trimmed, works with localized names; filters combine with **AND**; sorting is stable on ties (`id` secondary); result count must equal filtered item count, not current page size; valid price boundaries are inclusive; pagination does not change filtered dataset.
- Acceptance: `CAT-01` 13 original products/IDs/prices unchanged; `CAT-02` query `plant`/`PLANT` equivalent; `CAT-03` unknown text displays accessible empty state; `CAT-04` filters + sort compose; `CAT-05` URL reflects criteria and survives refresh/back; `CAT-06` available-only excludes stock 0; `CAT-07` pagination includes partial last page; `CAT-08` loading/error/retry work; `CAT-09` accessible suggestions and keyboard interactions; `CAT-10` expanded catalog does not break baseline product detail IDs.

**Lead Developer (`@FORGE`)**
- Patterns: query-object filter model, pure selector functions, stable comparator strategy, controlled search input/debounce, REST catalog read model; preserve `lib/search.ts` behavior with characterization tests.
- Touchpoints: `lib/products.ts`, `lib/search.ts`, `app/search-form.tsx`, `app/shop.tsx`, `/products`, `/search`, `/api/products`.
- Increment 1: [ ] confirm current live search and clear/empty cases; [ ] visible result count; [ ] Home/Accessories filter; [ ] ascending and descending price sort; [ ] clear/reset controls; [ ] deterministic order.
- Increment 2: [ ] retain and keyboard-harden autocomplete; [ ] price range; [ ] in-stock; [ ] combined filters; [ ] query-string synchronization; [ ] add ~30 seeded products; [ ] loading/error/empty states; [ ] debounce suggestions and cancel stale work.
- Increment 3: [ ] grow to 40–50 seeded products; [ ] paginate in groups of 10; [ ] Previous/Next/pages; [ ] preserve current filter on back navigation; [ ] API 500/timeout retry; [ ] page out of range; [ ] partial last page; [ ] eventually rating filtering using seeded rating metadata (actual user reviews remain P1).
- Design decision: write product filtering in a testable service that works without React, and preferably can run on API side once expanded. Use URL search params as single source of truth for shareable filters.
- A/B guard: all old searches and suggestion links still lead to expected existing products; no arbitrary price/name changes.
- Tests: query matrix `plant`, `PLANT`, `'  plant  '`, `notarealproduct`; filter AND semantics, zero items, sort monotonic + tie stability, direct query-string reload, pagination first/middle/last, invalid range, API failure & recovery.
- Done: CAT-01…CAT-10 PASS and no unapproved behavioral regressions.

### P0-03 — Product details, quantity, availability and media

**Business Architect (`@ATLAS`)**
- Objective: a user can inspect a valid product, choose a valid quantity/variant and add the intended amount to the cart with feedback.
- Rules: quantity integer, minimum 1, maximum min(10, available stock); zero-stock products cannot be purchased; product not found is informative and safe; submitted selection must match cart line item; genuine stock errors have visible recovery.
- Acceptance: `PDP-01` existing ID 46 name, category, ₹1,499 unchanged; `PDP-02` quantity control validates boundaries; `PDP-03` cart reflects selected qty; `PDP-04` out-of-stock disabled; `PDP-05` missing/deleted ID safe; `PDP-06` gallery swaps photos and has fallback; `PDP-07` server rejects stale/over-stock quantities; `PDP-08` keyboard gallery; `PDP-09` related items lead to correct IDs.

**Lead Developer (`@FORGE`)**
- Patterns: `ProductDetail` view + `QuantitySelector` component, selected-variant value object, stock policy shared by UI and server, media-state fallback.
- Increment 1: [ ] product metadata/price/description; [ ] quantity selector 1–10; [ ] Add-to-Cart toast; [ ] View Cart / Back / breadcrumb; [ ] invalid product handling.
- Increment 2: [ ] image thumbnails and main image; [ ] zoom; [ ] stock count; [ ] out-of-stock state; [ ] meaningful color/size variants for suitable **new** products; [ ] related items.
- Increment 3: [ ] stale price warning; [ ] stock changed before add-to-cart; [ ] broken image fallback; [ ] keyboard-operated gallery; [ ] deleted/unavailable product recovery.
- Future P1 dependency: [ ] provide `WishlistButton` extension point; **do not** implement wishlist persistence until P1 is approved.
- A/B guard: existing `products/46` and all legacy IDs stay correct.
- Tests: detail fields, increment/decrement boundaries, invalid ID, gallery, stale stock, broken image, disabled actions, related navigation.
- Done: PDP-01…PDP-09 PASS plus source API contract tested.

### P0-04 — Guest cart, math, persistence and recovery

**Business Architect (`@ATLAS`)**
- Objective: shopper maintains a consistent, accurate guest cart from discovery through checkout.
- Rules: one line per product/variant, quantity 1–10 bounded by stock, remove qty 0, no negative totals; displayed line total = unit price × qty; subtotal is sum of line totals, tax included and delivery free; updating in one view eventually reconciles every visible badge/summary.
- Acceptance: `CART-01` add/update/remove and line totals correct; `CART-02` guest D1 cart persists reload/navigation; `CART-03` duplicate add merges; `CART-04` clear cart confirmation and empty state; `CART-05` one bad request leaves UI consistent and displays retry; `CART-06` cross-tab reconciliation or clear stale-data warning; `CART-07` backend revalidates amount; `CART-08` no unintended duplicate update on repeated click; `CART-09` no sensitive session-token leakage.

**Lead Developer (`@FORGE`)**
- Patterns: `CartService` use cases with repository adapter; optimistic update only with rollback/refetch; immutable cart state; money utility in paise; domain invariant tests.
- Increment 1: [ ] characterize existing `/api/shop` GET/POST behavior; [ ] cart line name/image/price/qty/total; [ ] quantity plus/minus; [ ] remove; [ ] empty cart; [ ] live subtotal; [ ] continue shopping/checkout.
- Increment 2: [ ] persistence; [ ] duplicate merge; [ ] max stock; [ ] clear confirmation; [ ] undo-remove within short accessible toast window; [ ] show discount and subtotal separately; [ ] refetch on session state change.
- Increment 3: [ ] product becomes out-of-stock after add; [ ] price changed notice; [ ] two-tab state reconciliation; [ ] network write failed/retry; [ ] rapid-click concurrency guard; [ ] idempotent update semantics; [ ] simulate failure in disposable staging.
- Future P1 dependency: [ ] define guest-to-authenticated merge **policy** now; implement authenticated merging only with P1 auth approval.
- A/B guard: persistent guest sessions must retain existing cookie behavior; no accidental cart reset on upgrade.
- Tests: exact Plant Pot qty 2 subtotal ₹2,998, update from distinct page, cart reload, remove, two tabs, 503 retry, negative/over-limit HTTP body, no duplicate lines.
- Done: CART-01…CART-09 PASS in staging with isolated guest cookies.

### P0-05 — Coupon rules, limits, calculations and failures

**Business Architect (`@ATLAS`)**
- Objective: clear and deterministic promotions with server-authoritative totals.
- Contract: one coupon per order, discount nonnegative and capped by subtotal, free delivery unchanged. `EVERYDAY` = 50% off and continues to work. Define consistent expiry clock, `FIRSTBUY` eligibility, one-use limits and discount caps. Existing 50% calculation on integers must match reference.
- Sample deterministic codes: `EVERYDAY` 50%; `SAVE100` ₹100 off minimum subtotal ₹1,000; `EXPIRED10` expired; `FIRSTBUY` new customer only (requires session-linked eligibility without full P1 auth); `LIMITED20` capped uses; `FREESHIP` free shipping (zero-valued benefit in free-shipping catalog, still validate gracefully).
- Acceptance: `CPN-01` EVERYDAY still applies correctly; `CPN-02` invalid/expired rejected; `CPN-03` boundary ₹999/₹1,000/₹1,001; `CPN-04` max discount and nonnegative total; `CPN-05` removed coupon restores full price; `CPN-06` server ignores client tampering; `CPN-07` API 500/timeout shows safe retry; `CPN-08` expired/capped use uses deterministic test clock; `CPN-09` no race permits extra redemption.

**Lead Developer (`@FORGE`)**
- Patterns: `CouponPolicy` strategy registry, pure pricing calculator, service-backed `POST /api/coupons/validate`, server recalculation at order creation, coupons D1 table/migration if usage/eligibility state is needed.
- Increment 1: [ ] characterize EVERYDAY; [ ] apply and remove; [ ] validation message; [ ] separate subtotal/discount/total; [ ] invalid coupon path.
- Increment 2: [ ] SAVE100, EXPIRED10, FIRSTBUY, LIMITED20, FREESHIP; [ ] minimums and caps; [ ] persistence/expiration/limits; [ ] single active coupon; [ ] error code mapping; [ ] server-side policy.
- Increment 3: [ ] frozen-clock expiry boundaries; [ ] usage races; [ ] 500/timeout/retry; [ ] maliciously supplied discount in payload ignored; [ ] cross-tab recalculation; [ ] negative total protection.
- A/B guard: `EVERYDAY` 50%-off display and calculation remain identical for old journeys.
- Tests: valid/invalid/expired/capped, boundaries, duplicate usage, tampered request, fallback, rounding and independent expected-values table.
- Done: CPN-01…CPN-09 PASS; coupon business rules published in API contract.

### P0-06 — Guest checkout, simulated payments, order creation

**Business Architect (`@ATLAS`)**
- Objective: safe, complete **demo** purchase journey; no real payment, no real delivery.
- Business rules: Delivery → Payment → Review → Confirm is a stateful flow; required name/email/phone/street/city/state/PIN validated; changing earlier step preserves valid entries; server revalidates current cart and coupon; one confirmation action yields at most one order; client never claims payment received; failed simulation never creates a paid order.
- Acceptance: `CHK-01` shipping validation and errors; `CHK-02` form state preserved on backward/forward; `CHK-03` simulated method success/decline/cancel/timeout; `CHK-04` order summary equals server; `CHK-05` unique order ID; `CHK-06` cart clears **only** on success; `CHK-07` idempotency key handles repeated confirm; `CHK-08` empty/expired-cart blocks checkout; `CHK-09` server catches modified price/coupon/stock; `CHK-10` no real card/payment data stored or sent to external gateway.

**Lead Developer (`@FORGE`)**
- Patterns: checkout state machine + validation schema; server `CheckoutService` with server-side price calculation, idempotent `OrderRepository`; D1 transaction/batch with uniqueness constraint and safe retry.
- Increment 1: [ ] characterize existing three-step checkout; [ ] name/email/phone/address/city/state/PIN; [ ] field-specific validation; [ ] summary; [ ] order reference; [ ] success page.
- Increment 2: [ ] preserve form between steps; [ ] shipping choices (free default); [ ] demo payment statuses and clear labels; [ ] invalid credential/form states; [ ] disable while pending; [ ] backward navigation; [ ] accessible progress and errors.
- Increment 3: [ ] fake timeout/decline/cancel; [ ] double-submission idempotency; [ ] stale inventory/price conflict; [ ] simulated payment iframe (prefer P1 Automation Lab if it adds external complexity; contract covered now); [ ] session expiration recovery; [ ] reload/interrupted checkout recovery.
- Migration: keep current `card`, `paypal`, `pay-later` demo options working; introducing simulated UPI/COD requires an explicit additional acceptance story. Never integrate real provider or handle true CVV/PAN as test data.
- A/B guard: complete original checkout on disposable A and candidate B, compare discounts, order status and cart clearing; never write real orders in public production smoke.
- Tests: valid address, malformed email/PIN, missing phone/state, step state persistence, payment branches, failed API, timeout, double-click, idempotency retry, zero cart, back navigation, order ID uniqueness.
- Done: CHK-01…CHK-10 PASS in isolated staging, with negative-path evidence.

### P0-07 — REST APIs and contracts, preserving existing clients

**Execution update (2026-10-31):** The P0-07–09 local API/data/test foundations are implemented. `docs/implementation/P0-07-09-ACCEPTANCE.md` maps each acceptance ID to checks; `outputs/p0-07-09-completion/EXECUTION_REPORT.md` records the current local and read-only production results. The unchecked increments remain the original plan, not proof of missing or completed execution. Protected hosted staging/recovery and P0-10 automation remain separate open gates.

**Business Architect (`@ATLAS`)**
- Objective: enable API-only setup and validation for UI tests while retaining all legacy behaviors.
- Rules: stable JSON response model, meaningful 2xx/4xx/5xx, explicit error `code` and `message`, no client-controlled monetary fields, products/stock authoritative, guest isolation, same-origin authenticated requests.
- Acceptance: `API-01` legacy `/api/shop` continues to work through migration; `API-02` product APIs return stable original records; `API-03` cart CRUD validated; `API-04` coupon endpoint server-authoritative; `API-05` order create/read isolated; `API-06` consistent errors; `API-07` no cross-session access; `API-08` contract test of payload shape; `API-09` same-site security; `API-10` no credentials leaked.

**Lead Developer (`@FORGE`)**
- Patterns: route handler → schema DTO validation → application service → repository; version API contracts as needed; make old `POST /api/shop` a compatibility adapter rather than duplicate business rules.
- Increment 1: [ ] `GET /api/health`; [ ] `GET /api/products`; [ ] `GET /api/products/:id`; [ ] `GET /api/categories`; [ ] preserve current `/api/shop` GET/POST and write characterization tests.
- Increment 2: [ ] `GET /api/cart`; [ ] `POST /api/cart/items`; [ ] `PATCH /api/cart/items/:id`; [ ] `DELETE /api/cart/items/:id`; [ ] `POST /api/coupons/validate`; [ ] `POST /api/orders`; [ ] `GET /api/orders/:id` for same guest.
- Increment 3: [ ] filter/sort/page query parameters; [ ] pagination metadata; [ ] stock update race conflict; [ ] idempotency and contract version policy; [ ] 400/401/403/404/409/422/429/503 examples; [ ] request correlation ID; [ ] transaction/rollback verification.
- Example product: `{ "id": 46, "name": "Plant Pot", "priceMinor": 149900, "currency": "INR", "stock": 20, "available": true }`. The existing UI price remains ₹1,499.
- Security: protect POST with origin/session/CSRF defenses appropriate to the actual runtime; server-side validate fields; never expose test reset APIs in production.
- Tests: Playwright Python `APIRequestContext`, contract assertions, cross-session isolation, method not allowed, quantity boundaries, price tampering, duplicate idempotency key, authorization.
- Done: API-01…API-10 PASS; versioned API reference available.

### P0-08 — Deterministic test data, migrations and environment isolation

**Business Architect (`@ATLAS`)**
- Objective: reproducible scenarios that do not compromise live orders or concurrent test runs.
- Rules: preserve 13 originals; test product IDs must be distinct; fixed known inventory and coupon states; every parallel worker owns namespace/user/session; clock can be frozen for expiration; test reset never deletes someone else's dataset.
- Acceptance: `DATA-01` one-command local seed; `DATA-02` safe isolated reset; `DATA-03` stable original product IDs/prices; `DATA-04` no reset on production; `DATA-05` isolated guest contexts; `DATA-06` reproducible expired coupon/stock scenarios; `DATA-07` rollback-safe additive migration; `DATA-08` parallel workers do not collide.

**Lead Developer (`@FORGE`)**
- Patterns: fixture factory + deterministic seed + repository ports + migration discipline; per-test worker IDs.
- Increment 1: [ ] baseline snapshot data; [ ] scripts for local D1 migration/seed; [ ] sample `standard_guest`, `empty_cart_guest`, `low_stock_product`, `out_of_stock_product`, `expired_coupon`; [ ] a test-mode predicate.
- Increment 2: [ ] staging-only protected seed/reset per test namespace; [ ] API fixtures to add inventory/orders; [ ] clock injection for coupon expiry; [ ] cleanup in `pytest` teardown; [ ] local test D1 database per worker where possible.
- Increment 3: [ ] concurrency isolation tests; [ ] persistence across deployments; [ ] migration rollback plan (prefer forward fix migration with backup); [ ] data retention/PII scrub; [ ] service failure seed.
- Proposed endpoint **only for trusted non-production environment**: `POST /api/test/reset` with short-lived test-only auth and namespace, not a public unauthenticated URL. Validate environment server-side, not via user-supplied header.
- Tests: reset idempotency, namespace isolation, prod reset rejection, migration up, duplicate seed, clock boundaries.
- Done: DATA-01…DATA-08 PASS and tester can reproduce without manually cleaning shared state.

### P0-09 — Automation hooks and Python Playwright testing framework

**Business Architect (`@ATLAS`)**
- Objective: tests remain readable, stable, business-oriented, reproducible, and independently runnable by a recruiter.
- Acceptance: `AUTO-01` semantic locators by role/label; `AUTO-02` selective stable test IDs; `AUTO-03` isolated pytest fixtures; `AUTO-04` clear Page/Component Objects; `AUTO-05` UI+API contract tests; `AUTO-06` diagnostics on fail; `AUTO-07` markers for smoke/regression/e2e/destructive; `AUTO-08` no fixed sleeps; `AUTO-09` browser and locale parametrization; `AUTO-10` 35–50 purposeful automated tests as portfolio target, not quota at expense of quality.

**Lead Developer (`@FORGE` with `@SPEC`)**
- Patterns: POM and component objects, fixtures for API and storage state, data factory, environment config adapter; no tight coupling to application TypeScript internal classes.
- Increment 1: [ ] create `python-playwright/` with `pyproject.toml`/requirements, `pytest.ini`, `conftest.py`; [ ] Home/Catalog/Product/Cart/Checkout page objects; [ ] base URL from env; [ ] first-run language fixture; [ ] navigation, search, cart smoke.
- Increment 2: [ ] API client wrappers and typed fixture objects; [ ] test data setup/teardown; [ ] split `tests/smoke`, `tests/api`, `tests/regression`, `tests/e2e`; [ ] failures capture trace/screenshot; [ ] English/French tests; [ ] cross-browser smoke; [ ] robust locators.
- Increment 3: [ ] CI parallel execution with isolated workers; [ ] HTML/JUnit report, Allure optional with approval; [ ] mobile context tests; [ ] flake register, artifact retention; [ ] candidate A-vs-B comparison command.
- Proposed IDs only when semantic labels insufficient: `product-search`, `product-card-46`, `product-price-46`, `cart-count`, `quantity-input`, `cart-subtotal`, `coupon-message`, `order-total`, `order-id`. **Preserve existing** `language-english`, `language-french`, `language-switcher`.
- Example smoke command: `python -m pytest -m smoke --base-url "$URL" --tracing=retain-on-failure`. Pin compatible Python, Playwright and pytest-playwright versions after environment test; use lockfile for reproducibility.
- Tests: fixture isolation (fresh cookie), strict semantic selectors, screenshot/trace collection, no production-write marker, use consistent price oracle and contract test.
- Done: AUTO-01…AUTO-10 PASS, tests executable locally and in CI with documented commands.

### P0-10 — CI/CD, baseline reporting, gated releases and rollback

**Business Architect (`@ATLAS`)**
- Objective: each code or deployment change is attributable and validated; approval gates prevent unreviewed release; every deployment has an automatic smoke verdict.
- Rules: tests must pass before push approval (when environment permits), before merge, after staging deploy, after production deploy; failed smoke stops advancement; owner approval cannot be inferred from chat silence or workflow activity.
- Acceptance: `REL-01` PR checks; `REL-02` independent monitoring step; `REL-03` baseline/candidate summary; `REL-04` staging deployment after approval; `REL-05` staging post-deploy smoke; `REL-06` production deployment after approval; `REL-07` production read-only post-deploy smoke; `REL-08` rollback and rerun smoke; `REL-09` reports/traces tied to SHA; `REL-10` no unapproved push or third-party installation.

**Lead Developer (`@FORGE` with `@SMOKE` and `@PERMIT`)**
- Patterns: reusable CI workflow, immutable build SHA, environment promotion, least-privilege GitHub Actions permission, fail-closed policy.
- Increment 1: [ ] `lint`, `typecheck`, `build`, Python unit/smoke checks; [ ] JUnit/trace artifacts; [ ] exact deployment URL/config; [ ] branch protection plan.
- Increment 2: [ ] baseline vs candidate matrix; [ ] protected staging environment; [ ] GitHub deployment-success/webhook smoke; [ ] no manual deployment escape; [ ] test-only DB; [ ] upload logs/artifacts only to trusted storage.
- Increment 3: [ ] protected production approval; [ ] production read-only smoke; [ ] rollback runbook; [ ] unique job names/required status checks; [ ] duplicate deploy concurrency prevention; [ ] scheduled optional regression only after owner approval.
- Tests: CI dry-run in disposable branch after push approval; deliberately failing smoke blocks next stage; expired approval re-requests; missing SHA/URL blocks release; failed deployment does not mark pass; rollback smoke runs.
- Done: REL-01…REL-10 PASS with at least one authorized staging release and its post-deploy smoke report. Without permission to deploy, report `BLOCKED` and do not pretend P0 fully done.

## 8. P0 end-to-end acceptance suite (not to be omitted)

| Suite | Required scenarios | Execution target |
|---|---|---|
| Navigation | home/logo, Shop/Accessories/Cart, active nav, 404, language dialog, keyboard/mobile | Baseline A, candidate B, prod read-only smoke |
| Catalog | name/partial/case/trim search, no results, clear, filter+sort, range, URL persistence, pagination, delayed/500 recovery | Candidate B; subset on A |
| Product | ID 46 metadata/₹1,499, quantity 1/10, stock 0, not found, gallery, variant | Candidate B |
| Cart | add, repeat add, qty ±, remove, clear, reload persist, two tabs, 503 recovery, total reconciliation | Isolated staging |
| Coupon | EVERYDAY 50%, invalid, expired, min threshold, remove, caps, usage, tamper, 500 recovery | Isolated staging |
| Checkout | address/PIN/phone/email validation, step back/forward, all demo methods, confirm, decline, timeout, double submit, cart clear, order ID | Isolated staging |
| API | products, product by ID, cart CRUD, coupon validate, create/get order, schema/status codes, session isolation, wrong origin, idempotency | Isolated staging |
| Data | seed/reset, prod rejection, per-worker isolation, migrations, coupon clock | Local/staging only |
| Framework & release | `-m smoke`, trace, junit, browser contexts, CI, per-deploy trigger, monitoring PASS/BLOCK, approval and rollback drill | Local CI + authorized staging |

**Completion rule:** P0 is done only when every acceptance ID above is `PASS`, `APPROVED_INTENTIONAL_CHANGE`, or a specifically owner-accepted exception with a recorded risk and follow-up. `SKIP`, `UNKNOWN` and `NOT_RUN` are not completion statuses. Build only one vertical slice at a time to keep 2–3 hours/day of Python Playwright study realistic.

## 9. P1 handoff — start only AFTER explicit approval

**Blocking gate:** Once P0 is completed, `@WATCHTOWER` issues `P0_FINAL_REPORT.md` listing every acceptance ID, A/B summary, last smoke status per deployed environment, known defects, runbooks, costs and recommended P1 order. `@CONDUCTOR` then stops and asks:

> **P0 is complete and the evidence pack is ready. May I begin P1 in this order: Authentication → Orders/Invoices → Automation Lab/Network Scenarios → Wishlist/Reviews → Localization/Accessibility? Reply `APPROVE P1 START` or specify a different priority.**

**No P1 coding or pushing begins before that answer.** To avoid ambiguity, the P1 backlog is fully specified now but remains pending.

### P1-01 — Authentication and account sessions

- **Architect:** guest checkout remains valid; registration/login/logout, password reset (demo or approved provider), protected profile, account roles, session expiry, safe guest cart merge, explicit unauthorized errors.
- **Developer:** separate auth adapter/service/session repository, guard middleware and role policy; do not wire actual paid identity provider without separate permission; test users with fake email addresses only.
- **Tests:** valid/invalid/locked login, password rules, storage state, session expiration, user-order authorization, two sessions, cart merge, route/API access.
- **Dependencies:** P0 API contracts and data isolation.

### P1-02 — Order history, statuses and downloads

- **Architect:** user order history, order detail, statuses Placed/Processing/Shipped/Delivered/Cancelled/Refunded, cancellation eligibility, status filters, invoices, isolation between users.
- **Developer:** order query repository, state transition policy, invoice generator in test-mode, versioned API/status events.
- **Tests:** order persists across sessions, status transition legality, cancellation rejection after cutoff, invoice download event and content, unauthorized access.

### P1-03 — Wishlist, ratings and reviews

- **Architect:** favorite products, authenticated persistence, review ratings 1–5, required fields, moderation/ownership, no duplicate conflicting votes.
- **Developer:** domain entities, wishlist repository, review API/UI, file upload to authorized safe storage if approved, validation and file limits.
- **Tests:** wishlist persistence, add/remove, star average, review length, edit/delete ownership, image upload/drag and invalid MIME/size.

### P1-04 — Automation Lab (dedicated, clearly test-only)

- **Architect:** a separate `/automation-lab` route for browser exercises so customer flows remain realistic.
- **Developer:** independent screens for alerts/confirm/prompts, modal focus, hover, double/right click, checkboxes/radios, single/multi-select, iframes/nested frames, new tabs, upload, PDF/CSV download, drag/drop, delayed buttons, infinite scroll, date picker, dynamic grid, editable text, Shadow DOM and notifications.
- **Tests:** explicit success signals for each interaction; Python Playwright files, frames, events, dialogs, download, keyboard, visual states.
- **Security:** no production secret access and no arbitrary execution capability from the Lab.

### P1-05 — Controlled network/error sandbox

- **Architect:** reproducible 404/401/403/429/500/503, slow 500/2,000/5,000ms, empty/malformed payload, abort/retry and recovery paths.
- **Developer:** test-only scenario controller behind environment guard; Playwright route mocking preferred over production API toggles where possible.
- **Tests:** loading/empty/error/retry states, request cancellation, safe backoff behavior, no flaky unbounded waits.

### P1-06 — Localization and accessibility expansion

- **Architect:** finish English/French translations, explicit fallback policy, readable date/number formatting, consistent error language, keyboard and screen-reader UX.
- **Developer:** translation-key audit, accessible name checks, icon labels, focus/dialog behavior, responsive QA, optional axe-core tests under approval.
- **Tests:** locale cookie persistence, long text on mobile, modal focus trap, WCAG-oriented checks, zero mixed-locale critical checkout labels.

**P2 placeholder (only after separate priority review):** Admin CRUD, order/inventory lifecycle control, audit history, bulk imports, advanced concurrent inventory, real user-experiment infrastructure, deep AI agent orchestration and more expensive observability.

## 10. Third-party permissions: step-by-step instructions, rationale, and block conditions

**Policy:** `@PERMIT` writes a dedicated request *before* any new installation, OAuth grant, paid plan upgrade, secret creation, external deployment or remote-write action. Always state provider, scopes, pricing implications, what data leaves the project, revocation steps, and why it is necessary. Favor existing tools and built-in facilities first.

### 10.1 GitHub repository write access and Actions (existing read access is separate)

**Why:** code reviews, immutable commits, source control, required checks, deployment links, trace/report artifacts.

1. Owner confirms `9anirudh9/everyday-ecommerce-store` is the intended repository and specifies branch naming and contribution permissions.
2. In GitHub repository **Settings → Collaborators and teams** (or organization access controls), verify the approved agent/app has **only the minimum needed repo permission**. Do not give admin permission when Contents write + PR access is sufficient.
3. For a new GitHub App, review **Settings → Applications → Installed GitHub Apps** and inspect granted repositories and permission categories. Grant only this repo if possible; review permissions before clicking Install/Authorize.
4. Enable GitHub Actions only if not already enabled; inspect **Settings → Actions → General** for allowed actions, token permission policy and fork PR security. Prefer read-only `GITHUB_TOKEN` except jobs that specifically need narrowly-scoped write permission.
5. Configure protected `main` in **Settings → Rules → Rulesets** or branch protection: require PR review, required unique status checks, prohibit force push, optionally include deployment requirements.
6. If plan supports it, configure **Settings → Environments → staging / production** and required reviewers, restricted branches, environment secrets. Verify entitlements: required-reviewer deployment rules have repository-visibility/plan restrictions. Do not assume private repo on free plan supports the same gates.
7. Test permission via an **approved temporary branch/PR only**; never use main as a dry-run target.
8. Document rollback/revoke path: remove app/repo permission, rotate any leaked credentials, disable workflows if necessary.

**Block if:** owner has not named repo/target branch, permission scope is overly broad, push approval missing, or required checks cannot be enforced in chosen environment.

### 10.2 Cloudflare Workers, D1, Wrangler and staging deployment

**Why:** current code runs on Cloudflare Workers and uses D1; staging DB and deployments are required to validate cart, coupon and order writes safely.

1. Owner signs into Cloudflare and confirms which Workers service and D1 database correspond to **development, staging and production**.
2. Create a **separate staging Worker + D1 database** (and disposable local D1), never point staging tests at production D1.
3. Set the Wrangler `DB` binding for each environment using the real configuration supported by the repo/hosting integration; first verify platform-managed configuration before editing project files.
4. For local development, install Node/pnpm versions shown in README and run `pnpm install`, `pnpm dev`; run D1 migration locally, e.g. `pnpm exec wrangler d1 execute DB --local --file drizzle/0000_legal_the_twelve.sql` after checking binding is configured.
5. If CI needs Cloudflare API access, create a narrowly scoped token for the specific account/Worker/D1 resources, store it only in a protected CI secret/environment, and keep it out of logs, `.env` commits and agent prompts.
6. Enable only the required deployment workflow after owner approves the plan and token scope. Stage first; attach deployed URL+SHA and run smoke.
7. For production, request a **separate** approval. Maintain a previous-known-good version and rollback procedure, subject to platform deployment behavior and D1 migration compatibility.
8. Review usage/cost limits and remove the token when no longer needed.

**Block if:** staging DB not isolated, no safe migration path, Cloudflare privileges unknown, or tests might modify live customer records.

### 10.3 Optional coding-agent platform + Playwright MCP / CLI

**Why:** agent-assisted exploration and test generation, especially after the deterministic Python framework exists. Not required for P0 business features unless specifically approved for agent runtime testing.

1. Choose one approved execution platform (e.g., locally installed coding agent or an organization-approved tool); verify current capabilities and pricing on its official documentation.
2. Explicitly review which files, shell commands, browser pages, network calls and git operations the agent can access. Disable autonomous push/deploy/install capabilities where controls exist.
3. Approve local-only installation and the Playwright MCP/CLI dependencies only after dependency/security check and an exact command list is shown.
4. Configure **read-only sandbox access** to the test environment initially; no production credentials in the prompt/context.
5. Register the vendor-neutral agent instructions from `agents/` using that platform's custom-agent process; map call names exactly.
6. Run the AG-03…AG-07 dry-runs, including refusal to push and fail-closed monitoring.
7. Review generated code manually; never allow a generated API/payment test to target production writes.
8. Disconnect/revoke access if it requests unexpected scopes or performs unapproved actions.

**Block if:** agent tool cannot restrict remote writes, execution cost unbounded, no audit log, or owner's installation permission absent.

### 10.4 Optional reporting/notifications or true A/B experimentation

**Why:** report sharing, alerts or product analytics may help later; **not mandatory** for initial P0.

1. Explain the actual gap not solved by local JUnit/HTML/traces + GitHub Actions.
2. Compare built-in GitHub artifact/report options first and record zero-extra-service alternative.
3. For any external reporting/analytics, specify exact provider, events/fields, data retention, cost, privacy risks and scopes.
4. Require owner approval for account creation, webhook/OAuth scopes and any persistent tracking cookies.
5. In a true randomized A/B test, define metrics, assignment, minimum detectable effect, sample size, privacy consent and stopping rule *before* exposing users.
6. Verify cancellation, revocation and data deletion process.

**Default:** skip additional vendors, paid A/B platforms, Slack bots, third-party payment gateways and actual email providers until their benefit and authorization are clear.

## 11. AI model routing and cost control

**Goal:** spend model tokens on uncertainty and architecture, not on repetitive, deterministic checks. Model availability/prices differ by account/provider and can change; select by capability tier rather than inventing a fixed price or implying automatic cross-platform routing exists.

| Work type | Default execution | Escalate only if | Cost rule |
|---|---|---|---|
| Counting/checklists, syntax, lint, diff, assertions, CI | **No LLM** (scripts and test runner) | Tool itself fails with ambiguous root cause | Prefer deterministic automation |
| Brief test-matrix drafting, docs, issue labeling, results summarization | Small/fast low-cost model | Misses constraints in two attempts | Cap context and output; reuse templates |
| Routine code edits, Page Objects, schema DTOs, unit tests | Standard mid-tier coding-capable model | Complex regression, repeated failing tests | Restrict to one workstream and file scope |
| Cross-cutting migrations, security, data races, auth, high-risk rollback | Strong reasoning/high-effort model | Human decision still required for tradeoff/approval | One targeted review; do not rerun entire spec |
| `@WATCHTOWER` compliance gates | Rule-based validator first; cheap model only for narrative discrepancy | Evidence conflicts | Never let LLM substitute for test artifacts |

Controls:

- [ ] Agent orchestrator records expected model tier, reason, max calls, max input context and actual usage when exposed by provider.
- [ ] Default **one planner call + one implementer call + one reviewer call** per small slice. Error-driven retry budget: one focused attempt, then escalate/stop.
- [ ] Pass minimal diffs and relevant files, not the entire repo, to an LLM.
- [ ] Reuse cached baseline snapshots and product fixtures across A/B runs; avoid re-summarizing unchanged evidence.
- [ ] Prevent agent-to-agent infinite conversations: each agent returns a short structured result and final verdict.
- [ ] Use test runner outputs, not hallucinated pass percentages. Run expensive cross-browser/full regression at milestone/release gates, fast smoke for each deployment.
- [ ] Track budget per slice (token usage, CI runtime, service spend); ask for approval before exceeding owner-agreed cap.
- [ ] For high-risk changes require deliberate independent review regardless of model tier.

**Suggested ownership:** `@CONDUCTOR` selects tiers and enforces budgets; `@WATCHTOWER` flags overspend or unbounded retries; `@PERMIT` obtains approval for new paid providers.

## 12. Releases, story slices, and first actions

### 12.1 Suggested P0 slices in dependency order

| Slice | Main outcome | First tests / release guard |
|---|---|---|
| `P0-00` | Agent definitions, dry-runs, audit and test baseline A | AG-01…AG-08; source audit + read-only baseline |
| `P0-01` | Shared navigation, cart badge, error routes | Navigation/mobile smoke |
| `P0-02` | Search/filter/sort and catalog pagination | Query/filter matrix + visual A/B |
| `P0-03` | Product detail quantity/media/stock | PDP edge and API tests |
| `P0-04` | Cart consistency and persistence | Staging cart E2E + session isolation |
| `P0-05` | Coupon server policy and edge cases | Staging coupon API/total oracle |
| `P0-06` | Robust demo checkout and idempotency | Staging end-to-end order flow |
| `P0-07` | Documented REST endpoints (implemented incrementally with slices) | Python API contract suite |
| `P0-08` | Deterministic D1 seed/reset (implemented early with slices) | Isolation/security tests |
| `P0-09` | Python Playwright POM, fixtures and reporting (throughout P0) | Runnable smoke/regression suite |
| `P0-10` | Approval-gated CI and post-deployment smoke (enable before first deployed slice) | Deliberate fail demonstration |

**Dependency note:** P0-07/08/09/10 are *foundations* that should start during P0-00 and be completed alongside UI slices, not left until the very end. No deployed feature bypasses P0-10.

### 12.2 First 10 concrete tickets (start immediately after access/approval preconditions)

1. `AG-001` Add eight agent prompts, manifest and static checker **locally**.
2. `AG-002` Run static checker; collect output and validate agent prompt names and guardrails.
3. `AG-003` Run role-by-role dry-run/negative tests in an approved agent execution environment; document any unsupported behavior.
4. `BASE-001` Record current `main` commit SHA, deployment ID, and read-only source inventory.
5. `BASE-002` Write non-destructive Python Playwright baseline smoke tests for Home, Shop, product 46, search, language, nav; execute when browser environment is available.
6. `BASE-003` Create disposable staging D1/test session, backed up before any mutation; require Cloudflare permissions and owner approval if needed.
7. `ARCH-001` Record ADRs for service boundaries, pricing, data isolation and releases.
8. `REL-001` Draft GitHub Actions required checks and post-deploy smoke workflow **locally**; get owner's push/deploy approvals separately.
9. `P0-01.01` Enhance header active state/cart badge behind a backward-compatible local patch; A/B compare and obtain push approval.
10. `P0-02.01` Characterize existing search and implement category/sort controls in small diff; A/B compare.

### 12.3 Defect/risk register from read-only source audit (NOT confirmed runtime failures)

| ID | Observation | Why it matters | Verify with |
|---|---|---|---|
| `RISK-01` | UI/domain/API behavior concentrated in `app/shop.tsx` | High regression surface for unrelated edits | Characterization suite before extraction |
| `RISK-02` | `/api/shop` multiplexes cart update and checkout, no dedicated catalog/order REST surface | Harder to isolate tests and evolve API | Contract matrix + adapter strategy |
| `RISK-03` | Cart mutations and checkout lack explicit idempotency key in inspected code | Retry/double-click risks | Concurrent/retry E2E in staging |
| `RISK-04` | Only EVERYDAY coupon exists in inspected UI/server code | Missing expired/min-order/usage edge scenarios | Coupon policy/API tests |
| `RISK-05` | No stock inventory in current `Product` type | Cannot test out-of-stock and stock races | Product inventory schema + boundary tests |
| `RISK-06` | No test suite/CI workflow found in inspected repository tree | Release regression detection not demonstrated | Add test/CI scaffold and execute |
| `RISK-07` | Search suggestions use role listbox/option links with limited keyboard logic visible | Accessibility interaction could be incomplete | Arrow/Enter/Escape/browser audit |
| `RISK-08` | No header cart quantity badge visible in inspected header | Cross-page cart feedback limited | Baseline screenshot + UI test |
| `RISK-09` | Demo payment card inputs appear in UI, while code submits only payment method at order creation | Ensure no real secrets or card storage appear in logs | Network/DB inspection with test data |
| `RISK-10` | Direct deployed Workers/D1 environment settings not verified | Unsafe to assume deployment or reset access | Owner/platform configuration review |

**Do not call these confirmed bugs until failing reproduction evidence exists.** File verified failures separately with reproduction URL, browser, SHA, steps, expected/actual, trace, screenshot, severity and assigned owner.

## 13. Templates for one work item and one release

### 13.1 Story / work item

```markdown
# P0-XX.YY — <feature>
Business architect: @ATLAS
Lead developer: @FORGE
QA: @SPEC
Baseline/A-B owner: @PROBE
Independent monitor: @WATCHTOWER
Approvals: @PERMIT
Status: PLANNED

## User value and business rules
... 
## Existing A contract and evidence
... 
## Candidate B design and design patterns
... 
## Incremental implementation tasks
- [ ] ...
## API and data migration (or N/A)
... 
## Acceptance criteria (including negative and boundaries)
... 
## Python Playwright test IDs, fixtures and target environment
... 
## A/B result (PASS/REGRESSION/BASELINE_DEFECT/INCONCLUSIVE)
... 
## Smoke impact, security, accessibility, cost
... 
## Approval ledger (push, staging, production, external)
... 
## Monitor verdict and open defects
... 
```

### 13.2 Release record

```markdown
# Release <tag> / SHA <hash>
Change IDs: ...
Baseline A SHA+URL: ...
Candidate B SHA+URL: ...
Pre-push tests: ...
A-vs-B contract/visual diff: ...
Independent monitor: PASS / BLOCK
Owner push approval: ...
Remote push proven: ...
Owner staging deployment approval: ...
Staging deployment URL/SHA/run: ...
Staging post-deploy smoke result: ...
Owner production deployment approval: ...
Production deployment URL/SHA/run: ...
Production post-deploy read-only smoke result: ...
Known defects / rollbacks / follow-up: ...
Model + CI cost summary: ...
```

## 14. P0 exit gate (no silent transition)

All must be checked before asking to implement P1:

- [ ] Every P0-01…P0-10 acceptance ID has evidence and result.
- [ ] AG-01…AG-08 agents defined **and** runtime-validated (not just static lint).
- [ ] Existing behavior baseline A captured and all intentional changes to candidate B identified.
- [ ] No unapproved regression in product IDs, prices, cart, coupon, language or demo checkout.
- [ ] All critical security and correctness defects resolved or explicitly approved as risk exceptions.
- [ ] Python Playwright smoke + API + key E2E pass against isolated staging.
- [ ] Automated post-deployment smoke fires on every authorized staging and production release.
- [ ] Production smoke is read-only; no public data reset or accidental order.
- [ ] Approval ledger includes every push, merge/deploy and external integration action.
- [ ] All tests and traces are reproducible and available in a safe trusted location.
- [ ] `@WATCHTOWER` issues P0 final PASS and the owner receives the P1 approval request.

## 15. References and maintenance

- Current source: https://github.com/9anirudh9/everyday-ecommerce-store
- Live site: https://everyday-shop-anirudh.cidirianirudh.chatgpt.site/
- Playwright Python setup: https://playwright.dev/python/docs/intro
- Playwright Python CI guidance: https://playwright.dev/python/docs/ci
- GitHub branch protection: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub environment protection/review: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

**Change-control rule:** Modify this plan when the codebase or scope changes; never mark a task complete from a proposal or simulated output. The final owner-approved implementation and evidence ledger must identify actual repository SHAs and deployment URLs.
