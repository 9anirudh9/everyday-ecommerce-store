# Python Playwright starter smoke (NOT EXECUTED)

This is a minimal **read-only** test starter; it does not implement all P0 tests. The main P0 backlog and acceptance matrix are in `../IMPLEMENTATION.md`.

1. Owner chooses an authorized browser environment and URL.
2. Create venv, install requirements, install browsers.
3. Run `python -m pytest tests/smoke -m smoke --base-url "https://everyday-shop-anirudh.cidirianirudh.chatgpt.site"`.
4. Save JUnit/trace evidence and add the actual baseline commit SHA.
5. Extend to a disposable staging environment for cart/order tests only.

Do not infer a PASS from `python -m py_compile`.

## Local P0-01 browser regression

`tests/regression/test_p0_navigation.py` exercises the real built pages with a
fresh browser context and in-memory cart API mock per test. It uses the standard
library unittest runner, so pytest and pytest-playwright are not prerequisites.
Python Playwright and an installed Chrome browser are required. The runner
rejects public targets and aborts unexpected API requests. It does not verify
D1, real guest sessions or a deployed release.

Build from the repository root, then serve the build with isolated local Worker
storage (keep this server running in a separate terminal):

```powershell
node scripts/run-framework.mjs build
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js dev --config dist/server/wrangler.json --local --persist-to .sites-runtime/p0-01-browser-d1 --ip 127.0.0.1 --port 8787 --inspector-port 0
```

Run from the repository root:

```powershell
python python-playwright/tests/regression/test_p0_navigation.py --base-url http://127.0.0.1:8787 --browser-channel chrome --report-dir outputs/p0-01-browser/run-name
```

Each scenario runs in English and French at 1366×900 and 390×844. The runner saves
JSON and JUnit results plus per-test traces, screenshots, accessibility snapshots,
API call records and browser diagnostics. Intentional failed-resource diagnostics
are retained separately. Reports identify HEAD, the dirty tree, source and build
fingerprints, actual browser version and fixture inputs. No automatic retries.
These checks cover the navigation/cart-badge slice; the remaining P0-01 roadmap
items (including custom 404 and hamburger menu) need their own implementation and
acceptance evidence.
