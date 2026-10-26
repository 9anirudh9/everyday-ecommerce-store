"""Controlled read-only A/B comparison for the P0-01 navigation/cart slice.

All browser /api requests are intercepted. The production cart/order API is never
called, and the only cart mutations here are in browser-local coupon state.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
LIVE_ORIGIN = "https://everyday-shop-anirudh.cidirianirudh.chatgpt.site"
LIVE_SHA = "4550358b96f0a26bd118d98e2e64eb956beaecbf"
LIVE_DEPLOYMENT = "appgdep_6ab4fff5b40c8191b3da9bb4752ebd8b"
FIXTURES = {
    "P0-01-empty-v1": {"items": []},
    "P0-01-43x2-46x3-v1": {"items": [{"product": 43, "qty": 2}, {"product": 46, "qty": 3}]},
}
VIEWPORTS = {"desktop": {"width": 1366, "height": 900}, "mobile": {"width": 390, "height": 844}}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


async def capture(browser, origin, role, fixture_name, language, viewport_name, folder):
    fixture = FIXTURES[fixture_name]
    context = await browser.new_context(viewport=VIEWPORTS[viewport_name], service_workers="block")
    await context.add_cookies([{"name": "everyday-language", "value": language, "url": origin}])
    await context.tracing.start(screenshots=True, snapshots=True, sources=True)
    events = []
    errors = []
    async def guard(route):
        request = route.request
        event = {"method": request.method, "url": request.url}
        events.append(event)
        if request.url == origin + "/api/shop" and request.method == "GET":
            await route.fulfill(json=fixture, headers={"Cache-Control": "private, no-store"})
        else:
            event["blocked"] = True
            await route.abort("blockedbyclient")
    await context.route("**/api/**", guard)
    page = await context.new_page()
    page.set_default_timeout(12000)
    page.on("pageerror", lambda error: errors.append({"type": "pageerror", "message": str(error)}))
    page.on("console", lambda message: errors.append({"type": "console", "message": message.text, "url": message.location.get("url", "")}) if message.type == "error" else None)
    count = sum(item["qty"] for item in fixture["items"])
    folder.mkdir(parents=True, exist_ok=True)
    pages = []
    seen_paths = {}

    async def record(path, action=None):
        if action:
            await action()
            await expect(page).to_have_url(origin + path)
            response_status = 200 if page.url == origin + path else None
        else:
            response = await page.goto(origin + path, wait_until="load")
            response_status = response.status if response else None
        await expect(page.locator("main")).to_be_visible()
        if role == "B":
            await expect(page.locator("header .cart-count")).to_have_text(str(count))
        if path in ("/cart", "/checkout"):
            if fixture["items"]:
                await expect(page.locator(".cart-row" if path == "/cart" else ".checkout-grid").first).to_be_visible()
            else:
                await expect(page.locator(".empty")).to_be_visible()
        elif path == "/products/46":
            await expect(page.locator("main .detail-copy button")).to_be_enabled()
        else:
            add_buttons = page.locator("main .product-card button")
            if await add_buttons.count():
                await expect(add_buttons.first).to_be_enabled()
        # Full-page screenshots do not trigger every lazy product image.
        # Decode the same main-content images on both revisions first.
        await page.evaluate("""async () => {
          const images = Array.from(document.querySelectorAll('main img'));
          for (const img of images) {
            img.loading = 'eager';
            await img.decode().catch(() => {});
          }
        }""")
        # A prior click can leave different hover/focus states on the two
        # origins even when their static page rendering is equivalent.
        await page.mouse.move(0, 0)
        await page.evaluate("document.activeElement?.blur()")
        slug = {"/":"home","/products":"products","/accessories":"accessories","/products/46":"product46",
                "/search?q=plant":"search","/search?q=plante":"search","/cart":"cart","/checkout":"checkout"}[path]
        seen_paths[slug] = seen_paths.get(slug, 0) + 1
        if seen_paths[slug] > 1:
            slug += f"-{seen_paths[slug]}"
        image_path = folder / (slug + ".png")
        main_image_path = folder / (slug + "-main.png")
        await page.screenshot(path=str(image_path), full_page=True, animations="disabled")
        await page.locator("main").screenshot(path=str(main_image_path), animations="disabled")
        frame = await page.evaluate("""() => {
          const cart = document.querySelector('header a[href="/cart"]');
          const r = cart.getBoundingClientRect();
          return {title:document.title, lang:document.documentElement.lang,
            links:Array.from(document.querySelectorAll('header nav a')).map(a=>({href:a.getAttribute('href'),text:a.textContent.trim(),current:a.getAttribute('aria-current')})),
            logo:document.querySelector('header a.logo')?.getAttribute('href'),
            cart:{href:cart.getAttribute('href'),label:cart.getAttribute('aria-label'),current:cart.getAttribute('aria-current'),
              width:r.width,height:r.height,count:cart.querySelector('.cart-count')?.textContent?.trim()??null},
            main:document.querySelector('main')?.innerText??'',
            cartRows:Array.from(document.querySelectorAll('.cart-row')).map(e=>e.innerText)};
        }""")
        snapshot = await page.locator("body").aria_snapshot()
        (folder / (slug + "-accessibility.txt")).write_text(snapshot, encoding="utf-8")
        pages.append({"path": path, "status": response_status, "main": normalized(frame["main"]),
                      "main_sha256": digest(main_image_path), "screenshot": str(image_path),
                      "accessibility": str(folder/(slug+"-accessibility.txt")), "frame": frame})

    try:
        await record("/")
        await record("/products", lambda: page.locator('header nav a[href="/products"]').click())
        await record("/accessories", lambda: page.locator('header nav a[href="/accessories"]').click())
        await record("/products/46")
        await record("/products", lambda: page.locator('.breadcrumb a[href="/products"]').click())
        query = "plante" if language == "fr" else "plant"
        await record("/search?q=" + query)
        await record("/cart", lambda: page.locator('header a[href="/cart"]').click())
        if fixture["items"]:
            # Browser-local coupon only. No POST and no real production cart.
            await page.locator("#coupon").fill("EVERYDAY")
            await page.locator(".coupon-form button[type='submit']").click()
            await expect(page.locator(".summary")).to_contain_text("₹3,147")
            await record("/checkout", lambda: page.locator('.summary a[href="/checkout"]').click())
        await page.locator("header a.logo").click()
        await expect(page).to_have_url(origin + "/")
        results = {"role": role, "origin": origin, "fixture": fixture_name, "language": language,
                   "viewport": viewport_name, "browser": browser.version, "pages": pages, "api_events": events,
                   "errors": errors, "logo_returned_home": page.url == origin + "/"}
    except Exception as exc:
        results = {"role": role, "origin": origin, "fixture": fixture_name, "language": language,
                   "viewport": viewport_name, "browser": browser.version, "pages": pages, "api_events": events,
                   "errors": errors, "exception": repr(exc)}
    finally:
        await context.tracing.stop(path=str(folder / "trace.zip"))
        await context.close()
    (folder / "result.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def compare(a, b):
    findings = []
    if a.get("exception") or b.get("exception"):
        return {"status": "INCONCLUSIVE", "findings": ["Execution exception on A or B"]}
    if any(e.get("blocked") for side in (a, b) for e in side["api_events"]):
        return {"status": "REGRESSION", "findings": ["Unexpected API call aborted"]}
    if any(e["method"] != "GET" for side in (a, b) for e in side["api_events"]):
        return {"status": "REGRESSION", "findings": ["Write request attempted"]}
    if len(a["pages"]) != len(b["pages"]):
        return {"status": "INCONCLUSIVE", "findings": ["Page capture count differs"]}
    total = sum(item["qty"] for item in FIXTURES[a["fixture"]]["items"])
    for old, new in zip(a["pages"], b["pages"]):
        path = old["path"]
        if old["path"] != new["path"] or old["status"] != 200 or new["status"] != 200:
            findings.append({"path": path, "type": "REGRESSION", "detail": "Route/status mismatch"})
        if old["main"] != new["main"]:
            findings.append({"path": path, "type": "REGRESSION", "detail": "Main content text changed"})
        if old["main_sha256"] != new["main_sha256"]:
            findings.append({"path": path, "type": "VISUAL_REVIEW", "detail": "Main screenshot differs; inspect paired images"})
        for field in ("logo",):
            if old["frame"][field] != new["frame"][field]:
                findings.append({"path": path, "type": "REGRESSION", "detail": f"{field} changed"})
        if [x["href"] for x in old["frame"]["links"]] != [x["href"] for x in new["frame"]["links"]]:
            findings.append({"path": path, "type": "REGRESSION", "detail": "Header nav target changed"})
        if old["frame"]["cart"]["href"] != new["frame"]["cart"]["href"]:
            findings.append({"path": path, "type": "REGRESSION", "detail": "Cart target changed"})
        if new["frame"]["cart"]["count"] != str(total):
            findings.append({"path": path, "type": "REGRESSION", "detail": "New badge count wrong"})
        if new["frame"]["cart"]["width"] < 44 or new["frame"]["cart"]["height"] < 44:
            findings.append({"path": path, "type": "REGRESSION", "detail": "Cart hit target under 44px"})
        if path == "/cart" and total:
            if len(old["frame"]["cartRows"]) != 2 or len(new["frame"]["cartRows"]) != 2:
                findings.append({"path": path, "type": "REGRESSION", "detail": "Cart row count mismatch"})
            if "₹6,295" not in old["main"] or "₹6,295" not in new["main"]:
                findings.append({"path": path, "type": "REGRESSION", "detail": "Known mixed subtotal missing"})
    old_errors=[(e["type"],e["message"]) for e in a["errors"]]
    new_errors=[(e["type"],e["message"]) for e in b["errors"]]
    for error in new_errors:
        if error not in old_errors:
            findings.append({"type":"REGRESSION","detail":f"New browser error: {error}"})
    if old_errors and old_errors == new_errors:
        findings.append({"type":"BASELINE_DEFECT","detail":f"Common browser errors: {old_errors}"})
    if any(f["type"] in ("REGRESSION", "VISUAL_REVIEW") for f in findings):
        status = "REGRESSION" if any(f["type"] == "REGRESSION" for f in findings) else "INCONCLUSIVE"
    else:
        status = "PASS"
    return {"status": status, "findings": findings, "intentional_changes": ["B adds active-navigation styling/aria-current", "B adds cart quantity badge"]}


async def run(args):
    args.report_dir.mkdir(parents=True, exist_ok=True)
    fixture_bytes={name:json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode() for name,value in FIXTURES.items()}
    fixture_meta={name:{"json":value,"sha256":hashlib.sha256(data).hexdigest()} for name,(value,data) in ((n,(FIXTURES[n],b)) for n,b in fixture_bytes.items())}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        cases=[]
        for fixture,language,viewport in product(FIXTURES,("en","fr"),VIEWPORTS):
            name=f"{fixture}_{language}_{viewport}"
            if args.case and name not in args.case:
                continue
            if args.max_cases and len(cases)>=args.max_cases:
                break
            a=await capture(browser, LIVE_ORIGIN, "A", fixture, language, viewport, args.report_dir/name/"A")
            b=await capture(browser, args.candidate_url, "B", fixture, language, viewport, args.report_dir/name/"B")
            comparison=compare(a,b)
            cases.append({"name":name,"comparison":comparison,"a":str(args.report_dir/name/"A/result.json"),"b":str(args.report_dir/name/"B/result.json")})
            print(f"{name}: {comparison['status']}", flush=True)
        await browser.close()
    report={"started_utc":args.started,"finished_utc":datetime.now(timezone.utc).isoformat(),"baseline":{
      "url":LIVE_ORIGIN,"sites_version":9,"source_sha":LIVE_SHA,"deployment_id":LIVE_DEPLOYMENT},
      "candidate":{"url":args.candidate_url,"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                   "dirty_status":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True),
                   "source_fingerprint":json.loads((ROOT/"outputs/p0-01-browser/candidate-2/results.json").read_text(encoding="utf-8"))["source_fingerprint"]["sha256"]},
      "fixtures":fixture_meta,"browser_channel":"chrome","viewports":VIEWPORTS,"cases":cases,
      "counts":{status:sum(c["comparison"]["status"]==status for c in cases) for status in ("PASS","REGRESSION","INCONCLUSIVE")},
      "scope":"Matched browser GET mock comparison. No production POST, real D1, random traffic or post-deployment smoke."}
    (args.report_dir/"comparison.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return 0 if report["counts"]["REGRESSION"]==report["counts"]["INCONCLUSIVE"]==0 else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-url",default="http://127.0.0.1:8787")
    parser.add_argument("--report-dir",required=True,type=Path)
    parser.add_argument("--max-cases",type=int,help="Focused diagnostic only; full comparison omits this flag")
    parser.add_argument("--case",action="append",help="Run one named matrix cell; repeat for focused retries")
    args=parser.parse_args()
    args.candidate_url=args.candidate_url.rstrip("/")
    if urlparse(args.candidate_url).hostname not in ("127.0.0.1","localhost","::1"):
        parser.error("Candidate must be loopback; baseline is pinned by script")
    args.report_dir=args.report_dir.resolve()
    args.started=datetime.now(timezone.utc).isoformat()
    return asyncio.run(run(args))


if __name__=="__main__":
    sys.exit(main())
