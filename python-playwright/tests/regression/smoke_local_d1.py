"""Stateful local-only cart/checkout smoke against disposable Wrangler D1."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

ROOT=Path(__file__).resolve().parents[3]


async def run(args):
    args.report_dir.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat()
    evidence={"scope":"local disposable D1 E2E, never production post-deployment smoke",
              "url":args.base_url,"started_utc":started,"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
              "source_fingerprint":json.loads((ROOT/"outputs/p0-01-browser/candidate-2/results.json").read_text(encoding="utf-8"))["source_fingerprint"]["sha256"],
              "checks":[],"api_responses":[],"errors":[]}
    def check(label,detail=None):
        evidence["checks"].append({"name":label,"status":"PASS","detail":detail})
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(channel="chrome",headless=True)
        evidence["browser_version"]=browser.version
        context_a=await browser.new_context(viewport={"width":1366,"height":900},service_workers="block")
        context_b=await browser.new_context(viewport={"width":1366,"height":900},service_workers="block")
        for context in (context_a,context_b):
            await context.add_cookies([{"name":"everyday-language","value":"en","url":args.base_url}])
            await context.tracing.start(screenshots=True,snapshots=True,sources=True)
        page_a=await context_a.new_page()
        page_b=await context_b.new_page()
        for page in (page_a,page_b):
            page.set_default_timeout(12000)
            page.on("pageerror",lambda error:evidence["errors"].append({"type":"pageerror","message":str(error)}))
            page.on("console",lambda message:evidence["errors"].append({"type":"console","message":message.text,"url":message.location.get("url","")}) if message.type=="error" else None)
            page.on("response",lambda response:evidence["api_responses"].append({"method":response.request.method,"status":response.status,"url":response.url}) if urlparse(response.url).path=="/api/shop" else None)
        error=None
        try:
            response=await page_a.goto(args.base_url+"/products/46")
            assert response.status==200
            await expect(page_a.locator("header .cart-count")).to_have_text("0")
            await expect(page_a.get_by_role("heading",name="Plant Pot",exact=True)).to_be_visible()
            await expect(page_a.get_by_text("₹1,499",exact=True)).to_be_visible()
            check("empty guest A and product 46/price")
            await page_a.get_by_role("button",name="Add to cart",exact=True).click()
            await expect(page_a.locator("header .cart-count")).to_have_text("1")
            await page_a.locator('header a[href="/cart"]').click()
            await expect(page_a).to_have_url(args.base_url+"/cart")
            await expect(page_a.locator(".cart-row")).to_have_count(1)
            await expect(page_a.locator(".summary .total")).to_contain_text("₹1,499")
            check("real API add, cart row, full-document navigation")
            await page_a.locator("#coupon").fill("EVERYDAY")
            await page_a.locator(".coupon-form button[type='submit']").click()
            await expect(page_a.locator(".summary .total")).to_contain_text("₹749")
            check("legacy 50% rounded discount",{"subtotal":1499,"discount":750,"total":749})
            response=await page_b.goto(args.base_url+"/cart")
            assert response.status==200
            await expect(page_b.locator("header .cart-count")).to_have_text("0")
            await expect(page_b.locator(".empty")).to_be_visible()
            cookies_a=await context_a.cookies(args.base_url)
            cookies_b=await context_b.cookies(args.base_url)
            def guest(cookies):
                return next((cookie for cookie in cookies if cookie["name"]=="__Host-everyday-guest"),None)
            first,second=guest(cookies_a),guest(cookies_b)
            assert first and second and first["value"]!=second["value"]
            assert all(c["httpOnly"] and c["secure"] and c["path"]=="/" for c in (first,second))
            check("separate guest sessions",{"cookies_distinct":True,"http_only":True,"secure":True})
            await page_a.locator('.summary a[href="/checkout"]').click()
            await expect(page_a).to_have_url(args.base_url+"/checkout")
            await expect(page_a.locator(".summary .total")).to_contain_text("₹749")
            for label,value in (("Full name","Test Shopper"),("Email address","test.shopper@example.com"),
                                ("Street address","123 Demo Street"),("City","Bengaluru"),("PIN code","560001")):
                await page_a.get_by_label(label,exact=True).fill(value)
            await page_a.get_by_role("button",name="Continue to payment").click()
            for label,value in (("Name on card","Test Shopper"),("Card number","4242 4242 4242 4242"),
                                ("Expiry","0133"),("CVV","123")):
                await page_a.get_by_label(label,exact=True).fill(value)
            await expect(page_a.locator("#expiry")).to_have_value("01/33")
            await page_a.get_by_role("button",name="Review order").click()
            await expect(page_a.get_by_role("heading",name="Confirm your order")).to_be_visible()
            await page_a.get_by_role("button",name="Confirm and place order").click()
            await expect(page_a.get_by_role("heading",name="Thanks for shopping.")).to_be_visible()
            await expect(page_a.locator("header .cart-count")).to_have_text("0")
            check("real local D1 demo checkout and cart clear")
            await page_a.goto(args.base_url+"/cart")
            await expect(page_a.locator(".empty")).to_be_visible()
            await page_b.reload()
            await expect(page_b.locator(".empty")).to_be_visible()
            check("persisted cart clear and guest B unaffected")
            unexpected=[entry for entry in evidence["errors"] if entry.get("type")=="pageerror" or not entry.get("url","").endswith("/favicon.ico")]
            assert not unexpected, f"Unexpected browser errors: {unexpected}"
            assert all(entry["status"]==200 for entry in evidence["api_responses"])
            check("API responses and browser diagnostics",{"unexpected_errors":0,"api_responses":len(evidence["api_responses"])})
        except Exception as exc:
            error=repr(exc)
            evidence["checks"].append({"name":"smoke execution","status":"FAIL","detail":error})
        finally:
            for name,context,page in (("A",context_a,page_a),("B",context_b,page_b)):
                try:
                    await page.screenshot(path=str(args.report_dir/f"guest-{name}.png"),full_page=True)
                    await context.tracing.stop(path=str(args.report_dir/f"guest-{name}-trace.zip"))
                finally:
                    await context.close()
            await browser.close()
    evidence["finished_utc"]=datetime.now(timezone.utc).isoformat()
    evidence["verdict"]="PASS" if error is None else "FAIL"
    (args.report_dir/"smoke-result.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"{evidence['verdict']}: {len([c for c in evidence['checks'] if c['status']=='PASS'])} checks; {args.report_dir}")
    if error: print(error)
    return 0 if error is None else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:8787")
    parser.add_argument("--report-dir",required=True,type=Path)
    args=parser.parse_args()
    args.base_url=args.base_url.rstrip("/")
    if urlparse(args.base_url).hostname not in ("127.0.0.1","localhost","::1"):
        parser.error("Only loopback isolated D1 is allowed")
    args.report_dir=args.report_dir.resolve()
    return asyncio.run(run(args))


if __name__=="__main__":
    sys.exit(main())
