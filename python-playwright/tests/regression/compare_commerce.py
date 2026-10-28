"""Matched P0-04/05/06 regression journeys on two disposable loopback D1 servers.

This is a controlled compatibility comparison, not a production traffic test.
Every mutation is restricted to localhost. There are no automatic retries.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from playwright.async_api import async_playwright, expect
from redact_trace import redact_trace, redact_text

ROOT=Path(__file__).resolve().parents[3]
BASELINE_ARCHIVE=ROOT/'outputs/p0-02-03/p0-02-03-candidate-source.zip'
BASELINE_SHA256='d2e07892d6135a9a49c0d652cd8ed674799aa14c8a6e8164a9c4a7d7e74d6dd6'
VIEWPORTS={'desktop':{'width':1366,'height':900},'mobile':{'width':390,'height':844}}
ADDRESS={'name':'Test Shopper','email':'test.shopper@example.com','street':'123 Demo Street','city':'Bengaluru','pin':'560001'}
SENSITIVE={'cardNumber','pan','cvv','cardExpiry','cardholder','expiry'}


def source_fingerprint():
    files={}
    for directory in ('app','lib','components','scripts','drizzle','db'):
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and path.suffix in ('.ts','.tsx','.mjs','.css','.sql','.json'):
                files[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'files':files}


def build_fingerprint(directory):
    files={path.relative_to(directory).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
           for path in directory.rglob('*') if path.is_file()}
    return {'sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'files':len(files)}


def loopback(url):
    return urlparse(url).scheme in ('http','https') and urlparse(url).hostname in ('localhost','127.0.0.1','::1')


class Capture:
    def __init__(self,browser,origin,side,folder,language='en',viewport='desktop'):
        self.browser,self.origin,self.side,self.folder=browser,origin,side,folder
        self.language,self.viewport=language,viewport
        self.context=self.page=None
        self.result={'side':side,'url':origin,'language':language,'viewport':VIEWPORTS[viewport],
                     'requests':[],'errors':[],'checks':[],'captures':[]}

    def text(self,en,fr):return fr if self.language=='fr' else en

    async def start(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        self.context=await self.browser.new_context(viewport=VIEWPORTS[self.viewport],service_workers='block')
        await self.context.add_cookies([{'name':'everyday-language','value':self.language,'url':self.origin}])
        await self.context.tracing.start(screenshots=True,snapshots=True,sources=True)
        async def guard(route):
            request=route.request
            if request.method not in ('GET','HEAD') and not loopback(request.url):
                self.result['requests'].append({'method':request.method,'url':request.url,'blocked':True})
                await route.abort('blockedbyclient')
            else:await route.continue_()
        await self.context.route('**/*',guard)
        self.page=await self.context.new_page();self.page.set_default_timeout(15000)
        self.page.on('pageerror',lambda error:self.result['errors'].append({'type':'pageerror','message':redact_text(str(error))}))
        self.page.on('console',lambda message:self.result['errors'].append({'type':'console','message':redact_text(message.text),'url':message.location.get('url','')}) if message.type=='error' else None)
        self.page.on('response',lambda response:self.result['requests'].append({'method':response.request.method,'url':response.url,'status':response.status}) if '/api/' in response.url else None)
        return self

    async def api(self,path,method='GET',data=None):
        assert loopback(self.origin),'Writing comparison requires a disposable loopback origin'
        response=await self.context.request.fetch(self.origin+path,method=method,data=data,headers={'Origin':self.origin})
        self.result['requests'].append({'method':method,'url':response.url,'status':response.status,'api_client':True})
        assert response.status==200,(path,method,response.status,await response.text())
        return await response.json()

    async def visit(self,path):
        response=await self.page.goto(self.origin+path,wait_until='load')
        assert response and response.status==200,(path,response.status if response else None)
        await expect(self.page.locator('main')).to_be_visible()

    async def save(self,name):
        await self.page.mouse.move(0,0)
        await self.page.screenshot(path=str(self.folder/(name+'.png')),full_page=True,animations='disabled')
        (self.folder/(name+'-accessibility.txt')).write_text(await self.page.locator('body').aria_snapshot(),encoding='utf-8')
        self.result['captures'].append(name)

    def check(self,label):self.result['checks'].append({'name':label,'status':'PASS'})

    def diagnostics(self):
        unexpected=[error for error in self.result['errors'] if error['type']=='pageerror' or urlparse(error.get('url','')).path!='/favicon.ico']
        assert not unexpected,unexpected
        assert not any(request.get('blocked') for request in self.result['requests'])

    async def finish(self):
        await self.context.tracing.stop(path=str(self.folder/'trace.zip'))
        await self.context.close();redact_trace(self.folder/'trace.zip')
        self.result['trace_redacted']=True
        (self.folder/'result.json').write_text(json.dumps(self.result,indent=2,ensure_ascii=False),encoding='utf-8')
        return self.result


async def api_journey(capture,product_id,method):
    price=899 if product_id==43 else 1499
    expected_name='Decoration Swing' if product_id==43 else 'Plant Pot'
    detail=await capture.api(f'/api/products/{product_id}')
    product=detail['product']
    assert (product['name'],product['price'],product['category'],product['image'])==(expected_name,price,'Home',f'/products/{product_id}.webp')
    capture.result['product']={key:product[key] for key in ('id','name','description','price','category','image')}
    await capture.api('/api/shop')
    await capture.api('/api/shop','POST',{'product':product_id,'qty':2})
    await capture.api('/api/shop','POST',{'product':product_id,'qty':2})
    assert (await capture.api('/api/shop'))['items']==[{'product':product_id,'qty':2}]
    capture.check('legacy absolute updates remain absolute and persistent')
    await capture.api('/api/shop','POST',{'product':product_id,'qty':1})
    await capture.visit('/cart')
    await expect(capture.page.locator('.cart-row')).to_have_count(1)
    await expect(capture.page.locator('header .cart-count')).to_have_text('1')
    await capture.save('cart')
    order=await capture.api('/api/shop','POST',{'action':'checkout','address':dict(ADDRESS),'paymentMethod':method,'coupon':'EVERYDAY'})
    discount=(price+1)//2
    assert order['discount']==discount and order['total']==price-discount and isinstance(order['id'],str)
    assert (await capture.api('/api/shop'))['items']==[]
    capture.result['outcome']={'subtotal':price,'discount':order['discount'],'total':order['total'],
                               'method':method,'cart_after':[],'order_id':order['id']}
    capture.check('legacy demo checkout rounding and success-only cart clear')
    await capture.visit('/cart');await expect(capture.page.locator('.empty')).to_be_visible()
    await capture.save('cleared-cart')


async def ui_journey(capture):
    page=capture.page
    await capture.visit('/products/46')
    await expect(page.locator('.detail-copy .price')).to_have_text('₹1,499')
    await page.get_by_role('button',name=capture.text('Add to cart','Ajouter au panier'),exact=True).click()
    await expect(page.locator('header .cart-count')).to_have_text('1')
    await page.locator('header a[href="/cart"]').click()
    await expect(page).to_have_url(capture.origin+'/cart')
    await expect(page.locator('.summary .total')).to_contain_text('₹1,499')
    await page.get_by_label(capture.text('Coupon code','Code de réduction'),exact=True).fill('EVERYDAY')
    await page.get_by_role('button',name=capture.text('Apply','Appliquer'),exact=True).click()
    await expect(page.locator('.summary .total')).to_contain_text('₹749')
    await capture.save('cart')
    await page.locator('.summary a[href="/checkout"]').click()
    await expect(page).to_have_url(capture.origin+'/checkout')
    labels=[('Full name','Nom complet','name'),('Email address','Adresse e-mail','email'),
            ('Street address','Adresse','street'),('City','Ville','city'),('PIN code','Code postal','pin')]
    for english,french,key in labels:
        await page.get_by_label(capture.text(english,french),exact=True).fill(ADDRESS[key])
    if capture.side=='B':
        await page.get_by_label(capture.text('Phone number','Numéro de téléphone'),exact=True).fill('9876543210')
        await page.get_by_label(capture.text('State','État'),exact=True).fill('Karnataka')
    await page.get_by_role('button',name=capture.text('Continue to payment','Continuer vers le paiement'),exact=True).click()
    for english,french,value in [('Name on card','Nom sur la carte','Test Shopper'),
            ('Card number','Numéro de carte','4242 4242 4242 4242'),('Expiry','Date d’expiration','0133'),('CVV','CVV','123')]:
        await page.get_by_label(capture.text(english,french),exact=True).fill(value)
    await expect(page.locator('#expiry')).to_have_value('01/33')
    if capture.side=='B':
        await page.get_by_label(capture.text('Payment outcome','Résultat du paiement'),exact=True).select_option('success')
    await page.get_by_role('button',name=capture.text('Review order','Vérifier la commande'),exact=True).click()
    await expect(page.locator('.summary .total')).to_contain_text('₹749')
    await capture.save('review')
    def confirmation(response):
        if urlparse(response.url).path!='/api/shop' or response.request.method!='POST':return False
        try:return response.request.post_data_json.get('action')=='checkout'
        except (ValueError,AttributeError):return False
    async with page.expect_response(confirmation) as pending:
        await page.get_by_role('button',name=capture.text('Confirm and place order','Confirmer et passer la commande'),exact=True).click()
    response=await pending.value;assert response.status==200
    request_body=response.request.post_data_json
    assert not (SENSITIVE & set(request_body))
    if capture.side=='B':
        assert request_body['contractVersion']==2 and isinstance(request_body['expectedVersion'],int)
        assert isinstance(request_body['idempotencyKey'],str)
    order=await response.json()
    assert (order['discount'],order['total'])==(750,749)
    await expect(page.get_by_role('heading',name=capture.text('Thanks for shopping.','Merci pour votre visite.'),exact=True)).to_be_visible()
    await expect(page.locator('header .cart-count')).to_have_text('0')
    assert (await capture.api('/api/shop'))['items']==[]
    assert await page.locator('html').get_attribute('lang')==capture.language
    capture.result['outcome']={'subtotal':1499,'discount':750,'total':749,'method':'card','cart_after':[],'order_id':order['id']}
    capture.result['checkout_request_keys']=sorted(request_body)
    capture.check('native cart navigation and EVERYDAY visible totals')
    capture.check('matched three-step demo checkout and expiry formatting')
    capture.check('successful receipt, guest cart clear, language persistence and no payment fields sent')
    await capture.save('receipt')


def compare(a,b):
    if a.get('status')!='PASS':return {'status':'INCONCLUSIVE','findings':['Baseline execution did not complete']}
    if b.get('status')!='PASS':return {'status':'REGRESSION','findings':['Candidate execution did not complete']}
    findings=[]
    for field in ('subtotal','discount','total','method','cart_after'):
        if a['outcome'][field]!=b['outcome'][field]:findings.append(f'Changed {field}')
    if a.get('product')!=b.get('product'):findings.append('Legacy product metadata changed')
    return {'status':'REGRESSION' if findings else 'PASS','findings':findings,
            'intentional_changes':['B persists and validates coupons on the server','B adds phone/state in contract v2',
                                   'B adds version/idempotency and recovery controls','B never transmits demo card fields']}


async def run(args):
    assert hashlib.sha256(BASELINE_ARCHIVE.read_bytes()).hexdigest()==BASELINE_SHA256,'Baseline archive identity mismatch'
    args.report_dir.mkdir(parents=True,exist_ok=True)
    before=source_fingerprint();test_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report={'scope':'Controlled local A/B compatibility, with independent disposable D1 databases; not production or randomized traffic',
            'started_utc':datetime.now(timezone.utc).isoformat(),
            'baseline':{'url':args.baseline_url,'source_archive_sha256':BASELINE_SHA256,
                        'build':build_fingerprint(ROOT/'.sites-runtime/p0-04-06-baseline/dist')},
            'candidate':{'url':args.candidate_url,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                         'source_fingerprint':before,'build':build_fingerprint(ROOT/'dist')},'cases':[]}
    cases=[('api',f'api_{product}_{method}',product,method,'en','desktop') for product in (43,46) for method in ('card','paypal','pay-later')]
    cases += [('ui',f'ui_{language}_{viewport}',46,'card',language,viewport) for language in ('en','fr') for viewport in VIEWPORTS]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(channel='chrome',headless=True);report['browser_version']=browser.version
        for kind,name,product,method,language,viewport in cases:
            if args.case and name not in args.case:continue
            sides=[]
            for side,origin in [('A',args.baseline_url),('B',args.candidate_url)]:
                capture=await Capture(browser,origin,side,args.report_dir/name/side,language,viewport).start()
                try:
                    if kind=='api':await api_journey(capture,product,method)
                    else:await ui_journey(capture)
                    capture.diagnostics();capture.result['status']='PASS'
                except Exception as error:capture.result.update(status='FAIL',error=redact_text(repr(error)))
                finally:sides.append(await capture.finish())
            result=compare(*sides)
            report['cases'].append({'name':name,'comparison':result,'a':str(args.report_dir/name/'A/result.json'),'b':str(args.report_dir/name/'B/result.json')})
            print(name,result['status'],flush=True)
        await browser.close()
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    report['counts']={status:sum(case['comparison']['status']==status for case in report['cases']) for status in ('PASS','REGRESSION','INCONCLUSIVE')}
    report['source_unchanged_during_run']=before==source_fingerprint()
    report['test_file_sha256']=test_hash
    report['test_file_unchanged_during_run']=test_hash==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.report_dir/'comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    suite=ET.Element('testsuite',name='commerce-AB',tests=str(len(report['cases'])),failures=str(report['counts']['REGRESSION']+report['counts']['INCONCLUSIVE']))
    for case in report['cases']:
        row=ET.SubElement(suite,'testcase',name=case['name'])
        if case['comparison']['status']!='PASS':ET.SubElement(row,'failure').text=json.dumps(case['comparison'])
    ET.ElementTree(suite).write(args.report_dir/'junit.xml',encoding='utf-8',xml_declaration=True)
    return int(report['counts']['REGRESSION']+report['counts']['INCONCLUSIVE']>0 or not report['source_unchanged_during_run'] or not report['test_file_unchanged_during_run'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-url',default='http://127.0.0.1:8788')
    parser.add_argument('--candidate-url',default='http://127.0.0.1:8787')
    parser.add_argument('--report-dir',type=Path,required=True)
    parser.add_argument('--case',action='append',help='Run one exact case; repeat to select focused cases')
    args=parser.parse_args()
    if not all(loopback(url) for url in (args.baseline_url,args.candidate_url)):
        parser.error('Both comparison targets must be disposable loopback servers')
    args.baseline_url=args.baseline_url.rstrip('/');args.candidate_url=args.candidate_url.rstrip('/')
    if args.baseline_url==args.candidate_url:parser.error('Independent A and B URLs are required')
    args.report_dir=args.report_dir.resolve()
    raise SystemExit(asyncio.run(run(args)))
