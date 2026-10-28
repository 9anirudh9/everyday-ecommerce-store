"""Local P0-02/03 browser and real-API acceptance checks.

Run only against a disposable loopback D1 instance. This runner needs the already
installed Python Playwright package and Chrome channel, and never installs them.
It has no automatic retries. A focused rerun is selected with --test.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import re
import subprocess
import sqlite3
import time
from urllib.parse import urlencode, urlparse
import xml.etree.ElementTree as ET

from playwright.async_api import async_playwright, expect
from redact_trace import redact_trace, redact_text

ROOT = Path(__file__).resolve().parents[3]
LEGACY = {
    43: ("Decoration Swing", 899, "Home"),
    44: ("Family Tree Photo Frame", 1299, "Home"),
    45: ("House Showpiece Plant", 699, "Home"),
    46: ("Plant Pot", 1499, "Home"),
    47: ("Table Lamp", 999, "Home"),
    93: ("Brown Leather Belt Watch", 1899, "Accessories"),
    94: ("Longines Master Collection", 3499, "Accessories"),
    154: ("Black Sun Glasses", 999, "Accessories"),
    155: ("Classic Sun Glasses", 1199, "Accessories"),
    156: ("Green and Black Glasses", 1299, "Accessories"),
    172: ("Blue Women's Handbag", 1799, "Accessories"),
    173: ("Heshe Women's Leather Bag", 2499, "Accessories"),
    175: ("White Faux Leather Backpack", 2199, "Accessories"),
}
VIEWPORTS = {"desktop": {"width": 1366, "height": 900},
             "mobile": {"width": 390, "height": 844}}


def fingerprint():
    files = {}
    for folder in ("app", "lib", "components", "scripts", "public/products"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in (".ts", ".tsx", ".mjs", ".css", ".svg"):
                files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), "files": files}


class Session:
    def __init__(self, args, browser, name, language="en", viewport="desktop"):
        self.args, self.browser, self.name = args, browser, name
        self.language, self.viewport = language, viewport
        self.folder = args.report_dir / name
        self.events, self.errors, self.expected_diagnostics = [], [], []
        self.context = self.page = None

    async def start(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.context = await self.browser.new_context(viewport=VIEWPORTS[self.viewport], service_workers="block")
        await self.context.add_cookies([{"name": "everyday-language", "value": self.language, "url": self.args.base_url}])
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(10000)
        self.page.on("pageerror", lambda error: self.errors.append({"type": "pageerror", "message": str(error)}))
        self.page.on("console", lambda message: self.errors.append({
            "type": "console", "message": message.text, "url": message.location.get("url", "")
        }) if message.type == "error" else None)
        self.page.on("response", lambda response: self.events.append({
            "method": response.request.method, "url": response.url, "status": response.status
        }) if "/api/" in response.url else None)
        return self

    def text(self, english, french):
        return french if self.language == "fr" else english

    async def open(self, path):
        response = await self.page.goto(self.args.base_url + path, wait_until="load")
        assert response is not None and response.status == 200, (path, response.status if response else None)
        await expect(self.page.locator("main")).to_be_visible()

    async def api(self, path, method="GET", data=None, expected=200, origin=None, context=None):
        headers = {"Origin": origin or self.args.base_url}
        if origin and origin != self.args.base_url:
            headers["Connection"] = "close"
        response = await (context or self.context).request.fetch(self.args.base_url + path, method=method, data=data, headers=headers)
        self.events.append({"method": method, "url": response.url, "status": response.status, "api_client": True})
        assert response.status == expected, (path, method, response.status, await response.text())
        return await response.json()

    async def catalog(self, **criteria):
        return await self.api("/api/products?" + urlencode(criteria))

    async def all_products(self, **criteria):
        first = await self.catalog(**criteria)
        rows = list(first["items"])
        for page in range(2, first["totalPages"] + 1):
            data = await self.catalog(**{**criteria, "page": page})
            rows.extend(data["items"])
        assert len(rows) == first["total"]
        return rows

    async def cart(self):
        return (await self.api("/api/shop"))["items"]

    def allow_diagnostic(self, url, pattern):
        self.expected_diagnostics.append({"url": url, "pattern": pattern})

    def check_errors(self):
        unexpected = []
        for error in self.errors:
            if error["type"] == "pageerror":
                unexpected.append(error)
            elif urlparse(error.get("url", "")).path == "/favicon.ico":
                continue
            elif not any(error.get("url") == item["url"] and re.fullmatch(item["pattern"], error["message"])
                         for item in self.expected_diagnostics):
                unexpected.append(error)
        assert not unexpected, f"Unexpected browser diagnostics: {unexpected}"

    async def finish(self, record):
        try:
            await self.page.screenshot(path=str(self.folder / "screenshot.png"), full_page=True, animations="disabled")
            snapshot = await self.page.locator("body").aria_snapshot()
            (self.folder / "accessibility.txt").write_text(snapshot, encoding="utf-8")
        except Exception as error:
            record["capture_error"] = redact_text(repr(error))
        finally:
            await self.context.tracing.stop(path=str(self.folder / "trace.zip"))
            await self.context.close()
            redact_trace(self.folder / "trace.zip")
        record.update({"events": self.events, "browser_errors": self.errors,
                       "expected_diagnostics": self.expected_diagnostics,
                       "trace": str(self.folder / "trace.zip"),
                       "screenshot": str(self.folder / "screenshot.png")})
        (self.folder / "evidence.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


async def api_legacy_catalog(s):
    rows = await s.all_products()
    assert len(rows) == 43 and len({p["id"] for p in rows}) == 43
    for product in rows:
        assert isinstance(product["stock"], int) and product["stock"] >= 0
        assert product["images"] and product["image"] == product["images"][0]
    for product_id, (name, price, category) in LEGACY.items():
        product = next(p for p in rows if p["id"] == product_id)
        assert (product["name"], product["price"], product["category"], product["image"]) == (
            name, price, category, f"/products/{product_id}.webp")


async def api_search_localization(s):
    groups = [await s.all_products(q=query) for query in ("plant", "PLANT", "  plant  ")]
    assert [p["id"] for p in groups[0]] == [p["id"] for p in groups[1]] == [p["id"] for p in groups[2]]
    assert {45, 46}.issubset({p["id"] for p in groups[0]})
    french = await s.all_products(q="plante", lang="fr")
    assert 45 in {p["id"] for p in french}
    assert (await s.catalog(q="notarealproduct"))["total"] == 0


async def api_and_filters(s):
    rows = await s.all_products()
    filtered = await s.all_products(category="Home", minPrice=700, maxPrice=2200, inStock="true", rating=4)
    expected = {p["id"] for p in rows if p["category"] == "Home" and 700 <= p["price"] <= 2200
                and p["stock"] > 0 and p["rating"] >= 4}
    assert {p["id"] for p in filtered} == expected
    assert all(p["stock"] > 0 for p in await s.all_products(inStock="true"))
    exact = await s.all_products(minPrice=1499, maxPrice=1499)
    assert 46 in {p["id"] for p in exact} and all(p["price"] == 1499 for p in exact)


async def api_sort_pagination(s):
    for sort, sign in (("price-asc", 1), ("price-desc", -1)):
        rows = await s.all_products(sort=sort)
        assert rows == sorted(rows, key=lambda p: (sign * p["price"], p["id"]))
    first, last, outside = await s.catalog(page=1), await s.catalog(page=5), await s.catalog(page=999)
    assert first["total"] == 43 and first["pageSize"] == 10 and len(first["items"]) == 10
    assert last["totalPages"] == 5 and len(last["items"]) == 3
    assert outside["page"] == 5 and [p["id"] for p in outside["items"]] == [p["id"] for p in last["items"]]


async def api_invalid_queries(s):
    data = await s.api("/api/products?minPrice=2000&maxPrice=1000", expected=400)
    assert data.get("error")
    empty = await s.catalog(q="notarealproduct", page=999)
    assert empty["total"] == 0 and empty["items"] == []


async def api_detail_contract(s):
    for product_id, (name, price, category) in LEGACY.items():
        data = await s.api(f"/api/products/{product_id}")
        product = data["product"]
        assert (product["id"], product["name"], product["price"], product["category"]) == (product_id, name, price, category)
        assert all(item["id"] != product_id for item in data["related"])
    assert (await s.api("/api/products/99999", expected=404)).get("error")
    assert (await s.api("/api/products/not-a-number", expected=404)).get("error")


async def api_stock_price_writes(s):
    assert await s.cart() == []
    for payload in ({"product": 202, "qty": 1}, {"product": 201, "qty": 11},
                    {"product": 46, "qty": 1, "expectedPrice": 1498}):
        if payload["product"] == 201:
            product = (await s.api("/api/products/201"))["product"]
            payload["qty"] = min(10, product["stock"]) + 1
        data = await s.api("/api/shop", "POST", payload, expected=409)
        assert data.get("error") and await s.cart() == []
    for invalid in (-1, 1.5, "2", 11):
        await s.api("/api/shop", "POST", {"product": 46, "qty": invalid}, expected=400)
        assert await s.cart() == []
    for _ in range(2):
        await s.api("/api/shop", "POST", {"product": 46, "qty": 2, "expectedPrice": 1499})
        assert await s.cart() == [{"product": 46, "qty": 2}]
    await s.api("/api/shop", "POST", {"product": 46, "qty": 0})
    assert await s.cart() == []


async def api_origin_and_empty_checkout(s):
    assert await s.cart() == []
    data = {"action": "checkout", "address": {"name": "Test Shopper", "email": "test@example.com",
            "street": "123 Demo Street", "city": "Bengaluru", "pin": "560001"}, "paymentMethod": "card"}
    await s.api("/api/shop", "POST", data, expected=400)
    with sqlite3.connect(s.args.database_file) as connection:
        cart_before = connection.execute("SELECT user,product,qty FROM cart ORDER BY user,product").fetchall()
    rejected_context = await s.browser.new_context(service_workers="block")
    try:
        await s.api("/api/shop", "POST", {"product": 46, "qty": 1}, expected=403,
                    origin="https://wrong.example", context=rejected_context)
    finally:
        await rejected_context.close()
    with sqlite3.connect(s.args.database_file) as connection:
        cart_after = connection.execute("SELECT user,product,qty FROM cart ORDER BY user,product").fetchall()
    assert cart_after == cart_before, "Wrong-Origin request mutated the disposable D1 cart"


async def api_checkout_stock_revalidation(s):
    database=s.args.database_file
    assert database and database.is_file() and database.resolve().is_relative_to((ROOT/".sites-runtime").resolve()), "Disposable local D1 fixture file is required"
    assert await s.cart()==[]
    cookies=await s.context.cookies(s.args.base_url)
    token=next(cookie["value"] for cookie in cookies if cookie["name"]=="__Host-everyday-guest")
    user="guest:"+token
    payload={"action":"checkout","address":{"name":"Test Shopper","email":"test@example.com","street":"123 Demo Street","city":"Bengaluru","pin":"560001"},"paymentMethod":"card"}
    for product,quantity in ((202,1),(201,3),(99999,1)):
        with sqlite3.connect(database,timeout=5) as connection:
            before=connection.execute('SELECT count(*) FROM orders WHERE user=?',(user,)).fetchone()[0]
            connection.execute('INSERT INTO cart (user,product,qty) VALUES (?,?,?)',(user,product,quantity))
        try:
            await s.api('/api/shop','POST',payload,expected=409)
            assert await s.cart()==[{"product":product,"qty":quantity}]
            with sqlite3.connect(database,timeout=5) as connection:
                assert connection.execute('SELECT count(*) FROM orders WHERE user=?',(user,)).fetchone()[0]==before
        finally:
            with sqlite3.connect(database,timeout=5) as connection:
                connection.execute('DELETE FROM cart WHERE user=?',(user,))


async def ui_catalog_filters(s):
    await s.open("/products")
    await expect(s.page.locator(".product-card")).to_have_count(10)
    await s.page.locator('select[name="category"]').select_option("Home")
    await s.page.locator('input[name="minPrice"]').fill("700")
    await s.page.locator('input[name="maxPrice"]').fill("2200")
    await s.page.locator('input[name="inStock"]').check()
    await s.page.locator('select[name="sort"]').select_option("price-asc")
    await s.page.get_by_role("button", name=s.text("Apply filters", "Appliquer les filtres"), exact=True).click()
    await expect(s.page).to_have_url(re.compile(r"minPrice=700"))
    await expect(s.page.locator(".product-card").first).to_be_visible()
    await s.page.reload()
    await expect(s.page.locator('input[name="minPrice"]')).to_have_value("700")
    await expect(s.page.locator('select[name="category"]')).to_have_value("Home")
    expected = await s.all_products(category="Home", minPrice=700, maxPrice=2200, inStock="true", sort="price-asc")
    cards = s.page.locator(".product-card")
    assert await cards.count() == min(10, len(expected))
    ids = await cards.locator('a.photo').evaluate_all("links => links.map(a=>Number(a.getAttribute('href').split('/').pop()))")
    assert ids == [p["id"] for p in expected[:10]]
    await s.page.get_by_role("link", name=s.text("Reset filters", "Réinitialiser les filtres"), exact=True).click()
    await expect(s.page.locator(".product-card")).to_have_count(10)


async def ui_pagination(s):
    await s.open("/products?sort=price-desc")
    await expect(s.page.locator(".product-card")).to_have_count(10)
    first = await s.page.locator('.product-card a.photo').first.get_attribute("href")
    await s.page.get_by_role("link", name=s.text("Next page", "Page suivante"), exact=True).click()
    await expect(s.page).to_have_url(re.compile(r"page=2"))
    await expect(s.page.locator(".product-card")).to_have_count(10)
    assert await s.page.locator('.product-card a.photo').first.get_attribute("href") != first
    await s.page.reload()
    await expect(s.page).to_have_url(re.compile(r"page=2"))
    await s.page.go_back()
    await expect(s.page).to_have_url(re.compile(r"sort=price-desc"))
    await s.open("/products?page=5")
    await expect(s.page.locator(".product-card")).to_have_count(3)
    await s.open("/products?q=notarealproduct")
    await expect(s.page.locator(".empty")).to_be_visible()
    await expect(s.page.get_by_role("link", name=s.text("Reset filters", "Réinitialiser les filtres"), exact=True).first).to_be_visible()


async def ui_product_quantity(s):
    await s.open("/products/46")
    await expect(s.page.get_by_role("heading", name=s.text("Plant Pot", "Pot de fleurs"), exact=True)).to_be_visible()
    quantity = s.page.get_by_label(s.text("Quantity", "Quantité"), exact=True)
    await expect(quantity).to_have_value("1")
    await expect(s.page.get_by_role("button", name=s.text("Decrease quantity", "Diminuer la quantité"), exact=True)).to_be_disabled()
    await quantity.fill("3")
    await s.page.get_by_role("button", name=s.text("Add to cart", "Ajouter au panier"), exact=True).click()
    await expect(s.page.locator("header .cart-count")).to_have_text("3")
    assert await s.cart() == [{"product": 46, "qty": 3}]
    await quantity.fill("2")
    await s.page.get_by_role("button", name=s.text("Add to cart", "Ajouter au panier"), exact=True).click()
    await expect(s.page.locator("header .cart-count")).to_have_text("5")
    assert await s.cart() == [{"product": 46, "qty": 5}]
    await s.page.locator('header a[href="/cart"]').click()
    await expect(s.page.locator(".cart-row")).to_have_count(1)
    await expect(s.page.locator(".summary .total")).to_contain_text("₹7,495")
    await s.api("/api/shop", "POST", {"product": 46, "qty": 0})


async def ui_media_stock_variants(s):
    await s.open("/products/46")
    gallery = s.page.get_by_role("button", name=s.text("View image 2", "Voir l’image 2"), exact=True)
    await gallery.focus()
    await s.page.keyboard.press("Enter")
    await expect(gallery).to_have_attribute("aria-pressed", "true")
    zoom = s.page.get_by_role("button", name=s.text("Zoom image", "Agrandir l’image"), exact=True)
    await zoom.click()
    await expect(s.page.get_by_role("dialog")).to_be_visible()
    await s.page.keyboard.press("Escape")
    await expect(s.page.get_by_role("dialog")).not_to_be_visible()
    await expect(zoom).to_be_focused()
    detail = await s.api("/api/products/200")
    await s.open("/products/200")
    if detail["product"].get("variantGroup"):
        all_rows = await s.all_products()
        siblings = [p for p in all_rows if p.get("variantGroup") == detail["product"]["variantGroup"] and p["id"] != 200]
        assert siblings, "Expected seeded variant siblings"
        link = s.page.locator(f'main a[href="/products/{siblings[0]["id"]}"]').first
        await link.click()
        await expect(s.page).to_have_url(s.args.base_url + f'/products/{siblings[0]["id"]}')
        await s.page.get_by_role("button", name=s.text("Add to cart", "Ajouter au panier"), exact=True).click()
        await expect(s.page.locator("header .cart-count")).to_have_text("1")
        assert await s.cart() == [{"product": siblings[0]["id"], "qty": 1}]
        await s.api("/api/shop", "POST", {"product": siblings[0]["id"], "qty": 0})
    await s.open("/products/202")
    await expect(s.page.locator(".detail-add")).to_be_disabled()
    await expect(s.page.locator(".detail-add")).to_have_text(s.text("Out of stock", "Rupture de stock"))
    await s.open("/products/201")
    data = (await s.api("/api/products/201"))["product"]
    quantity = s.page.get_by_label(s.text("Quantity", "Quantité"), exact=True)
    assert int(await quantity.get_attribute("max")) == min(10, data["stock"])
    s.allow_diagnostic(s.args.base_url + "/api/products/99999", r"Failed to load resource: the server responded with a status of 404 \(Not Found\)")
    await s.open("/products/99999")
    await expect(s.page.get_by_role("heading", name=s.text("Product not found", "Produit introuvable"), exact=True)).to_be_visible()


async def ui_autocomplete(s):
    await s.open("/products")
    search = s.page.locator('header input[name="q"]')
    await search.fill("plant" if s.language == "en" else "plante")
    await expect(search).to_have_attribute("aria-expanded", "true")
    list_id = await search.get_attribute("aria-controls")
    assert list_id and await s.page.locator(f'[id="{list_id}"]').count() == 1
    await search.press("ArrowDown")
    selected = await search.get_attribute("aria-activedescendant")
    assert selected
    option = s.page.locator(f'[id="{selected}"]')
    await expect(option).to_have_attribute("aria-selected", "true")
    href = await option.get_attribute("href")
    await search.press("Enter")
    await expect(s.page).to_have_url(s.args.base_url + href)
    await s.open('/products')
    search=s.page.locator('header input[name="q"]')
    await search.fill('plant')
    await expect(search).to_have_attribute('aria-expanded','true')
    await search.fill('notarealproduct')
    await search.press('ArrowDown')
    await expect(s.page.get_by_text(s.text('No quick matches','Aucun résultat rapide'),exact=True)).to_be_visible()
    assert await search.get_attribute('aria-activedescendant') is None


async def ui_catalog_loading_recovery(s):
    mode, started, release = "hold", asyncio.Event(), asyncio.Event()
    real = await s.catalog()
    async def mock(route):
        nonlocal mode
        if urlparse(route.request.url).path != "/api/products":
            await route.fallback()
            return
        if mode == "hold":
            started.set()
            await release.wait()
            s.allow_diagnostic(route.request.url, r"Failed to load resource: the server responded with a status of 500 \(Internal Server Error\)")
            await route.fulfill(status=500, json={"error": "Deliberate catalog failure"})
        elif mode == "malformed":
            await route.fulfill(json={"items": None})
        else:
            await route.fulfill(json=real)
    await s.context.route("**/api/products**", mock)
    await s.open("/products")
    await asyncio.wait_for(started.wait(), 10)
    await expect(s.page.get_by_role("status").filter(has_text=re.compile("Loading|Chargement", re.I))).to_be_visible()
    release.set()
    await expect(s.page.get_by_role("alert")).to_be_visible()
    mode = "malformed"
    await s.page.get_by_role("button", name="Try again", exact=True).click()
    await expect(s.page.get_by_role("alert")).to_be_visible()
    mode = "ready"
    await s.page.get_by_role("button", name="Try again", exact=True).click()
    await expect(s.page.locator(".product-card")).to_have_count(10)


async def ui_stale_price_conflict(s):
    await s.open("/products/46")
    async def conflict(route):
        if route.request.method == "POST":
            await route.fulfill(status=409, json={"error": "The price has changed. Please review it before adding.",
                "product":46,"currentPrice":1599,"availableStock":10,"maxQuantity":10})
        else:
            await route.fallback()
    await s.context.route("**/api/shop", conflict)
    s.allow_diagnostic(s.args.base_url + "/api/shop", r"Failed to load resource: the server responded with a status of 409 \(Conflict\)")
    await s.page.get_by_role("button", name="Add to cart", exact=True).click()
    await expect(s.page.get_by_role("alert")).to_contain_text(re.compile("price|review", re.I))
    await expect(s.page.locator("header .cart-count")).to_have_text("0")
    assert await s.cart() == []


async def ui_broken_image_fallback(s):
    async def break_image(route):
        await route.abort("failed")
    await s.context.route("**/products/46.webp", break_image)
    s.allow_diagnostic(s.args.base_url + "/products/46.webp", r"Failed to load resource: net::ERR_FAILED")
    await s.open("/products/46")
    await expect(s.page.locator('main img').first).to_have_attribute("src", re.compile("fallback"))
    assert await s.page.locator('main img').first.evaluate("image => image.complete && image.naturalWidth > 0")
    await expect(s.page.get_by_role("button", name="Add to cart", exact=True)).to_be_enabled()


async def ui_malformed_detail_recovery(s):
    mode = "malformed"
    real = await s.api("/api/products/46")
    async def mock(route):
        if mode == "malformed":
            await route.fulfill(json={"product": {"stock": 1, "images": []}, "related": [None]})
        elif mode == "bad-locale":
            await route.fulfill(json={"product":{**real["product"],"nameFr":{}},"related":real["related"]})
        else:
            await route.fulfill(json=real)
    await s.context.route("**/api/products/46", mock)
    await s.open("/products/46")
    await expect(s.page.get_by_role("alert")).to_be_visible()
    mode = "bad-locale"
    await s.page.get_by_role("button", name="Try again", exact=True).click()
    await expect(s.page.get_by_role("alert")).to_be_visible()
    mode = "ready"
    await s.page.get_by_role("button", name="Try again", exact=True).click()
    await expect(s.page.get_by_role("heading", name="Plant Pot", exact=True)).to_be_visible()


async def ui_french_invalid_range(s):
    await s.open('/products?minPrice=2000&maxPrice=1000')
    await expect(s.page.get_by_role('alert')).to_contain_text('Le prix minimum ne doit pas dépasser le prix maximum.')


API_CASES = [api_legacy_catalog, api_search_localization, api_and_filters, api_sort_pagination,
             api_invalid_queries, api_detail_contract, api_stock_price_writes, api_checkout_stock_revalidation]
MATRIX_CASES = [ui_catalog_filters, ui_pagination, ui_product_quantity, ui_media_stock_variants]


async def run(args):
    before = fingerprint()
    records = []
    cases = [(fn, "en", "desktop") for fn in API_CASES]
    cases += [(fn, lang, size) for lang in ("en", "fr") for size in VIEWPORTS for fn in MATRIX_CASES]
    cases += [(ui_autocomplete, lang, "desktop") for lang in ("en", "fr")]
    cases += [(fn, "en", "desktop") for fn in (ui_catalog_loading_recovery, ui_stale_price_conflict, ui_broken_image_fallback, ui_malformed_detail_recovery)]
    cases += [(ui_french_invalid_range, "fr", "desktop")]
    cases += [(api_origin_and_empty_checkout, "en", "desktop")]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=args.browser_channel, headless=True)
        browser_version = browser.version
        for fn, language, viewport in cases:
            name = f"{fn.__name__}_{language}_{viewport}"
            if args.test and args.test not in (fn.__name__, name):
                continue
            started = time.monotonic()
            record = {"test": name, "language": language, "viewport": VIEWPORTS[viewport]}
            session = await Session(args, browser, name, language, viewport).start()
            try:
                await fn(session)
                session.check_errors()
                record["status"] = "PASS"
            except Exception as error:
                record.update({"status": "FAIL", "error": redact_text(repr(error))})
            finally:
                record["seconds"] = round(time.monotonic() - started, 3)
                await session.finish(record)
                records.append(record)
                print(name, record["status"], flush=True)
        await browser.close()
    report = {"scope": "P0-02/03 local isolated API/browser acceptance, not production smoke or controlled A/B",
              "started_utc": args.started, "finished_utc": datetime.now(timezone.utc).isoformat(),
              "base_url": args.base_url, "browser_version": browser_version,
              "playwright_python_version": package_version("playwright"),
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "dirty_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
              "source_fingerprint": before, "source_unchanged_during_run": before == fingerprint(),
              "test_file_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "records": records, "tests_run": len(records),
              "passed": sum(r["status"] == "PASS" for r in records),
              "failed": sum(r["status"] != "PASS" for r in records)}
    (args.report_dir / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    xml = ET.Element("testsuite", name="p0-02-03-catalog-detail", tests=str(len(records)), failures=str(report["failed"]))
    for record in records:
        case = ET.SubElement(xml, "testcase", name=record["test"], time=str(record["seconds"]))
        if record["status"] != "PASS":
            ET.SubElement(case, "failure").text = record["error"]
    ET.ElementTree(xml).write(args.report_dir / "junit.xml", encoding="utf-8", xml_declaration=True)
    return int(report["failed"] > 0 or not report["source_unchanged_during_run"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--database-file",type=Path,help="Disposable local D1 SQLite fixture file under .sites-runtime")
    parser.add_argument("--test", help="One method or full matrix case name; no automatic retries")
    args = parser.parse_args()
    args.base_url = args.base_url.rstrip("/")
    if urlparse(args.base_url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("This writing suite only accepts a loopback disposable database target")
    args.report_dir = args.report_dir.resolve()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    args.started = datetime.now(timezone.utc).isoformat()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
