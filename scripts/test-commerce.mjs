/** Pure pricing/validation contracts; no external service or package install. */
import assert from 'node:assert/strict';
import {readFileSync,existsSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {createRequire} from 'node:module';
import {runInThisContext} from 'node:vm';
import ts from 'typescript';
import {DatabaseSync} from 'node:sqlite';

const root=resolve(import.meta.dirname,'..');
const nodeRequire=createRequire(import.meta.url),cache=new Map();
function load(path){
  const file=resolve(root,path);if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};cache.set(file,loaded);
  const compiled=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const wrapped=runInThisContext(`(function(exports,require,module,__filename,__dirname){${compiled}\n})`,{filename:file});
  wrapped(loaded.exports,specifier=>{if(!specifier.startsWith('.')&&!specifier.startsWith('@/'))return nodeRequire(specifier);const base=specifier.startsWith('@/')?resolve(root,specifier.slice(2)):resolve(dirname(file),specifier);return load(existsSync(base)?base:base+'.ts')},loaded,file,dirname(file));
  return loaded.exports;
}
const {calculateQuote,normalizeCoupon,couponRules}=load('lib/coupons.ts');
const {checkoutFingerprintInput,validateCheckoutExpectations,validateAddress,simulationFailure,isPaymentMethod,isSimulation}=load('lib/checkout.ts');
const context={now:Date.parse('2026-10-28T00:00:00Z'),orderCount:0,guestUses:0,globalUses:0,globalLimit:5};
const records=[];
function check(name,test){try{test();records.push({name,status:'PASS'});console.log('PASS',name)}catch(error){records.push({name,status:'FAIL',error:error.stack});console.error('FAIL',name,error.message)}}
const quote=(rupees,code,ctx=context)=>calculateQuote(rupees*100,code,ctx);
check('EVERYDAY preserves odd-rupee legacy rounding',()=>{const q=quote(1499,'EVERYDAY');assert.equal(q.discount,750);assert.equal(q.total,749);assert.equal(q.totalPaise,74900)});
check('EVERYDAY preserves existing899 checkout449',()=>{const q=quote(899,'EVERYDAY');assert.equal(q.discount,450);assert.equal(q.total,449)});
check('EVERYDAY even2998 ->1499 exact',()=>{assert.equal(quote(2998,'EVERYDAY').discount,1499)});
check('SAVE100 999 boundary is rejected',()=>{assert.equal(quote(999,'SAVE100').couponError.code,'COUPON_MINIMUM')});
check('SAVE100 1000 boundary is included',()=>{const q=quote(1000,'SAVE100');assert.equal(q.discount,100);assert.equal(q.total,900)});
check('SAVE100 1001 stays fixed100',()=>{assert.equal(quote(1001,'SAVE100').total,901)});
check('FIRSTBUY10 percent and500cap',()=>{assert.equal(quote(1499,'FIRSTBUY').discount,150);assert.equal(quote(9999,'FIRSTBUY').discount,500)});
check('FIRSTBUY rejects existing legacy guest order',()=>{assert.equal(quote(1499,'FIRSTBUY',{...context,orderCount:1}).couponError.code,'FIRST_ORDER_ONLY')});
check('FIRSTBUY rejects prior redemption',()=>{assert.equal(quote(1499,'FIRSTBUY',{...context,guestUses:1}).couponError.code,'FIRST_ORDER_ONLY')});
check('LIMITED20 whole-rupee math and500cap',()=>{assert.equal(quote(1499,'LIMITED20').discount,300);assert.equal(quote(9000,'LIMITED20').discount,500)});
check('LIMITED20 one per guest',()=>{assert.equal(quote(1499,'LIMITED20',{...context,guestUses:1}).couponError.code,'COUPON_ALREADY_USED')});
check('LIMITED20 exactglobalcap rejects',()=>{assert.equal(quote(1499,'LIMITED20',{...context,globalUses:5}).couponError.code,'COUPON_LIMIT_REACHED')});
check('LIMITED20 lastavailableuse valid',()=>{assert.equal(quote(1499,'LIMITED20',{...context,globalUses:4}).valid,true)});
check('Expiry before boundary valid; exact boundary expired',()=>{const expiry=couponRules.LIMITED20.expiresAt;assert.equal(quote(1499,'LIMITED20',{...context,now:expiry-1}).valid,true);assert.equal(quote(1499,'LIMITED20',{...context,now:expiry}).couponError.code,'COUPON_EXPIRED')});
check('EXPIRED10 always expired under releaseclock',()=>{assert.equal(quote(1499,'EXPIRED10').couponError.code,'COUPON_EXPIRED')});
check('FREESHIP valid zero benefit/free delivery',()=>{const q=quote(1499,'FREESHIP');assert.equal(q.valid,true);assert.equal(q.delivery,0);assert.equal(q.discount,0);assert.equal(q.total,1499)});
check('Unknown coupon including prototype properties rejected',()=>{for(const code of ['NOPE','constructor','__proto__'])assert.equal(quote(1499,code).couponError.code,'COUPON_INVALID')});
check('Coupon normalization is trim/case independent',()=>{assert.equal(normalizeCoupon(' everyday '),'EVERYDAY')});
check('Removing coupon restores original totals',()=>{const q=quote(1499,null);assert.equal(q.discount,0);assert.equal(q.total,1499);assert.equal(q.coupon,null)});
check('Discount never exceeds subtotal',()=>{for(const subtotal of [0,1,99,100,999,1000,1001,1499,10000])for(const code of Object.keys(couponRules)){const q=quote(subtotal,code);assert.ok(q.discount>=0&&q.discount<=q.subtotal&&q.total>=0)}});
check('Invalid negative or nonfinite money cannot produce negative total',()=>{for(const subtotal of [-100,NaN,Infinity]){const q=calculateQuote(subtotal,'EVERYDAY',context);assert.equal(q.total,0);assert.equal(q.valid,false)}});
const address={name:'Test Shopper',email:'test@example.com',phone:'9876543210',street:'123 Demo Street',city:'Bengaluru',state:'Karnataka',pin:'560001'};
check('Strict valid delivery normalizes surrounding whitespace',()=>{assert.equal(validateAddress({...address,name:' Test Shopper '}).address.name,'Test Shopper')});
check('Strict new checkout requires phone and state',()=>{const result=validateAddress({...address,phone:'',state:''});assert.ok(result.errors.phone&&result.errors.state)});
check('Legacy delivery remains compatible without phone/state',()=>{assert.ok(validateAddress({...address,phone:'',state:''},false).address)});
check('Malformed email andPIN rejected',()=>{const result=validateAddress({...address,email:'bad',pin:'123'});assert.ok(result.errors.email&&result.errors.pin)});
check('Phone requires real digit count, allows91 countrycode',()=>{for(const phone of ['( )---....','123','abcdefghij'])assert.ok(validateAddress({...address,phone}).errors.phone);assert.ok(validateAddress({...address,phone:'+91 98765 43210'}).address)});
check('Delivery arrays and oversized fields rejected',()=>{assert.ok(validateAddress([]).errors.address);assert.ok(validateAddress({...address,street:'x'.repeat(300)}).errors.street)});
check('Only three retained demo payment methods',()=>{for(const value of ['card','paypal','pay-later'])assert.equal(isPaymentMethod(value),true);assert.equal(isPaymentMethod('real-provider'),false)});
check('Simulation failures are explicit and success has none',()=>{assert.equal(simulationFailure('success'),null);assert.equal(simulationFailure('decline').status,422);assert.equal(simulationFailure('timeout').status,408);assert.equal(simulationFailure('cancel').status,409);assert.equal(isSimulation('arbitrary'),false)});
check('Checkout fingerprint distinguishes persisted coupon from explicit removal',()=>{const base={paymentMethod:'card',expectedVersion:1};assert.notDeepEqual(checkoutFingerprintInput(base,address,true,'success'),checkoutFingerprintInput({...base,coupon:null},address,true,'success'));assert.notDeepEqual(checkoutFingerprintInput(base,address,true,'success'),checkoutFingerprintInput({...base,coupon:''},address,true,'success'))});
check('Checkout rejects malformed version/total before idempotent replay',()=>{for(const expectedVersion of [null,'1',-1,1.5])assert.equal(validateCheckoutExpectations({expectedVersion},true).code,'INVALID_CART_VERSION');for(const expectedTotal of [null,'749',-1,NaN])assert.equal(validateCheckoutExpectations({expectedVersion:1,expectedTotal},true).code,'INVALID_EXPECTED_TOTAL');assert.equal(validateCheckoutExpectations({expectedVersion:1,expectedTotal:749},true),null)});
check('Checkout fingerprint preserves expected-total presence',()=>{const base={paymentMethod:'card',expectedVersion:1};assert.notDeepEqual(checkoutFingerprintInput(base,address,true,'success'),checkoutFingerprintInput({...base,expectedTotal:749},address,true,'success'))});
function fixture(){const database=new DatabaseSync(':memory:');database.exec(readFileSync(resolve(root,'drizzle/0000_legal_the_twelve.sql'),'utf8'));database.exec(readFileSync(resolve(root,'drizzle/0001_resilient_commerce.sql'),'utf8'));return database}
function transaction(database,action){database.exec('BEGIN');try{action();database.exec('COMMIT')}catch(error){database.exec('ROLLBACK');throw error}}
function simulatedOrder(database,user,key,code='LIMITED20',version=1){
  transaction(database,()=>{
    database.prepare('INSERT INTO commerce_guards(id,permitted) VALUES(?,CASE WHEN COALESCE((SELECT version FROM cart_state WHERE user=?),0)=? THEN 1 ELSE 0 END)').run(key,user,version);
    database.prepare('INSERT INTO checkout_requests(user,request_key,fingerprint,order_id,created_at) VALUES(?,?,?,?,?)').run(user,key,key,key,'2026-10-28T00:00:00Z');
    if(code)database.prepare('INSERT INTO coupon_redemptions(order_id,user,code,created_at) VALUES(?,?,?,?)').run(key,user,code,'2026-10-28T00:00:00Z');
    database.prepare('INSERT INTO orders(id,user,items,total,address) VALUES(?,?,?,?,?)').run(key,user,'{}',1199,'{}');
    database.prepare('DELETE FROM cart WHERE user=?').run(user);
    database.prepare('DELETE FROM commerce_guards WHERE id=?').run(key);
  });
}
check('Additive migration keeps legacy cart/order rows',()=>{const database=new DatabaseSync(':memory:');database.exec(readFileSync(resolve(root,'drizzle/0000_legal_the_twelve.sql'),'utf8'));database.exec("INSERT INTO cart VALUES('legacy',46,2); INSERT INTO orders VALUES('old','legacy','{}',1499,'{}')");database.exec(readFileSync(resolve(root,'drizzle/0001_resilient_commerce.sql'),'utf8'));assert.equal(database.prepare('SELECT qty FROM cart').get().qty,2);assert.equal(database.prepare('SELECT count(*) AS n FROM orders').get().n,1);database.close()});
check('Cart SQL triggers revision only on actual quantity changes',()=>{const database=fixture();database.prepare('INSERT INTO cart VALUES(?,?,?)').run('guest',46,2);assert.equal(database.prepare('SELECT version FROM cart_state').get().version,1);database.prepare('UPDATE cart SET qty=2 WHERE user=?').run('guest');assert.equal(database.prepare('SELECT version FROM cart_state').get().version,1);database.prepare('UPDATE cart SET qty=3 WHERE user=?').run('guest');assert.equal(database.prepare('SELECT version FROM cart_state').get().version,2);database.prepare('DELETE FROM cart WHERE user=?').run('guest');assert.equal(database.prepare('SELECT version FROM cart_state').get().version,3);database.close()});
check('LIMITED20 sixth redemption rolls back order/key/cart clear',()=>{const database=fixture();for(let index=0;index<6;index++)database.prepare('INSERT INTO cart VALUES(?,?,?)').run('guest'+index,46,1);for(let index=0;index<5;index++)simulatedOrder(database,'guest'+index,'request'+index);assert.throws(()=>simulatedOrder(database,'guest5','request5'),/COUPON_LIMIT_REACHED/);assert.equal(database.prepare('SELECT count(*) AS n FROM orders').get().n,5);assert.equal(database.prepare('SELECT count(*) AS n FROM coupon_redemptions').get().n,5);assert.equal(database.prepare('SELECT count(*) AS n FROM checkout_requests').get().n,5);assert.equal(database.prepare('SELECT qty FROM cart WHERE user=?').get('guest5').qty,1);assert.equal(database.prepare('SELECT count(*) AS n FROM commerce_guards').get().n,0);database.close()});
check('Per-guest limited redemption uniqueness is atomic',()=>{const database=fixture();database.prepare('INSERT INTO cart VALUES(?,?,?)').run('guest',46,1);simulatedOrder(database,'guest','request-one');database.prepare('INSERT INTO cart VALUES(?,?,?)').run('guest',46,1);assert.throws(()=>simulatedOrder(database,'guest','request-two','LIMITED20',3),/UNIQUE constraint failed/);assert.equal(database.prepare('SELECT count(*) AS n FROM orders').get().n,1);assert.equal(database.prepare('SELECT qty FROM cart').get().qty,1);database.close()});
check('FIRSTBUY SQL trigger rejects prior legacy order before writes',()=>{const database=fixture();database.prepare('INSERT INTO orders VALUES(?,?,?,?,?)').run('legacy-order','guest','{}',1499,'{}');database.prepare('INSERT INTO cart VALUES(?,?,?)').run('guest',46,1);assert.throws(()=>simulatedOrder(database,'guest','request-first','FIRSTBUY'),/FIRST_ORDER_ONLY/);assert.equal(database.prepare('SELECT count(*) AS n FROM orders').get().n,1);assert.equal(database.prepare('SELECT count(*) AS n FROM checkout_requests').get().n,0);assert.equal(database.prepare('SELECT qty FROM cart').get().qty,1);database.close()});
check('Stale checkout revision cannot erase a newer cart write',()=>{const database=fixture();database.prepare('INSERT INTO cart VALUES(?,?,?)').run('guest',46,1);database.prepare('UPDATE cart SET qty=2 WHERE user=?').run('guest');assert.throws(()=>simulatedOrder(database,'guest','request-stale',null,1),/commerce_precondition/);assert.equal(database.prepare('SELECT count(*) AS n FROM orders').get().n,0);assert.equal(database.prepare('SELECT qty FROM cart').get().qty,2);database.close()});
const output={scope:'Pure commerce policies, delivery and SQLite trigger transaction contracts; not D1/API/browser execution',records,passed:records.filter(record=>record.status==='PASS').length,failed:records.filter(record=>record.status!=='PASS').length};
mkdirSync(resolve(root,'outputs/p0-04-06'),{recursive:true});writeFileSync(resolve(root,'outputs/p0-04-06/domain-results.json'),JSON.stringify(output,null,2));
process.exitCode=output.failed?1:0;
