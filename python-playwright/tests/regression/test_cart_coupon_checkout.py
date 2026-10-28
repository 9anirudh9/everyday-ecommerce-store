"""P0-04/05/06 acceptance against a disposable loopback D1 database.

No installation, production writes, sleeps or automatic retries. --test selects
one focused case after a diagnosed failure. UI assertions use semantic controls.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from urllib.parse import urlparse
import uuid
import xml.etree.ElementTree as ET

from playwright.async_api import async_playwright, expect
from redact_trace import redact_trace,redact_text

ROOT=Path(__file__).resolve().parents[3]
VIEWPORTS={'desktop':{'width':1366,'height':900},'mobile':{'width':390,'height':844}}
ADDRESS={'name':'Test Shopper','email':'test.shopper@example.com','phone':'9876543210',
         'street':'123 Demo Street','city':'Bengaluru','state':'Karnataka','pin':'560001'}


def fingerprint():
    files={}
    for directory in ('app','lib','components','scripts','drizzle'):
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and path.suffix in ('.ts','.tsx','.mjs','.css','.sql'):
                files[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'files':files}


class Session:
    def __init__(self,args,browser,name,language='en',viewport='desktop'):
        self.args,self.browser,self.name=args,browser,name
        self.language,self.viewport=language,viewport
        self.folder=args.report_dir/name
        self.events,self.errors,self.expected_diagnostics=[],[],[]
        self.sensitive_checkout_fields=[]
        self.context=self.page=None

    async def start(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        self.context=await self.browser.new_context(viewport=VIEWPORTS[self.viewport],service_workers='block')
        await self.context.add_cookies([{'name':'everyday-language','value':self.language,'url':self.args.base_url}])
        await self.context.tracing.start(screenshots=True,snapshots=True,sources=True)
        self.context.on('page',self.observe)
        self.page=await self.context.new_page()
        self.page.set_default_timeout(12000)
        return self

    def observe(self,page):
        page.on('pageerror',lambda error:self.errors.append({'type':'pageerror','message':str(error)}))
        page.on('console',lambda message:self.errors.append({'type':'console','message':message.text,'url':message.location.get('url','')}) if message.type=='error' else None)
        page.on('response',lambda response:self.events.append({'method':response.request.method,'url':response.url,'status':response.status}) if '/api/' in response.url else None)
        def inspect_request(request):
            if request.method=='POST' and urlparse(request.url).path=='/api/shop':
                try:
                    body=request.post_data_json
                    if isinstance(body,dict) and body.get('action')=='checkout':
                        forbidden={'cardNumber','cvv','pan','cardExpiry','cardholder'} & set(body)
                        if forbidden:self.sensitive_checkout_fields.append(sorted(forbidden))
                except Exception:pass
        page.on('request',inspect_request)

    def text(self,english,french):
        return french if self.language=='fr' else english

    async def open(self,path):
        response=await self.page.goto(self.args.base_url+path,wait_until='load')
        assert response and response.status==200,(path,response.status if response else None)
        await expect(self.page.locator('main')).to_be_visible()

    async def request(self,path,method='GET',data=None,status=200,context=None,origin=None):
        context=context or self.context
        headers={'Origin':origin or self.args.base_url}
        if origin and origin!=self.args.base_url:headers['Connection']='close'
        response=await context.request.fetch(self.args.base_url+path,method=method,data=data,headers=headers)
        self.events.append({'method':method,'url':response.url,'status':response.status,'api_client':True})
        expected=(status,) if isinstance(status,int) else tuple(status)
        assert response.status in expected,(path,response.status,await response.text())
        body=await response.json()
        return body,response.status

    async def snapshot(self,context=None):
        return (await self.request('/api/shop',context=context))[0]

    async def set_item(self,product=46,qty=1,context=None,**extra):
        snap=await self.snapshot(context)
        payload={'product':product,'qty':qty,'expectedVersion':snap['version'],'idempotencyKey':str(uuid.uuid4()),**extra}
        return (await self.request('/api/shop','POST',payload,context=context))[0]

    async def coupon(self,code,context=None,status=200,**extra):
        snap=await self.snapshot(context)
        return (await self.request('/api/coupons/validate','POST',
            {'code':code,'apply':True,'expectedVersion':snap['version'],**extra},status=status,context=context))[0]

    async def checkout_body(self,context=None,**extra):
        snap=await self.snapshot(context)
        return {'action':'checkout','contractVersion':2,'address':dict(ADDRESS),'paymentMethod':'card',
                'simulation':'success','idempotencyKey':str(uuid.uuid4()),'expectedVersion':snap['version'],**extra}

    async def checkout(self,context=None,status=200,**extra):
        payload=await self.checkout_body(context,**extra)
        return (await self.request('/api/shop','POST',payload,status=status,context=context))[0]

    async def db_user(self):
        await self.snapshot()
        cookies=await self.context.cookies(self.args.base_url)
        token=next(cookie['value'] for cookie in cookies if cookie['name']=='__Host-everyday-guest')
        return 'guest:'+token

    def database(self):
        path=self.args.database_file
        assert path and path.is_file() and path.resolve().is_relative_to((ROOT/'.sites-runtime').resolve()),'Disposable local D1 fixture required'
        return sqlite3.connect(path,timeout=5)

    async def order_count(self):
        user=await self.db_user()
        with self.database() as connection:
            return connection.execute('SELECT count(*) FROM orders WHERE user=?',(user,)).fetchone()[0]

    def allow(self,url,pattern):
        self.expected_diagnostics.append({'url':url,'pattern':pattern})

    def check_errors(self):
        assert not self.sensitive_checkout_fields,f'Checkout transmitted forbidden fields: {self.sensitive_checkout_fields}'
        unexpected=[]
        for error in self.errors:
            if error['type']=='pageerror':unexpected.append(error)
            elif urlparse(error.get('url','')).path=='/favicon.ico':continue
            elif not any(error.get('url')==item['url'] and re.fullmatch(item['pattern'],error['message']) for item in self.expected_diagnostics):unexpected.append(error)
        assert not unexpected,f'Unexpected diagnostics: {unexpected}'

    async def finish(self,record):
        try:
            await self.page.screenshot(path=str(self.folder/'screenshot.png'),full_page=True,animations='disabled')
            (self.folder/'accessibility.txt').write_text(await self.page.locator('body').aria_snapshot(),encoding='utf-8')
        except Exception as error:record['capture_error']=redact_text(repr(error))
        finally:
            await self.context.tracing.stop(path=str(self.folder/'trace.zip'));await self.context.close()
            redact_trace(self.folder/'trace.zip')
        record.update(events=self.events,browser_errors=self.errors,expected_diagnostics=self.expected_diagnostics,trace_redacted=True,
                      trace=str(self.folder/'trace.zip'),screenshot=str(self.folder/'screenshot.png'))
        (self.folder/'evidence.json').write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')


async def api_initial_snapshot(s):
    data=await s.snapshot()
    assert data['items']==[] and isinstance(data['version'],int)
    quote=data['quote']
    assert (quote['subtotal'],quote['discount'],quote['total'],quote['delivery'])==(0,0,0,0)
    user=await s.db_user()
    assert user[6:] not in json.dumps(data),'Session capability leaked into API response'


async def api_cart_math_and_persistence(s):
    await s.set_item(46,2)
    data=await s.snapshot();assert data['items']==[{'product':46,'qty':2}]
    assert data['quote']['subtotal']==2998
    await s.set_item(46,3)
    await s.set_item(43,1)
    data=await s.snapshot();assert data['quote']['subtotal']==5396
    assert len(data['items'])==2
    await s.set_item(46,0)
    assert (await s.snapshot())['items']==[{'product':43,'qty':1}]


async def api_cart_version_conflict(s):
    before=await s.snapshot()
    requests=[{'product':p,'qty':1,'expectedVersion':before['version'],'idempotencyKey':str(uuid.uuid4())} for p in (43,46)]
    responses=await asyncio.gather(*(s.request('/api/shop','POST',payload,status=(200,409)) for payload in requests))
    assert sorted(status for _,status in responses)==[200,409]
    snap=await s.snapshot();assert len(snap['items'])==1
    loser=requests[next(index for index,(_,status) in enumerate(responses) if status==409)]
    await s.request('/api/shop','POST',{**loser,'expectedVersion':snap['version'],'idempotencyKey':str(uuid.uuid4())})
    assert len((await s.snapshot())['items'])==2


async def api_cart_idempotent_retry(s):
    snap=await s.snapshot()
    payload={'product':46,'qty':2,'expectedVersion':snap['version'],'idempotencyKey':str(uuid.uuid4())}
    await s.request('/api/shop','POST',payload)
    first=await s.snapshot()
    await s.request('/api/shop','POST',payload)
    second=await s.snapshot()
    assert first['items']==second['items']==[{'product':46,'qty':2}]
    assert first['version']==second['version']


async def api_invalid_mutations(s):
    for qty in (-1,1.5,'2',11):
        await s.request('/api/shop','POST',{'product':46,'qty':qty},status=400)
        assert (await s.snapshot())['items']==[]
    await s.request('/api/shop','POST',{'product':202,'qty':1},status=409)
    with s.database() as connection:
        cart_before=connection.execute('SELECT user,product,qty FROM cart ORDER BY user,product').fetchall()
    rejected_context=await s.browser.new_context(service_workers='block')
    try:
        await s.request('/api/shop','POST',{'product':46,'qty':1},status=403,
                        context=rejected_context,origin='https://wrong.example')
    finally:await rejected_context.close()
    with s.database() as connection:
        cart_after=connection.execute('SELECT user,product,qty FROM cart ORDER BY user,product').fetchall()
    assert cart_after==cart_before,'Wrong-Origin request mutated the disposable D1 cart'


async def api_clear_cart(s):
    await s.set_item(46,2);await s.set_item(43,1)
    snap=await s.snapshot()
    await s.request('/api/shop','POST',{'action':'clear','expectedVersion':snap['version'],'idempotencyKey':str(uuid.uuid4())})
    data=await s.snapshot();assert data['items']==[] and data['quote']['total']==0


async def api_guest_isolation(s):
    other=await s.browser.new_context(service_workers='block')
    try:
        await s.set_item(46,2)
        assert (await s.snapshot(other))['items']==[]
        await s.set_item(43,1,context=other)
        assert (await s.snapshot())['items']==[{'product':46,'qty':2}]
    finally:await other.close()


async def api_everyday_rounding(s):
    await s.set_item(46,1);await s.coupon(' everyday ')
    snap=await s.snapshot()
    assert (snap['quote']['subtotal'],snap['quote']['discount'],snap['quote']['total'])==(1499,750,749)
    await s.set_item(46,2)
    snap=await s.snapshot();assert snap['quote']['discount']==1499 and snap['quote']['total']==1499


async def api_save100_threshold(s):
    await s.set_item(47,1)
    await s.coupon('SAVE100',status=(400,409,422))
    assert (await s.snapshot())['quote']['discount']==0
    await s.set_item(47,0);await s.set_item(46,1);await s.coupon('SAVE100')
    quote=(await s.snapshot())['quote'];assert quote['discount']==100 and quote['total']==1399


async def api_invalid_expired_coupons(s):
    await s.set_item(46,1)
    for code in ('NOTREAL','EXPIRED10'):
        await s.coupon(code,status=(400,409,422))
        assert (await s.snapshot())['quote']['discount']==0


async def api_single_coupon_and_remove(s):
    await s.set_item(46,1)
    await s.coupon('EVERYDAY');await s.coupon('SAVE100')
    quote=(await s.snapshot())['quote'];assert quote['coupon']=='SAVE100' and quote['discount']==100
    await s.coupon('')
    quote=(await s.snapshot())['quote'];assert quote['coupon'] is None and quote['discount']==0 and quote['total']==1499
    await s.coupon('FREESHIP')
    quote=(await s.snapshot())['quote'];assert quote['coupon']=='FREESHIP' and quote['discount']==0 and quote['delivery']==0


async def api_firstbuy_eligibility(s):
    await s.set_item(46,1);await s.coupon('FIRSTBUY')
    quote=(await s.snapshot())['quote'];assert quote['discount']==150 and quote['total']==1349
    order=await s.checkout();assert order['total']==1349
    await s.set_item(46,1)
    await s.coupon('FIRSTBUY',status=(400,409,422))
    assert (await s.snapshot())['quote']['discount']==0


async def api_checkout_validation(s):
    await s.set_item(46,1)
    for field,value in (('name',''),('email','bad'),('phone',''),('phone','123'),('state',''),('pin','12345')):
        payload=await s.checkout_body(address={**ADDRESS,field:value})
        await s.request('/api/shop','POST',payload,status=400)
        assert (await s.snapshot())['items']==[{'product':46,'qty':1}]
    assert await s.order_count()==0


async def api_demo_payment_failures(s):
    await s.set_item(46,1)
    for simulation,status in (('decline',422),('cancel',409),('timeout',408)):
        await s.checkout(simulation=simulation,status=status)
        assert (await s.snapshot())['items']==[{'product':46,'qty':1}]
        assert await s.order_count()==0
    for method in ('card','paypal','pay-later'):
        if not (await s.snapshot())['items']:await s.set_item(46,1)
        result=await s.checkout(paymentMethod=method)
        assert result['paymentMethod']==method and result['status']=='demo-confirmed'
    assert await s.order_count()==3


async def api_checkout_idempotency_race(s):
    await s.set_item(46,2);await s.coupon('EVERYDAY')
    payload=await s.checkout_body()
    results=await asyncio.gather(*(s.request('/api/shop','POST',payload) for _ in range(2)))
    first,second=(body for body,_ in results)
    assert first['id']==second['id'] and first['total']==second['total']==1499
    assert await s.order_count()==1 and (await s.snapshot())['items']==[]
    replay,_=await s.request('/api/shop','POST',payload)
    assert replay['id']==first['id'] and replay['replayed'] is True
    await s.request('/api/shop','POST',{**payload,'address':{**ADDRESS,'city':'Chennai'}},status=409)
    assert await s.order_count()==1


async def api_checkout_different_keys_race(s):
    await s.set_item(46,1)
    payload=await s.checkout_body()
    results=await asyncio.gather(*(s.request('/api/shop','POST',{**payload,'idempotencyKey':str(uuid.uuid4())},status=(200,400,409)) for _ in range(2)))
    assert sum(status==200 for _,status in results)==1
    assert await s.order_count()==1 and (await s.snapshot())['items']==[]


async def api_checkout_vs_cart_race(s):
    await s.set_item(46,1)
    payload=await s.checkout_body()
    mutation={'product':43,'qty':1,'expectedVersion':payload['expectedVersion'],'idempotencyKey':str(uuid.uuid4())}
    order,update=await asyncio.gather(s.request('/api/shop','POST',payload,status=(200,409)),s.request('/api/shop','POST',mutation,status=(200,409)))
    assert sorted([order[1],update[1]])==[200,409]
    snap=await s.snapshot()
    if order[1]==200:assert snap['items']==[] and await s.order_count()==1
    else:assert {item['product'] for item in snap['items']}=={43,46} and await s.order_count()==0


async def api_checkout_request_identity(s):
    await s.set_item(46,1);await s.coupon('EVERYDAY')
    payload=await s.checkout_body()
    await s.request('/api/shop','POST',payload)
    await s.request('/api/shop','POST',{**payload,'coupon':None},status=409)
    await s.request('/api/shop','POST',{**payload,'expectedTotal':None},status=400)
    await s.request('/api/shop','POST',{**payload,'expectedVersion':None},status=400)
    assert await s.order_count()==1


async def api_checkout_tampering_and_sensitive(s):
    await s.set_item(46,1)
    payload=await s.checkout_body(total=-100,discount=999999,subtotal=0)
    result,_=await s.request('/api/shop','POST',payload)
    assert result['subtotal']==1499 and result['discount']==0 and result['total']==1499
    user=await s.db_user()
    with s.database() as connection:
        row=connection.execute('SELECT items,address FROM orders WHERE user=?',(user,)).fetchone()
    assert row and not any(key in ' '.join(str(value) for value in row).lower() for key in ('cardnumber','cvv','cardexpiry','cardholder'))
    await s.set_item(46,1)
    await s.checkout(expectedTotal=1,status=409)
    assert (await s.snapshot())['items']==[{'product':46,'qty':1}]
    await s.checkout(cardNumber='do-not-store-pan',cvv='do-not-store-cvv',status=400)
    assert (await s.snapshot())['items']==[{'product':46,'qty':1}]


async def api_order_scope_and_empty_checkout(s):
    await s.checkout(status=400)
    await s.set_item(46,1);order=await s.checkout()
    data,_=await s.request('/api/orders/'+order['id'])
    assert data.get('id',data.get('order',{}).get('id'))==order['id']
    other=await s.browser.new_context(service_workers='block')
    try:await s.request('/api/orders/'+order['id'],context=other,status=404)
    finally:await other.close()


async def api_legacy_checkout_compatibility(s):
    await s.set_item(46,1)
    legacy={key:ADDRESS[key] for key in ('name','email','street','city','pin')}
    order,_=await s.request('/api/shop','POST',{'action':'checkout','address':legacy,'paymentMethod':'card','coupon':'EVERYDAY'})
    assert order['total']==749 and (await s.snapshot())['items']==[]


async def api_limited_per_guest(s):
    await s.set_item(46,1);await s.coupon('LIMITED20')
    order=await s.checkout();assert order['discount']==300 and order['total']==1199
    await s.set_item(46,1)
    await s.coupon('LIMITED20',status=(400,409,422))
    assert (await s.snapshot())['quote']['discount']==0


async def api_limited_global_race(s):
    contexts=[]
    try:
        payloads=[]
        for _ in range(7):
            context=await s.browser.new_context(service_workers='block');contexts.append(context)
            await s.set_item(46,1,context=context)
            await s.coupon('LIMITED20',context=context)
            payloads.append(await s.checkout_body(context))
        results=await asyncio.gather(*(s.request('/api/shop','POST',body,status=(200,409,422),context=context) for body,context in zip(payloads,contexts)))
        successful=[body for body,status in results if status==200]
        assert 0<len(successful)<=5
        assert len({body['id'] for body in successful})==len(successful)
        with s.database() as connection:
            rows=connection.execute('SELECT items FROM orders').fetchall()
        limited=[row for row in rows if json.loads(row[0]).get('coupon')=='LIMITED20']
        assert len(limited)<=5,'Global cap exceeded'
        for context,(_,status) in zip(contexts,results):
            snap=await s.snapshot(context)
            assert (snap['items']==[]) if status==200 else (snap['items']==[{'product':46,'qty':1}])
    finally:
        for context in contexts:await context.close()


async def fill_delivery(s):
    fields=[('Full name','Nom complet','name'),('Email address','Adresse e-mail','email'),
            ('Phone number','Numéro de téléphone','phone'),('Street address','Adresse','street'),
            ('City','Ville','city'),('State','État','state'),('PIN code','Code postal','pin')]
    for english,french,key in fields:
        await s.page.get_by_label(s.text(english,french),exact=True).fill(ADDRESS[key])
    await s.page.get_by_role('button',name=s.text('Continue to payment','Continuer vers le paiement'),exact=True).click()


async def fill_payment(s,outcome='success'):
    for english,french,value in [('Name on card','Nom sur la carte','Test Shopper'),
            ('Card number','Numéro de carte','4242 4242 4242 4242'),('Expiry','Date d’expiration','0133'),('CVV','CVV','123')]:
        field=s.page.get_by_label(s.text(english,french),exact=True)
        if await field.count() and await field.is_visible():await field.fill(value)
    await s.page.get_by_label(s.text('Payment outcome','Résultat du paiement'),exact=True).select_option(outcome)
    await s.page.get_by_role('button',name=s.text('Review order','Vérifier la commande'),exact=True).click()


async def confirm_ui(s):
    await s.page.get_by_role('button',name=s.text('Confirm and place order','Confirmer et passer la commande'),exact=True).click()
    await expect(s.page.get_by_text(re.compile(r'Order #|Commande n°'))).to_be_visible()


async def ui_cart_undo_clear(s):
    await s.set_item(46,2)
    await s.open('/cart')
    await expect(s.page.locator('.cart-row')).to_have_count(1)
    await expect(s.page.locator('.summary .total')).to_contain_text('₹2,998')
    await s.page.locator('.cart-row').get_by_role('button',name=s.text('Remove','Retirer'),exact=True).click()
    await expect(s.page.locator('.empty')).to_be_visible()
    await s.page.get_by_role('button',name=s.text('Undo','Annuler'),exact=True).click()
    await expect(s.page.locator('header .cart-count')).to_have_text('2')
    await expect(s.page.locator('.cart-row')).to_have_count(1)
    clear=s.page.get_by_role('button',name=s.text('Clear cart','Vider le panier'),exact=True)
    await clear.click()
    dialog=s.page.get_by_role('dialog')
    await expect(dialog).to_be_visible()
    await dialog.get_by_role('button',name=s.text('Clear cart','Vider le panier'),exact=True).click()
    await expect(s.page.locator('.empty')).to_be_visible()
    assert (await s.snapshot())['items']==[]


async def ui_coupon_persistence(s):
    await s.set_item(46,1);await s.open('/cart')
    coupon=s.page.get_by_label(s.text('Coupon code','Code de réduction'),exact=True)
    apply=s.page.get_by_role('button',name=s.text('Apply','Appliquer'),exact=True)
    await coupon.fill('everyday');await apply.click()
    await expect(s.page.locator('.summary .total')).to_contain_text('₹749')
    await coupon.fill('SAVE100');await apply.click()
    await expect(s.page.locator('.summary .total')).to_contain_text('₹1,399')
    await s.page.reload()
    await expect(s.page.locator('.summary .total')).to_contain_text('₹1,399')
    await s.page.get_by_role('button',name=s.text('Remove coupon','Retirer le code'),exact=True).click()
    await expect(s.page.locator('.summary .total')).to_contain_text('₹1,499')
    assert (await s.snapshot())['quote']['coupon'] is None


async def ui_checkout_success(s):
    await s.set_item(46,1);await s.coupon('EVERYDAY');await s.open('/checkout')
    await fill_delivery(s);await fill_payment(s)
    await expect(s.page.locator('.summary .total')).to_contain_text('₹749')
    await confirm_ui(s)
    await expect(s.page.locator('header .cart-count')).to_have_text('0')
    assert (await s.snapshot())['items']==[] and await s.order_count()==1


async def ui_two_tab_reconciliation(s):
    await s.open('/cart')
    await expect(s.page.locator('header .cart-count')).to_have_text('0')
    second=await s.context.new_page();await second.goto(s.args.base_url+'/products/46')
    await second.get_by_role('button',name='Add to cart',exact=True).click()
    await expect(second.locator('header .cart-count')).to_have_text('1')
    await expect(s.page.locator('header .cart-count')).to_have_text('1')
    await expect(s.page.locator('.cart-row')).to_have_count(1)
    await second.close()


async def ui_cart_failed_write_retry(s):
    await s.set_item(46,1);await s.open('/cart')
    fail=True
    async def intercept(route):
        nonlocal fail
        if route.request.method=='POST' and fail:
            fail=False;await route.fulfill(status=503,json={'error':'Deliberate cart failure'})
        else:await route.fallback()
    await s.context.route('**/api/shop',intercept)
    s.allow(s.args.base_url+'/api/shop',r'Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)')
    await s.page.locator('.cart-row').get_by_role('button',name='Remove',exact=True).click()
    await expect(s.page.get_by_role('alert').first).to_be_visible()
    assert (await s.snapshot())['items']==[{'product':46,'qty':1}]
    await s.page.get_by_role('button',name='Retry cart update',exact=True).click()
    await expect(s.page.locator('.empty')).to_be_visible()
    assert (await s.snapshot())['items']==[]


async def ui_coupon_failure_retry(s):
    await s.set_item(46,1);await s.open('/cart')
    fail=True
    async def intercept(route):
        nonlocal fail
        if fail:
            fail=False;await route.fulfill(status=503,json={'error':'Deliberate coupon failure'})
        else:await route.fallback()
    await s.context.route('**/api/coupons/validate',intercept)
    s.allow(s.args.base_url+'/api/coupons/validate',r'Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)')
    await s.page.get_by_label('Coupon code',exact=True).fill('EVERYDAY')
    await s.page.get_by_role('button',name='Apply',exact=True).click()
    await expect(s.page.get_by_role('alert').first).to_be_visible()
    assert (await s.snapshot())['quote']['total']==1499
    await s.page.get_by_role('button',name='Apply',exact=True).click()
    await expect(s.page.locator('.summary .total')).to_contain_text('₹749')


async def ui_lost_checkout_response_retry(s):
    await s.set_item(46,1);await s.open('/checkout')
    await fill_delivery(s);await fill_payment(s)
    lost=True
    async def intercept(route):
        nonlocal lost
        body=route.request.post_data_json if route.request.method=='POST' else None
        if lost and isinstance(body,dict) and body.get('action')=='checkout':
            lost=False
            response=await route.fetch()
            assert response.status==200
            await route.abort('timedout')
        else:await route.fallback()
    await s.context.route('**/api/shop',intercept)
    s.allow(s.args.base_url+'/api/shop',r'Failed to load resource: net::ERR_TIMED_OUT')
    await s.page.get_by_role('button',name='Confirm and place order',exact=True).click()
    await expect(s.page.get_by_role('button',name='Retry confirmation',exact=True)).to_be_visible()
    assert await s.order_count()==1
    await s.page.get_by_role('button',name='Retry confirmation',exact=True).click()
    await expect(s.page.get_by_text(re.compile('Order #'))).to_be_visible()
    assert await s.order_count()==1 and (await s.snapshot())['items']==[]


async def ui_malformed_checkout_response_retry(s):
    await s.set_item(46,1);await s.open('/checkout')
    await fill_delivery(s);await fill_payment(s)
    malformed=True
    async def intercept(route):
        nonlocal malformed
        body=route.request.post_data_json if route.request.method=='POST' else None
        if malformed and isinstance(body,dict) and body.get('action')=='checkout':
            malformed=False
            response=await route.fetch();data=await response.json();assert response.status==200
            await route.fulfill(json={key:data[key] for key in ('id','total','status','cart')})
        else:await route.fallback()
    await s.context.route('**/api/shop',intercept)
    await s.page.get_by_role('button',name='Confirm and place order',exact=True).click()
    await expect(s.page.get_by_role('button',name='Retry confirmation',exact=True)).to_be_visible()
    assert await s.order_count()==1
    await s.page.get_by_role('button',name='Retry confirmation',exact=True).click()
    await expect(s.page.get_by_text(re.compile('Order #'))).to_be_visible()
    assert await s.order_count()==1


async def ui_clear_failure_recovery(s):
    await s.set_item(46,1);await s.open('/cart')
    fail=True
    async def intercept(route):
        nonlocal fail
        body=route.request.post_data_json if route.request.method=='POST' else None
        if fail and isinstance(body,dict) and body.get('action')=='clear':
            fail=False;await route.fulfill(status=503,json={'error':'Deliberate clear failure'})
        else:await route.fallback()
    await s.context.route('**/api/shop',intercept)
    s.allow(s.args.base_url+'/api/shop',r'Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)')
    await s.page.get_by_role('button',name='Clear cart',exact=True).click()
    dialog=s.page.get_by_role('dialog')
    await dialog.get_by_role('button',name='Clear cart',exact=True).click()
    await expect(dialog).not_to_be_visible()
    await expect(s.page.get_by_role('button',name='Retry cart update',exact=True)).to_be_visible()
    assert (await s.snapshot())['items']==[{'product':46,'qty':1}]
    await s.page.get_by_role('button',name='Retry cart update',exact=True).click()
    await expect(s.page.locator('.empty')).to_be_visible()


async def ui_safe_draft_reload(s):
    await s.set_item(46,1);await s.open('/checkout')
    await s.page.get_by_label(s.text('Full name','Nom complet'),exact=True).fill(ADDRESS['name'])
    await s.page.get_by_label(s.text('Phone number','Numéro de téléphone'),exact=True).fill(ADDRESS['phone'])
    await s.page.evaluate("window.dispatchEvent(new Event('focus'))")
    await expect(s.page.get_by_label(s.text('Full name','Nom complet'),exact=True)).to_have_value(ADDRESS['name'])
    await s.page.reload()
    await expect(s.page.get_by_label(s.text('Full name','Nom complet'),exact=True)).to_have_value(ADDRESS['name'])
    await fill_delivery(s)
    for english,french,value in [('Name on card','Nom sur la carte','Test Shopper'),('Card number','Numéro de carte','4242 4242 4242 4242'),('Expiry','Date d’expiration','0133'),('CVV','CVV','123')]:
        field=s.page.get_by_label(s.text(english,french),exact=True)
        if await field.count() and await field.is_visible():await field.fill(value)
    storage=await s.page.evaluate("JSON.stringify({...sessionStorage})")
    assert '4242' not in storage and 'cvv' not in storage.lower() and '0133' not in storage
    await s.page.reload()
    field=s.page.get_by_label(s.text('Card number','Numéro de carte'),exact=True)
    if await field.count() and await field.is_visible():await expect(field).to_have_value('')


async def ui_payment_failure_recovery(s):
    await s.set_item(46,1);await s.open('/checkout')
    await fill_delivery(s);await fill_payment(s,'decline')
    s.allow(s.args.base_url+'/api/shop',r'Failed to load resource: the server responded with a status of 422 \(Unprocessable Entity\)')
    await s.page.get_by_role('button',name='Confirm and place order',exact=True).click()
    await expect(s.page.get_by_role('alert').first).to_contain_text(re.compile('declined',re.I))
    assert await s.order_count()==0 and (await s.snapshot())['items']==[{'product':46,'qty':1}]
    await s.page.get_by_role('button',name='Change payment outcome',exact=True).click()
    await s.page.get_by_label('Payment outcome',exact=True).select_option('success')
    await s.page.get_by_role('button',name='Review order',exact=True).click()
    await confirm_ui(s)
    assert await s.order_count()==1 and (await s.snapshot())['items']==[]


API_CASES=[api_initial_snapshot,api_cart_math_and_persistence,api_cart_version_conflict,api_cart_idempotent_retry,
    api_invalid_mutations,api_clear_cart,api_guest_isolation,api_everyday_rounding,api_save100_threshold,
    api_invalid_expired_coupons,api_single_coupon_and_remove,api_firstbuy_eligibility,api_checkout_validation,
    api_demo_payment_failures,api_checkout_idempotency_race,api_checkout_different_keys_race,api_checkout_vs_cart_race,api_checkout_request_identity,api_checkout_tampering_and_sensitive,
    api_order_scope_and_empty_checkout,api_legacy_checkout_compatibility,api_limited_per_guest,api_limited_global_race]
MATRIX_CASES=[ui_cart_undo_clear,ui_coupon_persistence,ui_checkout_success]
FOCUSED_CASES=[ui_two_tab_reconciliation,ui_cart_failed_write_retry,ui_coupon_failure_retry,ui_lost_checkout_response_retry,ui_malformed_checkout_response_retry,ui_clear_failure_recovery,ui_payment_failure_recovery]


async def run(args):
    before=fingerprint();records=[]
    test_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    cases=[(fn,'en','desktop') for fn in API_CASES]
    cases += [(fn,language,viewport) for language in ('en','fr') for viewport in VIEWPORTS for fn in MATRIX_CASES]
    cases += [(fn,'en','desktop') for fn in FOCUSED_CASES]
    cases += [(ui_safe_draft_reload,language,'desktop') for language in ('en','fr')]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(channel=args.browser_channel,headless=True)
        browser_version=browser.version
        for function,language,viewport in cases:
            name=f'{function.__name__}_{language}_{viewport}'
            if args.test and args.test not in (function.__name__,name):continue
            record={'test':name,'language':language,'viewport':VIEWPORTS[viewport]}
            session=await Session(args,browser,name,language,viewport).start()
            started=time.monotonic()
            try:
                await function(session);session.check_errors();record['status']='PASS'
            except Exception as error:record.update(status='FAIL',error=redact_text(repr(error)))
            finally:
                record['seconds']=round(time.monotonic()-started,3)
                await session.finish(record);records.append(record)
                print(name,record['status'],flush=True)
        await browser.close()
    report={'scope':'Disposable local-D1 P0-04/05/06 API/browser acceptance; not production smoke or A/B',
        'base_url':args.base_url,'started_utc':args.started,'finished_utc':datetime.now(timezone.utc).isoformat(),
        'browser_version':browser_version,'playwright_python_version':package_version('playwright'),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'dirty_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        'source_fingerprint':before,'source_unchanged_during_run':before==fingerprint(),
        'test_file_sha256':test_hash,'test_file_unchanged_during_run':test_hash==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'tests_run':len(records),'passed':sum(r['status']=='PASS' for r in records),
        'failed':sum(r['status']!='PASS' for r in records),'records':records}
    (args.report_dir/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    suite=ET.Element('testsuite',name='p0-04-06-cart-coupon-checkout',tests=str(len(records)),failures=str(report['failed']))
    for record in records:
        case=ET.SubElement(suite,'testcase',name=record['test'],time=str(record['seconds']))
        if record['status']!='PASS':ET.SubElement(case,'failure').text=record['error']
    ET.ElementTree(suite).write(args.report_dir/'junit.xml',encoding='utf-8',xml_declaration=True)
    return int(report['failed']>0 or not report['source_unchanged_during_run'] or not report['test_file_unchanged_during_run'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8787')
    parser.add_argument('--browser-channel',default='chrome')
    parser.add_argument('--report-dir',type=Path,required=True)
    parser.add_argument('--database-file',type=Path,required=True)
    parser.add_argument('--test',help='One function or full matrix case; no automatic retries')
    args=parser.parse_args();args.base_url=args.base_url.rstrip('/')
    if urlparse(args.base_url).hostname not in ('127.0.0.1','localhost','::1'):
        parser.error('Writing acceptance suite requires loopback and disposable D1')
    if not args.database_file.resolve().is_relative_to((ROOT/'.sites-runtime').resolve()):
        parser.error('Database fixture must be under repository .sites-runtime')
    args.report_dir=args.report_dir.resolve();args.report_dir.mkdir(parents=True,exist_ok=True)
    args.started=datetime.now(timezone.utc).isoformat()
    return asyncio.run(run(args))


if __name__=='__main__':raise SystemExit(main())
