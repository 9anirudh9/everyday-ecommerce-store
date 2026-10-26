"""Local P0-01 browser contract checks; all cart requests are intercepted.

Uses unittest because pytest is optional in the existing checkout. No installs
are needed when Python Playwright and a Chrome channel are already available.
"""
import argparse
import asyncio
from collections import defaultdict
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from playwright.async_api import async_playwright, expect
import playwright

ROOT = Path(__file__).resolve().parents[3]
CONFIG = None
RECORDS = []


class MockCart:
    """Per-context state. Unknown API routes/methods abort instead of forwarding."""
    def __init__(self):
        self.items = []
        self.mode = "ready"
        self.fail_write = False
        self.allow_checkout = False
        self.hold_reads = False
        self.hold_writes = False
        self.pending_reads = []
        self.pending_writes = []
        self.read_started = asyncio.Event()
        self.write_started = asyncio.Event()
        self.events = []
        self.expected_failures = []

    def expect_failure(self, route, kind):
        self.expected_failures.append({"request_index": len(self.events) - 1, "url": route.request.url, "kind": kind})

    async def route(self, route):
        request = route.request
        url = urlparse(request.url)
        if url.path != "/api/shop" or request.url.split("/api/")[0] != CONFIG.base_url:
            self.events.append({"unexpected_api": request.url})
            await route.abort()
            return
        event = {"method": request.method, "url": request.url, "mode": self.mode}
        self.events.append(event)
        if request.method == "GET":
            snapshot = [dict(item) for item in self.items]
            if self.hold_reads:
                self.pending_reads.append((route, snapshot))
                self.read_started.set()
                return
            if self.mode == "network":
                self.expect_failure(route, "network")
                await route.abort("failed")
            elif self.mode == "http":
                self.expect_failure(route, "http503")
                await route.fulfill(status=503, json={"error": "Unable to load your cart."})
            elif self.mode == "json":
                await route.fulfill(status=200, content_type="application/json", body="{broken")
            elif self.mode == "shape":
                await route.fulfill(json={"items": [{"product": 46, "qty": 11}]})
            elif self.mode == "null":
                await route.fulfill(json={"items": [None]})
            else:
                await route.fulfill(json={"items": snapshot})
        elif request.method == "POST":
            body = request.post_data_json
            event["body"] = body
            event["will_fail_write"] = self.fail_write
            if self.hold_writes:
                self.pending_writes.append((route, body))
                self.write_started.set()
            else:
                await self.write(route, body)
        else:
            event["unexpected_method"] = True
            await route.abort()

    async def write(self, route, body):
        if self.fail_write:
            self.expect_failure(route, "http503")
            await route.fulfill(status=503, json={"error": "Could not update the cart."})
        elif self.allow_checkout and body.get("action") == "checkout" and set(body) == {"action", "address", "coupon", "paymentMethod"}:
            self.items = []
            await route.fulfill(json={"id": "mock-only-order-0001"})
        elif set(body) == {"product", "qty"} and body["product"] in (43, 46) and type(body["qty"]) is int and 0 <= body["qty"] <= 10:
            self.items = [item for item in self.items if item["product"] != body["product"]]
            if body["qty"]:
                self.items.append(dict(body))
            await route.fulfill(json={"ok": True})
        else:
            self.events.append({"unexpected_write": body})
            await route.abort()

    async def release_reads(self):
        self.hold_reads = False
        for route, snapshot in self.pending_reads:
            await route.fulfill(json={"items": snapshot})
        self.pending_reads.clear()

    async def release_writes(self):
        self.hold_writes = False
        for route, body in self.pending_writes:
            await self.write(route, body)
        self.pending_writes.clear()


class NavigationChecks(unittest.IsolatedAsyncioTestCase):
    language = "en"
    viewport = {"width": 1366, "height": 900}

    async def asyncSetUp(self):
        self.started = time.monotonic()
        self.artifacts = CONFIG.report_dir / self.id().split(".")[-2] / self._testMethodName
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.runtime = await async_playwright().start()
        self.browser = await self.runtime.chromium.launch(channel=CONFIG.browser_channel, headless=True)
        self.context = await self.browser.new_context(viewport=self.viewport, service_workers="block")
        await self.context.add_cookies([{"name": "everyday-language", "value": self.language, "url": CONFIG.base_url}])
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self.mock = MockCart()
        await self.context.route("**/api/**", self.mock.route)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(8000)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append({"type": "pageerror", "message": str(error)}))
        self.page.on("console", lambda message: self.errors.append({"type": "console", "message": message.text, "location": message.location}) if message.type == "error" else None)
        self.header = self.page.locator("header")
        self.bag = self.header.get_by_role("link", name="Panier" if self.language == "fr" else "Shopping cart")
        self.badge = self.header.locator(".cart-count")

    async def asyncTearDown(self):
        try:
            await self.page.screenshot(path=str(self.artifacts / "page.png"), full_page=True)
            (self.artifacts / "accessibility.txt").write_text(await self.page.locator("body").aria_snapshot(), encoding="utf-8")
            expected = []
            unexpected = []
            budgets = defaultdict(list)
            for failure in self.mock.expected_failures:
                budgets[(failure["url"], failure["kind"])].append(failure)
            for error in self.errors:
                url = error.get("location", {}).get("url", "")
                kind = {"Failed to load resource: net::ERR_FAILED": "network",
                        "Failed to load resource: the server responded with a status of 503 (Service Unavailable)": "http503"}.get(error["message"])
                budget = budgets[(url, kind)]
                if error["type"] == "console" and budget:
                    expected.append({**error, "matched_mock_failure": budget.pop(0)})
                else:
                    unexpected.append(error)
            evidence = {"browser": self.browser.version, "viewport": self.viewport, "language": self.language,
                        "mock_events": self.mock.events, "expected_errors": expected, "unexpected_errors": unexpected,
                        "unmatched_mock_failures": [failure for budget in budgets.values() for failure in budget]}
            (self.artifacts / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            self.assertFalse(unexpected, f"Unexpected browser errors: {unexpected}")
            self.assertFalse(evidence["unmatched_mock_failures"], "Expected diagnostic counts differ from observed counts")
            self.assertFalse(any(any(k.startswith("unexpected") for k in event) for event in self.mock.events), "Unexpected API call")
        finally:
            await self.context.tracing.stop(path=str(self.artifacts / "trace.zip"))
            await self.context.close()
            await self.browser.close()
            await self.runtime.stop()

    async def open(self, path="/"):
        response = await self.page.goto(CONFIG.base_url + path)
        self.assertEqual(response.status, 200)
        await expect(self.header).to_be_visible()

    async def count(self, quantity):
        await expect(self.badge).to_have_text(str(quantity))
        await expect(self.bag).to_have_accessible_name(f"Panier, {quantity} articles" if self.language == "fr" else f"Shopping cart, {quantity} items")
        await expect(self.badge).to_have_attribute("aria-hidden", "true")

    async def test_navigation_and_active_state(self):
        await self.open()
        await self.count(0)
        for path in ("/products", "/accessories", "/cart", "/"):
            link = self.bag if path == "/cart" else self.header.locator(f'nav a[href="{path}"]')
            await expect(link).to_have_attribute("href", path)
            await link.click()
            await expect(self.page).to_have_url(CONFIG.base_url + path)
            await self.count(0)
            current = self.header.locator('[aria-current="page"]')
            await expect(current).to_have_count(1)
            await expect(current).to_have_attribute("href", path)
            self.assertIn("underline", await current.evaluate("e => getComputedStyle(e).textDecorationLine"))
        await self.open("/products/46")
        await expect(self.header.locator('[aria-current="page"]')).to_have_attribute("href", "/products")
        await self.page.locator('.breadcrumb a[href="/products"]').click()
        await expect(self.page).to_have_url(CONFIG.base_url + "/products")
        await self.header.locator("a.logo").click()
        await expect(self.page).to_have_url(CONFIG.base_url + "/")
        await self.open("/search?q=plant")
        await expect(self.header.locator('[aria-current="page"]')).to_have_count(0)

    async def test_sum_and_document_navigation_persistence(self):
        self.mock.items = [{"product": 43, "qty": 2}, {"product": 46, "qty": 3}]
        await self.open("/products")
        await self.count(5)
        # Full document navigation must retain context-level interception/state.
        await self.bag.click()
        await expect(self.page).to_have_url(CONFIG.base_url + "/cart")
        await self.count(5)
        await expect(self.page.locator(".cart-row")).to_have_count(2)
        await self.page.reload()
        await self.count(5)
        self.assertTrue(all(e.get("method") == "GET" for e in self.mock.events))

    async def test_loading_then_empty(self):
        self.mock.hold_reads = True
        await self.open("/cart")
        await asyncio.wait_for(self.mock.read_started.wait(), 8)
        await expect(self.badge).to_have_count(0)
        await expect(self.bag).to_have_accessible_name("Panier" if self.language == "fr" else "Shopping cart")
        await expect(self.page.get_by_role("status")).to_be_visible()
        await self.mock.release_reads()
        await self.count(0)
        await expect(self.page.locator(".empty")).to_be_visible()
        self.assertTrue(all(e.get("method") == "GET" for e in self.mock.events))

    async def test_failure_and_retry(self):
        for mode in ("http", "network", "json", "shape", "null"):
            self.mock.mode = mode
            await self.open("/cart")
            await expect(self.bag).to_have_accessible_name("Panier, Quantité indisponible" if self.language == "fr" else "Shopping cart, Cart quantity unavailable")
            await expect(self.badge).to_have_text("—")
            await expect(self.page.get_by_role("alert")).to_be_visible()
            self.mock.mode = "ready"
            self.mock.items = [{"product": 46, "qty": 2}]
            await self.page.get_by_role("button", name="Réessayer" if self.language == "fr" else "Try again", exact=True).click()
            await self.count(2)
            await expect(self.page.locator(".cart-row")).to_have_count(1)
        self.assertTrue(all(e.get("method") == "GET" for e in self.mock.events))

    async def test_add_update_remove_and_failed_write(self):
        await self.open("/products/46")
        await self.count(0)
        await self.page.get_by_role("button", name="Ajouter au panier" if self.language == "fr" else "Add to cart", exact=True).click()
        await self.count(1)
        await self.bag.click()
        await self.count(1)
        increase = self.page.get_by_role("button", name="Augmenter la quantité de Pot de fleurs" if self.language == "fr" else "Increase Plant Pot")
        decrease = self.page.get_by_role("button", name="Diminuer la quantité de Pot de fleurs" if self.language == "fr" else "Decrease Plant Pot")
        await increase.click()
        await self.count(2)
        self.mock.fail_write = True
        await increase.click()
        await expect(self.page.locator('[data-sonner-toast][data-type="error"]')).to_be_visible()
        await self.count(2)
        self.mock.fail_write = False
        await decrease.click()
        await self.count(1)
        await expect(decrease).to_be_disabled()
        await self.page.get_by_role("button", name="Retirer" if self.language == "fr" else "Remove", exact=True).click()
        await self.count(0)
        await expect(self.page.locator(".empty")).to_be_visible()
        self.assertEqual([e["body"] for e in self.mock.events if e.get("method") == "POST"],
                         [{"product": 46, "qty": q} for q in (1, 2, 3, 1, 0)])

    async def test_boundaries(self):
        self.mock.items = [{"product": 46, "qty": 10}]
        await self.open("/cart")
        await self.count(10)
        await expect(self.page.get_by_role("button", name="Augmenter la quantité de Pot de fleurs" if self.language == "fr" else "Increase Plant Pot")).to_be_disabled()
        self.assertTrue(all(e.get("method") == "GET" for e in self.mock.events))

    async def test_first_visit_language_dialog(self):
        await self.context.clear_cookies()
        await self.open()
        await expect(self.page.get_by_role("dialog")).to_be_visible()
        await self.page.get_by_test_id("language-french" if self.language == "fr" else "language-english").click()
        await expect(self.page.get_by_role("dialog")).to_have_count(0)
        await self.count(0)
        await self.page.reload()
        await expect(self.page.get_by_role("dialog")).to_have_count(0)
        await expect(self.page.locator("html")).to_have_attribute("lang", self.language)

    async def test_checkout_clears_shared_badge(self):
        self.mock.items = [{"product": 46, "qty": 1}]
        self.mock.allow_checkout = True
        await self.open("/checkout")
        await self.count(1)
        fields = [("Full name", "Nom complet", "Test Shopper"), ("Email address", "Adresse e-mail", "shopper@example.com"),
                  ("Street address", "Adresse", "123 Demo Street"), ("City", "Ville", "Bengaluru"), ("PIN code", "Code postal", "560001")]
        for english, french, value in fields:
            await self.page.get_by_label(french if self.language == "fr" else english, exact=True).fill(value)
        await self.page.get_by_role("button", name="Continuer vers le paiement" if self.language == "fr" else "Continue to payment").click()
        for english, french, value in [("Name on card", "Nom sur la carte", "Test Shopper"), ("Card number", "Numéro de carte", "4242 4242 4242 4242"), ("Expiry", "Date d’expiration", "0133"), ("CVV", "CVV", "123")]:
            await self.page.get_by_label(french if self.language == "fr" else english, exact=True).fill(value)
        await expect(self.page.locator("#expiry")).to_have_value("01/33")
        await self.page.get_by_role("button", name="Vérifier la commande" if self.language == "fr" else "Review order").click()
        await self.page.get_by_role("button", name="Confirmer et passer la commande" if self.language == "fr" else "Confirm and place order").click()
        await self.count(0)
        await expect(self.page.get_by_role("heading", name="Merci pour votre visite." if self.language == "fr" else "Thanks for shopping.", exact=True)).to_be_visible()
        writes = [e["body"] for e in self.mock.events if e.get("method") == "POST"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["action"], "checkout")
        self.assertEqual(writes[0]["paymentMethod"], "card")
        self.assertEqual(set(writes[0]), {"action", "address", "coupon", "paymentMethod"})

    async def test_mobile_layout_and_hit_target(self):
        self.mock.items = [{"product": 46, "qty": 10}]
        await self.open()
        await self.count(10)
        await expect(self.badge).to_be_visible()
        box = await self.bag.bounding_box()
        self.assertGreaterEqual(box["width"], 44)
        self.assertGreaterEqual(box["height"], 44)
        dimensions = await self.page.evaluate("({width:innerWidth, scroll:document.documentElement.scrollWidth})")
        self.assertLessEqual(dimensions["scroll"], dimensions["width"])
        self.assertTrue(await self.bag.evaluate("e => { const r=e.getBoundingClientRect(); return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)); }"))
        await self.bag.click()
        await expect(self.page).to_have_url(CONFIG.base_url + "/cart")
        await self.count(10)

    async def test_keyboard_focus_and_activation(self):
        await self.open()
        await self.count(0)
        logo = self.header.locator("a.logo")
        await self.page.keyboard.press("Tab")
        await expect(logo).to_be_focused()
        style = await logo.evaluate("e => ({width:getComputedStyle(e).outlineWidth, style:getComputedStyle(e).outlineStyle})")
        self.assertGreaterEqual(float(style["width"].replace("px", "")), 3)
        self.assertEqual(style["style"], "solid")
        await self.page.keyboard.press("Tab")
        await expect(self.header.locator('nav a[href="/"]')).to_be_focused()
        await self.page.keyboard.press("Tab")
        await expect(self.header.locator('nav a[href="/products"]')).to_be_focused()
        await self.page.keyboard.press("Enter")
        await expect(self.page).to_have_url(CONFIG.base_url + "/products")

    async def test_language_switch_persists_cart(self):
        self.mock.items = [{"product": 46, "qty": 2}]
        await self.open()
        await self.count(2)
        other = "fr" if self.language == "en" else "en"
        await self.page.get_by_test_id("language-switcher").select_option(other)
        await expect(self.page.locator("html")).to_have_attribute("lang", other)
        await expect(self.badge).to_have_text("2")
        await expect(self.header.locator('a[href="/products"]')).to_have_text("Boutique" if other == "fr" else "Shop")
        await self.page.reload()
        await expect(self.page.locator("html")).to_have_attribute("lang", other)
        await expect(self.header.locator(".bag")).to_have_accessible_name("Panier, 2 articles" if other == "fr" else "Shopping cart, 2 items")
        self.assertTrue(all(e.get("method") == "GET" for e in self.mock.events))

    async def test_stale_read_cannot_overwrite_successful_mutation(self):
        await self.open("/products/46")
        await self.count(0)
        self.mock.hold_writes = True
        await self.page.get_by_role("button", name="Ajouter au panier" if self.language == "fr" else "Add to cart", exact=True).click()
        await asyncio.wait_for(self.mock.write_started.wait(), 8)
        self.mock.hold_reads = True
        await self.page.evaluate("window.dispatchEvent(new Event('focus'))")
        await asyncio.wait_for(self.mock.read_started.wait(), 8)
        await self.mock.release_writes()
        await self.count(1)
        await self.mock.release_reads()
        # An explicit read completion barrier avoids accepting an earlier frame.
        await self.page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        await self.count(1)

    async def test_focus_refresh_preserves_unsaved_checkout_fields(self):
        self.mock.items = [{"product": 46, "qty": 1}]
        await self.open("/checkout")
        await self.count(1)
        name = self.page.get_by_label("Nom complet" if self.language == "fr" else "Full name", exact=True)
        await name.fill("Focus Shopper")
        self.mock.hold_reads = True
        await self.page.evaluate("window.dispatchEvent(new Event('focus'))")
        await asyncio.wait_for(self.mock.read_started.wait(), 8)
        await expect(name).to_have_value("Focus Shopper")
        await self.mock.release_reads()
        await self.count(1)
        await expect(name).to_have_value("Focus Shopper")
        for field, value in [("email", "focus@example.com"), ("street", "123 Demo Street"), ("city", "Bengaluru"), ("pin", "560001")]:
            await self.page.locator(f'input[name="{field}"]').fill(value)
        await self.page.get_by_role("button", name="Continuer vers le paiement" if self.language == "fr" else "Continue to payment").click()
        card_name = self.page.get_by_label("Nom sur la carte" if self.language == "fr" else "Name on card", exact=True)
        await card_name.fill("Unsaved Test Shopper")
        self.mock.mode = "http"
        await self.page.evaluate("window.dispatchEvent(new Event('focus'))")
        await expect(self.badge).to_have_text("—")
        await expect(card_name).to_have_value("Unsaved Test Shopper")
        await expect(self.page.get_by_role("alert")).to_be_visible()
        self.mock.mode = "ready"
        await self.page.get_by_role("button", name="Réessayer" if self.language == "fr" else "Try again", exact=True).click()
        await self.count(1)
        await expect(card_name).to_have_value("Unsaved Test Shopper")
        self.assertTrue(all(e.get("method") == "GET" for e in self.mock.events))


class EvidenceResult(unittest.TextTestResult):
    def startTest(self, test):
        test.record_started = time.monotonic()
        super().startTest(test)

    def addSuccess(self, test):
        RECORDS.append({"test": test.id(), "status": "PASS", "seconds": round(time.monotonic()-test.record_started, 3)})
        super().addSuccess(test)

    def addFailure(self, test, error):
        RECORDS.append({"test": test.id(), "status": "FAIL", "seconds": round(time.monotonic()-test.record_started, 3), "error": self._exc_info_to_string(error, test)})
        super().addFailure(test, error)

    def addError(self, test, error):
        RECORDS.append({"test": test.id(), "status": "BLOCKED", "seconds": round(time.monotonic()-test.record_started, 3), "error": self._exc_info_to_string(error, test)})
        super().addError(test, error)


def fingerprint(paths):
    files = {}
    for path in paths:
        if path.is_file():
            files[str(path.relative_to(ROOT)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), "files": files}


def main():
    global CONFIG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--test", help="Optional method name for a focused diagnostic; no automatic retries")
    CONFIG = parser.parse_args()
    CONFIG.base_url = CONFIG.base_url.rstrip("/")
    if urlparse(CONFIG.base_url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only loopback targets are allowed; this suite must never run on production")
    CONFIG.report_dir = CONFIG.report_dir.resolve()
    CONFIG.report_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    source_paths = [p for folder in ("app", "lib", "components", "build", "scripts") for p in (ROOT/folder).rglob("*") if p.suffix in (".tsx", ".ts", ".mjs", ".css", ".py")]
    source_paths += [ROOT/p for p in ("package.json", "pnpm-lock.yaml", "vite.config.ts", "tsconfig.json", ".openai/hosting.json")]
    source = fingerprint(source_paths)
    build = fingerprint((ROOT/"dist").rglob("*"))
    driver_version = json.loads((Path(playwright.__file__).parent / "driver/package/package.json").read_text(encoding="utf-8"))["version"]
    suite = unittest.TestSuite()
    for language in ("en", "fr"):
        for label, viewport in (("desktop", {"width": 1366, "height": 900}), ("mobile", {"width": 390, "height": 844})):
            cls = type(f"Navigation_{language}_{label}", (NavigationChecks,), {"language": language, "viewport": viewport})
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls) if not CONFIG.test else [cls(CONFIG.test)])
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    report = {"scope": "P0-01 navigation/cart-badge slice, browser-mocked API; not D1 E2E or production smoke",
              "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(), "base_url": CONFIG.base_url,
              "playwright_python_version": package_version("playwright"), "playwright_driver_version": driver_version,
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "dirty_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
              "source_fingerprint": source, "build_fingerprint": build, "test_file_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "records": RECORDS,
              "source_unchanged_during_run": source == fingerprint(source_paths),
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "baseline_comparison": "NOT RUN", "production_smoke": "NOT RUN", "database_e2e": "NOT RUN"}
    (CONFIG.report_dir/"results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    xml = ET.Element("testsuite", name="p0-01-mocked-browser", tests=str(result.testsRun), failures=str(len(result.failures)), errors=str(len(result.errors)))
    for record in RECORDS:
        case = ET.SubElement(xml, "testcase", name=record["test"], time=str(record["seconds"]))
        if record["status"] != "PASS":
            ET.SubElement(case, "failure" if record["status"] == "FAIL" else "error").text = record["error"]
    ET.ElementTree(xml).write(CONFIG.report_dir/"junit.xml", encoding="utf-8", xml_declaration=True)
    print(f"Evidence: {CONFIG.report_dir}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
