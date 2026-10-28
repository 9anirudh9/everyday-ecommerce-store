"""Production catalog/detail smoke. Every browser API write fails closed."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'regression'))
from redact_trace import redact_trace,redact_text


async def run(args):
    args.report_dir.mkdir(parents=True,exist_ok=True)
    report={"scope":"Read-only post-deployment P0-02 through P0-06 smoke","url":args.base_url,
            "sites_sha":args.sites_sha,"version_id":args.version_id,"deployment_id":args.deployment_id,
            "started_utc":datetime.now(timezone.utc).isoformat(),"cases":[]}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(channel='chrome',headless=True)
        report['browser_version']=browser.version
        for lang in ('en','fr'):
            for size,viewport in [('desktop',{'width':1366,'height':900}),('mobile',{'width':390,'height':844})]:
                name=f'{lang}_{size}';folder=args.report_dir/name;folder.mkdir(parents=True,exist_ok=True)
                result={'name':name,'checks':[],'api_requests':[],'errors':[]}
                context=await browser.new_context(viewport=viewport,service_workers='block')
                await context.add_cookies([{'name':'everyday-language','value':lang,'url':args.base_url}])
                await context.tracing.start(screenshots=True,snapshots=True,sources=True)
                async def guard(route):
                    request=route.request
                    result['api_requests'].append({'url':request.url,'method':request.method})
                    if request.method!='GET':await route.abort('blockedbyclient')
                    else:await route.continue_()
                await context.route('**/api/**',guard)
                page=await context.new_page();page.set_default_timeout(15000)
                page.on('pageerror',lambda e:result['errors'].append({'type':'pageerror','message':str(e)}))
                page.on('console',lambda m:result['errors'].append({'type':'console','message':m.text,'url':m.location.get('url','')}) if m.type=='error' else None)
                async def visit(path):
                    response=await page.goto(args.base_url+path,wait_until='load')
                    assert response and response.status==200
                    await expect(page.locator('main')).to_be_visible()
                def check(name):result['checks'].append({'name':name,'status':'PASS'})
                try:
                    await visit('/products')
                    await expect(page.locator('.product-card')).to_have_count(10)
                    await expect(page.get_by_test_id('catalog-result-count')).to_contain_text('43')
                    await page.screenshot(path=str(folder/'catalog.png'),full_page=True,animations='disabled')
                    check('expanded catalog, controls and page size')
                    await page.get_by_role('link',name='Page suivante' if lang=='fr' else 'Next page',exact=True).click()
                    await expect(page).to_have_url(__import__('re').compile('page=2'))
                    await expect(page.locator('.product-card')).to_have_count(10)
                    await visit('/products?page=5')
                    await expect(page.locator('.product-card')).to_have_count(3)
                    check('next page and partial final page')
                    await visit('/products?category=Home&minPrice=700&maxPrice=1500&inStock=true&sort=price-asc')
                    await expect(page.locator('.product-card').first).to_be_visible()
                    await expect(page.locator('select[name="category"]')).to_have_value('Home')
                    check('combined criteria restored from URL')
                    await visit('/products/46')
                    await expect(page.get_by_role('heading',name='Pot de fleurs' if lang=='fr' else 'Plant Pot',exact=True)).to_be_visible()
                    await expect(page.locator('.detail-copy .price')).to_have_text('₹1,499')
                    await expect(page.get_by_label('Quantité' if lang=='fr' else 'Quantity',exact=True)).to_have_value('1')
                    image=page.get_by_role('button',name='Voir l’image 2' if lang=='fr' else 'View image 2',exact=True)
                    await image.click();await expect(image).to_have_attribute('aria-pressed','true')
                    zoom=page.get_by_role('button',name='Agrandir l’image' if lang=='fr' else 'Zoom image',exact=True)
                    await zoom.click();await expect(page.get_by_role('dialog')).to_be_visible()
                    await page.keyboard.press('Escape');await expect(zoom).to_be_focused()
                    await page.screenshot(path=str(folder/'product.png'),full_page=True,animations='disabled')
                    check('legacy product, quantity, gallery and keyboard zoom')
                    await visit('/products/202');await expect(page.locator('.detail-add')).to_be_disabled()
                    check('unavailable stock cannot be added')
                    await page.locator('header a[href="/cart"]').click()
                    await expect(page.locator('.empty')).to_be_visible()
                    await expect(page.locator('header .cart-count')).to_have_text('0')
                    snapshot_response=await context.request.get(args.base_url+'/api/shop')
                    result['api_requests'].append({'url':args.base_url+'/api/shop','method':'GET','api_client':True})
                    assert snapshot_response.status==200
                    snapshot=await snapshot_response.json()
                    assert snapshot['items']==[] and isinstance(snapshot['version'],int)
                    assert snapshot['quote']['total']==0 and snapshot['quote']['discount']==0
                    assert snapshot['quote']['coupon'] is None and snapshot['issues']==[]
                    check('new commerce schema and authoritative empty guest quote')
                    await visit('/checkout')
                    await expect(page.get_by_role('heading',name='Le panier est vide ou votre session invitée a changé.' if lang=='fr' else 'Your cart is empty or your guest session changed.',exact=True)).to_be_visible()
                    assert await page.locator('.confirm-order').count()==0
                    check('empty guest checkout blocks order confirmation')
                    assert all(x['method']=='GET' for x in result['api_requests'])
                    unexpected=[x for x in result['errors'] if x['type']=='pageerror' or urlparse(x.get('url','')).path!='/favicon.ico']
                    assert not unexpected,unexpected
                    check('guest cart/navigation/API stay read-only without browser errors')
                    result['status']='PASS'
                except Exception as error:
                    result.update(status='FAIL',error=redact_text(repr(error)))
                finally:
                    await context.tracing.stop(path=str(folder/'trace.zip'));await context.close()
                    redact_trace(folder/'trace.zip')
                report['cases'].append(result);print(name,result['status'],flush=True)
        await browser.close()
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    report['passed']=sum(r['status']=='PASS' for r in report['cases'])
    report['failed']=sum(r['status']=='FAIL' for r in report['cases'])
    (args.report_dir/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return int(report['failed']>0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='https://everyday-shop-anirudh.cidirianirudh.chatgpt.site')
    parser.add_argument('--sites-sha',required=True)
    parser.add_argument('--version-id',required=True)
    parser.add_argument('--deployment-id',required=True)
    parser.add_argument('--report-dir',type=Path,required=True)
    args=parser.parse_args();args.base_url=args.base_url.rstrip('/')
    raise SystemExit(asyncio.run(run(args)))
