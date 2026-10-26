"""Read-only browser smoke for the existing live Sites version 9."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

LIVE = "https://everyday-shop-anirudh.cidirianirudh.chatgpt.site"


async def run(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    result = {
        "scope": "existing live v9 read-only smoke; not candidate post-deployment smoke",
        "url": LIVE,
        "deployed_source_sha_from_sites_record": "4550358b96f0a26bd118d98e2e64eb956beaecbf",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "checks": [], "api_requests": [], "errors": [],
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        result["browser_version"] = browser.version
        context = await browser.new_context(
            viewport={"width": 1366, "height": 900}, service_workers="block")
        await context.add_cookies([{"name": "everyday-language", "value": "en", "url": LIVE}])
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        async def guard(route):
            request = route.request
            result["api_requests"].append({"method": request.method, "url": request.url})
            if request.method != "GET":
                await route.abort("blockedbyclient")
                raise AssertionError(f"Unexpected production API write: {request.method}")
            await route.continue_()

        await context.route("**/api/**", guard)
        page = await context.new_page()
        page.on("pageerror", lambda error: result["errors"].append({
            "type": "pageerror", "message": str(error)}))
        page.on("console", lambda message: result["errors"].append({
            "type": "console", "message": message.text,
            "url": message.location.get("url", "")}) if message.type == "error" else None)
        try:
            for path, heading in (("/", None), ("/products/46", "Plant Pot"),
                                  ("/search?q=plant", None), ("/cart", None)):
                response = await page.goto(LIVE + path, wait_until="load")
                assert response and response.status == 200, (path, response.status if response else None)
                await expect(page.locator("main")).to_be_visible()
                if heading:
                    await expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                    await expect(page.get_by_text("\u20b91,499", exact=True)).to_be_visible()
                if path == "/cart":
                    await expect(page.locator(".empty")).to_be_visible()
                result["checks"].append({"path": path, "status": "PASS"})
            await page.screenshot(path=str(folder / "live-v9-cart.png"), full_page=True)
            assert all(x["method"] == "GET" for x in result["api_requests"])
            unexpected = [x for x in result["errors"] if x["type"] == "pageerror" or
                          urlparse(x.get("url", "")).path != "/favicon.ico"]
            assert not unexpected, unexpected
            result["verdict"] = "PASS"
        except Exception as error:
            result["verdict"] = "FAIL"
            result["exception"] = repr(error)
        finally:
            await context.tracing.stop(path=str(folder / "live-v9-trace.zip"))
            await context.close()
            await browser.close()
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (folder / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(result["verdict"], len(result["checks"]), "read-only route checks")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.report_dir.resolve())))
