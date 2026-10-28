"""Controlled, read-only P0-02/03 legacy-compatibility comparison.

This is a paired browser regression comparison, not a traffic experiment. All
browser API writes are blocked; the API client below issues GET requests only.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode, urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "https://everyday-shop-anirudh.cidirianirudh.chatgpt.site"
BASELINE_SHA = "46ecbe70c664930fad3845cf4babc1baf66d838c"
LEGACY = {43,44,45,46,47,93,94,154,155,156,172,173,175}
VIEWPORTS = {"desktop":{"width":1366,"height":900}, "mobile":{"width":390,"height":844}}


def fingerprint():
    files = {}
    for folder in ("app", "lib", "components", "public/products"):
        for path in (ROOT/folder).rglob("*"):
            if path.is_file() and path.suffix in (".ts", ".tsx", ".css", ".svg"):
                files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"sha256":hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),"files":files}


async def capture(browser, origin, side, language, viewport, folder):
    folder.mkdir(parents=True,exist_ok=True)
    context = await browser.new_context(viewport=VIEWPORTS[viewport],service_workers="block")
    await context.add_cookies([{"name":"everyday-language","value":language,"url":origin}])
    await context.tracing.start(screenshots=True,snapshots=True,sources=True)
    page = await context.new_page()
    page.set_default_timeout(12000)
    result = {"side":side,"origin":origin,"language":language,"viewport":VIEWPORTS[viewport],
              "requests":[],"errors":[],"checks":[],"searches":{},"captures":[]}

    async def guard(route):
        request = route.request
        result["requests"].append({"method":request.method,"url":request.url})
        if request.method != "GET":
            await route.abort("blockedbyclient")
        else:
            await route.continue_()
    await context.route("**/api/**",guard)
    page.on("pageerror",lambda error:result["errors"].append({"type":"pageerror","message":str(error)}))
    page.on("console",lambda m:result["errors"].append({"type":"console","message":m.text,"url":m.location.get("url","")}) if m.type=="error" else None)

    async def ready_catalog():
        if side == "B":
            await expect(page.get_by_test_id("catalog-results")).to_be_visible()
        else:
            await expect(page.locator("main")).to_be_visible()

    async def visit(path):
        response=await page.goto(origin+path,wait_until="load")
        assert response and response.status==200,(path,response.status if response else None)
        await expect(page.locator("main")).to_be_visible()
        await expect(page.locator("header .cart-count")).to_have_text("0")
        result["checks"].append({"path":path,"status":"PASS"})

    async def screenshot(name):
        await page.mouse.move(0,0)
        await page.screenshot(path=str(folder/(name+".png")),full_page=True,animations="disabled")
        (folder/(name+"-accessibility.txt")).write_text(await page.locator("body").aria_snapshot(),encoding="utf-8")
        result["captures"].append(name)

    async def all_candidate_products(query=None):
        rows=[]
        params={"lang":language}
        if query is not None:params["q"]=query
        page_number=1
        while True:
            params["page"]=page_number
            response=await context.request.get(origin+"/api/products?"+urlencode(params))
            result["requests"].append({"method":"GET","url":response.url,"api_client":True,"status":response.status})
            assert response.status==200
            data=await response.json()
            rows.extend(data["items"])
            if page_number>=data["totalPages"]:break
            page_number+=1
        return rows

    try:
        await visit("/")
        result["header"]=await page.evaluate("""() => ({
          logo:document.querySelector('header a.logo').getAttribute('href'),
          links:Array.from(document.querySelectorAll('header nav a')).map(a=>a.getAttribute('href')),
          cart:document.querySelector('header a[href="/cart"]').getAttribute('href'),
          language:document.documentElement.lang})""")
        await screenshot("home")
        await page.locator('header nav a[href="/products"]').click()
        await expect(page).to_have_url(origin+"/products")
        await ready_catalog()
        catalog_ids=await page.locator('main .product-card a.photo').evaluate_all("links=>links.map(a=>Number(a.getAttribute('href').split('/').pop()))")
        if side=="A":
            assert set(catalog_ids)==LEGACY
            result["catalog_ids"]=catalog_ids
        else:
            rows=await all_candidate_products()
            result["catalog_ids"]=[p["id"] for p in rows]
            assert len(rows)==43 and len(catalog_ids)==10
            assert LEGACY.issubset(result["catalog_ids"])
        await screenshot("catalog")
        queries=["plant","PLANT","  plant  ","notarealproduct"]
        if language=="fr":queries.append("plante")
        for index,query in enumerate(queries):
            await visit("/search?"+urlencode({"q":query}))
            await ready_catalog()
            if side=="A":
                ids=await page.locator('main .product-card a.photo').evaluate_all("links=>links.map(a=>Number(a.getAttribute('href').split('/').pop()))")
            else:
                ids=[product["id"] for product in await all_candidate_products(query)]
            result["searches"][query]=sorted(set(ids)&LEGACY)
            if query=="notarealproduct":
                assert not ids
                await expect(page.locator(".empty")).to_be_visible()
            if index==0:await screenshot("search")
        await visit("/products/46")
        await expect(page.locator(".detail-copy h1")).to_have_text("Pot de fleurs" if language=="fr" else "Plant Pot")
        await expect(page.locator(".detail-copy .price")).to_have_text("\u20b91,499")
        result["product46"]={
            "name":await page.locator(".detail-copy h1").inner_text(),
            "category":await page.locator(".detail-copy .eyebrow").inner_text(),
            "price":await page.locator(".detail-copy .price").inner_text(),
            "image":await page.locator(".detail-photo img").get_attribute("src"),
        }
        if side=="B":
            await expect(page.get_by_label("Quantité" if language=="fr" else "Quantity",exact=True)).to_have_value("1")
            await expect(page.get_by_role("button",name="Voir l’image 2" if language=="fr" else "View image 2",exact=True)).to_be_visible()
        await screenshot("product46")
        await page.locator('.breadcrumb a[href="/products"]').click()
        await expect(page).to_have_url(origin+"/products")
        await ready_catalog()
        await page.locator('header a[href="/cart"]').click()
        await expect(page).to_have_url(origin+"/cart")
        await expect(page.locator(".empty")).to_be_visible()
        await expect(page.locator("header .cart-count")).to_have_text("0")
        await screenshot("cart")
        assert await page.locator("html").get_attribute("lang")==language
        await page.locator("header a.logo").click()
        await expect(page).to_have_url(origin+"/")
        assert all(event["method"]=="GET" for event in result["requests"])
        unexpected=[e for e in result["errors"] if e["type"]=="pageerror" or urlparse(e.get("url","")).path!="/favicon.ico"]
        assert not unexpected,unexpected
        result["status"]="PASS"
    except Exception as error:
        result["status"]="INCONCLUSIVE" if "ERR_CONNECTION_RESET" in str(error) else "FAIL"
        result["exception"]=repr(error)
    finally:
        await context.tracing.stop(path=str(folder/"trace.zip"))
        await context.close()
    (folder/"result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result


def compare(a,b):
    if a["status"]!="PASS" or b["status"]!="PASS":
        return {"status":"INCONCLUSIVE","findings":[{"side":r["side"],"exception":r.get("exception")} for r in (a,b) if r["status"]!="PASS"]}
    findings=[]
    for key in ("header","product46","searches"):
        if a[key]!=b[key]:findings.append({"type":"REGRESSION","field":key,"a":a[key],"b":b[key]})
    return {"status":"REGRESSION" if findings else "PASS","findings":findings,
            "intentional_changes":["Catalog grows from13 to43 products","Catalog pages contain10 products","Filters/sort/pagination controls","PDP quantity,stock,gallery,variants and related items"]}


async def run(args):
    before=fingerprint()
    args.report_dir.mkdir(parents=True,exist_ok=True)
    report={"started_utc":datetime.now(timezone.utc).isoformat(),"baseline":{"url":BASELINE,"sites_version":10,"source_sha":BASELINE_SHA},
            "candidate":{"url":args.candidate_url,"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"source_fingerprint":before},
            "scope":"Read-only controlled legacy compatibility regression; not randomized traffic or post-deployment smoke","cases":[]}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(channel="chrome",headless=True)
        report["browser_version"]=browser.version
        for language in ("en","fr"):
            for viewport in VIEWPORTS:
                name=f"{language}_{viewport}"
                if args.case and name not in args.case:continue
                folder=args.report_dir/name
                a=await capture(browser,BASELINE,"A",language,viewport,folder/"A")
                b=await capture(browser,args.candidate_url,"B",language,viewport,folder/"B")
                result=compare(a,b)
                report["cases"].append({"name":name,"comparison":result,"a":str(folder/"A/result.json"),"b":str(folder/"B/result.json")})
                print(name,result["status"],flush=True)
        await browser.close()
    report["finished_utc"]=datetime.now(timezone.utc).isoformat()
    report["source_unchanged_during_run"]=before==fingerprint()
    report["counts"]={status:sum(c["comparison"]["status"]==status for c in report["cases"]) for status in ("PASS","REGRESSION","INCONCLUSIVE")}
    report["test_file_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.report_dir/"comparison.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return int(report["counts"]["REGRESSION"]+report["counts"]["INCONCLUSIVE"]>0 or not report["source_unchanged_during_run"])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-url",default="http://127.0.0.1:8787")
    parser.add_argument("--report-dir",type=Path,required=True)
    parser.add_argument("--case",action="append")
    args=parser.parse_args()
    if urlparse(args.candidate_url).hostname not in ("127.0.0.1","localhost","::1"):
        parser.error("Candidate must be loopback")
    args.candidate_url=args.candidate_url.rstrip("/")
    args.report_dir=args.report_dir.resolve()
    raise SystemExit(asyncio.run(run(args)))
