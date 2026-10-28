# Python Playwright contract and browser suite

The new pytest suite lives in `tests/api`, `tests/smoke`, and `tests/e2e`. The
standalone runners in `tests/regression` are preserved and excluded from pytest
discovery. There are 51 focused pytest functions; origin/method parametrization
expands a full run to 68 cases. `python -m pytest --collect-only`
checks collection only; it is not runtime evidence.

Python 3.13 is the tested interpreter. Prepare a virtual environment and install
the tested dependency closure in `requirements.lock` (the shorter
`requirements.txt` lists direct pins). On Windows:

```powershell
python -m venv .sites-runtime/qa-venv
.sites-runtime/qa-venv/Scripts/python.exe -m pip install -r python-playwright/requirements.lock
```

Install the Playwright browser engines separately where needed. Chromium tests
use installed Google Chrome; selecting Firefox/WebKit needs the corresponding
Playwright engine. A missing engine is NOT RUN, never a browser PASS. The lock
was resolved on Windows/Python 3.13; other platforms need dependency verification.

Run the full en/fr × desktop/mobile matrix, with a retained source fingerprint,
JSON summary, per-run JUnit and HTML reports:

```powershell
.sites-runtime/qa-venv/Scripts/python.exe scripts/run_qa_matrix.py --base-url http://127.0.0.1:8790 --manifest .sites-runtime/test-data/demo-001/main/manifest.json --report-dir outputs/qa/demo-001
```

For read-only deployment checks, use `--smoke` and omit `--manifest`. Bind that
report to the exact deployment identity in the release ledger; a bare URL does
not identify a release. Matrix results distinguish individual test executions
from the 51 unique test functions. No automatic retries are enabled.

Run read-only smoke against an authorized URL:

```powershell
.sites-runtime/qa-venv/Scripts/python.exe -m pytest python-playwright/tests/smoke -m smoke --base-url http://127.0.0.1:8790 --browser chromium --locale en --viewport-mode desktop --junitxml .sites-runtime/qa-reports/smoke.xml --html .sites-runtime/qa-reports/smoke.html --self-contained-html
```

Run `python scripts/build_qa.py` to build with runtime/artifact provenance.
After `scripts/test_data.py prepare --run-id <slug> --worker main --port 8790`
and `serve` in another terminal, run isolated local API and browser tests:

```powershell
.sites-runtime/qa-venv/Scripts/python.exe -m pytest python-playwright/tests/api python-playwright/tests/e2e --base-url http://127.0.0.1:8790 --test-data-manifest .sites-runtime/test-data/<slug>/main/manifest.json --browser chromium --locale en --viewport-mode desktop --junitxml .sites-runtime/qa-reports/local.xml --html .sites-runtime/qa-reports/local.html --self-contained-html
```

Repeat with `--locale fr` and `--viewport-mode mobile`. Chromium uses the
installed system Chrome channel. Firefox and WebKit are selectable through
`--browser` if those browser engines are installed. The P0-07?09 local release evidence
records their read-only smoke results and exact engine versions.
For `-n N`, prepare and serve separate `gw0` through `gwN-1` workers in the
same run, each on a distinct port. Pass the `main` manifest path; fixtures
resolve each xdist worker's sibling manifest and URL, then verify ownership.
Running only one local server cannot support `-n N`.

Every API call checks `X-Request-ID` and `Cache-Control`; write tests require
an exact `127.0.0.1` or `localhost` origin, matching owned manifest, and a
database inside that namespace. Browser writes are blocked outside that
origin. The client blocks redirects and never prints request bodies or guest
cookies. Traces are retained only on failure and sanitized with the existing
`redact_trace.py`; screenshots may show dummy test data. Keep `.pytest-artifacts`
and report files local, and delete them after 7 days. Do not publish guest
capabilities, traces, screenshots, or the manifest.

## Earlier standalone runner notes

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
