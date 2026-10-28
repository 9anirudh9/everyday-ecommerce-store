import {db} from './db';
import {products} from './products';
import {maxProductQuantity,validateStockQuantity} from './stock';
import {calculateQuote,couponRules,evaluateCoupon,normalizeCoupon,type CouponContext} from './coupons';
import {checkoutFingerprintInput,isPaymentMethod,isSimulation,simulationFailure,validateAddress,validateCheckoutExpectations} from './checkout';
import type {CartItem,CartIssue,CartSnapshot,CheckoutResult,PaymentMethod} from './commerce-types';

type StateRow={version:number;coupon:string|null};
type Receipt={fingerprint:string};
type CheckoutReceipt=Receipt&{order_id:string;created_at:string};
type OrderRow={id:string;user:string;items:string;total:number;address:string};
export type CommerceBody=Record<string,unknown>;
export class CommerceError extends Error{
  constructor(public status:number,public code:string,message:string,public details:Record<string,unknown>={}){super(message)}
}
const now=()=>new Date().toISOString();
async function digest(value:unknown){
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)));
  return Array.from(new Uint8Array(bytes),byte=>byte.toString(16).padStart(2,'0')).join('');
}
function keyOf(value:unknown,required=false){
  if(value===undefined&&!required)return null;
  if(typeof value!=='string'||!/^[A-Za-z0-9._:-]{8,128}$/.test(value))throw new CommerceError(400,'INVALID_IDEMPOTENCY_KEY','Use a valid confirmation or request key.');
  return value;
}
function versionOf(value:unknown,fallback:number){
  if(value===undefined)return fallback;
  if(!Number.isInteger(value)||Number(value)<0)throw new CommerceError(400,'INVALID_CART_VERSION','Use a valid cart version.');
  return Number(value);
}
async function couponContext(user:string,code:string|null,database: D1Database):Promise<CouponContext>{
  const row=await database.prepare(`SELECT
    (SELECT count(*) FROM orders WHERE user=?) AS orderCount,
    (SELECT count(*) FROM coupon_redemptions WHERE user=? AND code=?) AS guestUses,
    (SELECT count(*) FROM coupon_redemptions WHERE code=?) AS globalUses,
    COALESCE((SELECT max_uses FROM coupon_limits WHERE code=?),5) AS globalLimit`)
    .bind(user,user,code??'',code??'',code??'').first<Omit<CouponContext,'now'>>();
  return {now:Date.now(),orderCount:row?.orderCount??0,guestUses:row?.guestUses??0,globalUses:row?.globalUses??0,globalLimit:row?.globalLimit??5};
}
function cartIssues(items:CartItem[]):CartIssue[]{
  return items.flatMap(item=>{
    const product=products.find(candidate=>candidate.id===item.product);
    if(!product)return [{code:'PRODUCT_UNAVAILABLE',message:'A product is no longer available. Remove it from your cart.',product:item.product}];
    const stock=validateStockQuantity(product,item.qty);
    return stock.valid?[]:[{code:stock.code??'STOCK_CHANGED',message:stock.error??'Availability changed.',product:item.product,currentPrice:product.price,availableStock:product.stock,maxQuantity:maxProductQuantity(product)}];
  });
}
export async function readCart(user:string,database: D1Database=db()):Promise<CartSnapshot>{
  // A transactional pair of SELECTs keeps rows and revision from different writes apart.
  const results=await database.batch([
    database.prepare('SELECT version,coupon FROM cart_state WHERE user=?').bind(user),
    database.prepare('SELECT product,qty FROM cart WHERE user=? ORDER BY product').bind(user),
  ]);
  const state=(results[0].results as StateRow[])[0]??{version:0,coupon:null};
  const items=results[1].results as CartItem[];
  const issues=cartIssues(items);
  const subtotalPaise=items.reduce((sum,item)=>sum+(products.find(product=>product.id===item.product)?.price??0)*100*item.qty,0);
  const context=await couponContext(user,state.coupon,database);
  return {items,version:state.version,quote:calculateQuote(subtotalPaise,state.coupon,context,issues.length===0),issues,checkedAt:now()};
}
function guard(database:D1Database,id:string,user:string,version:number){
  return database.prepare('INSERT INTO commerce_guards(id,permitted) VALUES(?,CASE WHEN COALESCE((SELECT version FROM cart_state WHERE user=?),0)=? THEN 1 ELSE 0 END)').bind(id,user,version);
}
async function mutationReplay(user:string,key:string,fingerprint:string,database:D1Database){
  const row=await database.prepare('SELECT fingerprint FROM commerce_mutations WHERE user=? AND request_key=?').bind(user,key).first<Receipt>();
  if(!row)return null;
  if(row.fingerprint!==fingerprint)throw new CommerceError(409,'IDEMPOTENCY_CONFLICT','This request key was already used for a different action.');
  return {ok:true,replayed:true,cart:await readCart(user,database)};
}
async function runMutation(user:string,body:CommerceBody,operation:unknown,statements:(database:D1Database)=>D1PreparedStatement[],database:D1Database,snapshot:CartSnapshot){
  const version=versionOf(body.expectedVersion,snapshot.version);
  const suppliedKey=keyOf(body.idempotencyKey);
  const fingerprint=await digest(operation);
  if(suppliedKey){const replay=await mutationReplay(user,suppliedKey,fingerprint,database);if(replay)return replay}
  if(version!==snapshot.version)throw new CommerceError(409,'CART_CHANGED','Your cart changed in another tab. Review it before retrying.',{cart:snapshot});
  const key=suppliedKey??`legacy-mutation:${crypto.randomUUID()}`;
  const id=crypto.randomUUID();
  try{
    await database.batch([
      database.prepare('INSERT OR IGNORE INTO cart_state(user,version) VALUES(?,0)').bind(user),
      guard(database,id,user,version),
      database.prepare('INSERT INTO commerce_mutations(user,request_key,fingerprint,created_at) VALUES(?,?,?,?)').bind(user,key,fingerprint,now()),
      ...statements(database),
      database.prepare('DELETE FROM commerce_guards WHERE id=?').bind(id),
    ]);
  }catch{
    if(suppliedKey){const replay=await mutationReplay(user,suppliedKey,fingerprint,database);if(replay)return replay}
    const current=await readCart(user,database);
    if(current.version!==version)throw new CommerceError(409,'CART_CHANGED','Your cart changed in another tab. Review it before retrying.',{cart:current});
    throw new CommerceError(503,'CART_SAVE_FAILED','Could not save your cart. Please try again.');
  }
  return {ok:true,replayed:false,cart:await readCart(user,database)};
}
export async function mutateCart(user:string,body:CommerceBody,database:D1Database=db()){
  const snapshot=await readCart(user,database);
  versionOf(body.expectedVersion,snapshot.version);
  if(body.action==='clear')return runMutation(user,body,{action:'clear',expectedVersion:body.expectedVersion??null},database=>[
    database.prepare('DELETE FROM cart WHERE user=?').bind(user),
    database.prepare('UPDATE cart_state SET coupon=NULL,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE user=? AND coupon IS NOT NULL').bind(user),
  ],database,snapshot);
  if(body.action!==undefined&&body.action!=='update')throw new CommerceError(400,'INVALID_ACTION','Choose a valid cart action.');
  const product=products.find(candidate=>candidate.id===body.product);
  if(!Number.isInteger(body.product)||!Number.isInteger(body.qty)||Number(body.qty)<0||Number(body.qty)>10)throw new CommerceError(400,'INVALID_QUANTITY','Invalid quantity.');
  if(body.expectedPrice!==undefined&&(typeof body.expectedPrice!=='number'||!Number.isFinite(body.expectedPrice)||body.expectedPrice<0))throw new CommerceError(400,'INVALID_PRICE','Enter a valid expected price.');
  const suppliedKey=keyOf(body.idempotencyKey);
  const operation={action:'update',product:body.product,qty:body.qty,expectedPrice:body.expectedPrice??null,expectedVersion:body.expectedVersion??null};
  if(suppliedKey){const replay=await mutationReplay(user,suppliedKey,await digest(operation),database);if(replay)return replay}
  // Successful receipts survive later catalog changes; new unknown products are
  // rejected, while an unavailable old line must remain removable with qty0.
  if(!product&&body.qty!==0)throw new CommerceError(400,'INVALID_PRODUCT','This product is no longer available.',{product:body.product});
  if(body.qty!==0&&product){
    const details={product:product.id,currentPrice:product.price,availableStock:product.stock,maxQuantity:maxProductQuantity(product),cart:snapshot};
    if(body.expectedPrice!==undefined&&body.expectedPrice!==product.price)throw new CommerceError(409,'PRICE_CHANGED','The price has changed. Review the current price before adding again.',details);
    const stock=validateStockQuantity(product,Number(body.qty));
    if(!stock.valid)throw new CommerceError(409,stock.code??'STOCK_CHANGED',stock.error??'Availability changed.',details);
  }
  return runMutation(user,body,operation,database=>body.qty===0?
    [database.prepare('DELETE FROM cart WHERE user=? AND product=?').bind(user,body.product)]:
    [database.prepare('INSERT INTO cart(user,product,qty) VALUES(?,?,?) ON CONFLICT(user,product) DO UPDATE SET qty=excluded.qty').bind(user,body.product,body.qty)],database,snapshot);
}
export async function validateAndApplyCoupon(user:string,body:CommerceBody,database:D1Database=db()){
  if(typeof body.code!=='string'||body.code.length>30)throw new CommerceError(400,'COUPON_INVALID','Enter a valid coupon code.');
  if(body.apply!==undefined&&typeof body.apply!=='boolean')throw new CommerceError(400,'INVALID_BODY','Use a valid coupon application action.');
  const code=normalizeCoupon(body.code)||null;
  const snapshot=await readCart(user,database);
  versionOf(body.expectedVersion,snapshot.version);
  const suppliedKey=keyOf(body.idempotencyKey);
  const operation={action:'coupon',code,expectedVersion:body.expectedVersion??null};
  if(body.apply===true&&suppliedKey){const replay=await mutationReplay(user,suppliedKey,await digest(operation),database);if(replay)return replay}
  const context=await couponContext(user,code,database);
  const result=code?evaluateCoupon(code,snapshot.quote.subtotalPaise,context):{discountPaise:0};
  if(result.error)throw new CommerceError(422,result.error.code,result.error.message,{cart:snapshot});
  if(body.apply!==true){const quote=calculateQuote(snapshot.quote.subtotalPaise,code,context,snapshot.issues.length===0);return {valid:quote.valid,quote,cart:snapshot}}
  return runMutation(user,body,operation,database=>[
    database.prepare('UPDATE cart_state SET coupon=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE user=? AND coupon IS NOT ?').bind(code,user,code),
  ],database,snapshot);
}
async function storedOrder(user:string,id:string,database:D1Database){
  const row=await database.prepare('SELECT id,user,items,total,address FROM orders WHERE id=? AND user=?').bind(id,user).first<OrderRow>();
  if(!row)return null;
  const data=JSON.parse(row.items) as {products:CartItem[];coupon?:string|null;subtotal?:number;discount?:number;paymentMethod?:PaymentMethod;status?:string};
  return {id:row.id,total:row.total,subtotal:data.subtotal??row.total,discount:data.discount??0,coupon:data.coupon??null,paymentMethod:data.paymentMethod??'card',status:'demo-confirmed' as const,items:data.products};
}
export async function getOrder(user:string,id:string,database:D1Database=db()){
  const order=await storedOrder(user,id,database);
  if(!order)throw new CommerceError(404,'ORDER_NOT_FOUND','Order not found.');
  return order;
}
async function checkoutReplay(user:string,key:string,fingerprint:string,database:D1Database):Promise<CheckoutResult|null>{
  const receipt=await database.prepare('SELECT fingerprint,order_id,created_at FROM checkout_requests WHERE user=? AND request_key=?').bind(user,key).first<CheckoutReceipt>();
  if(!receipt)return null;
  if(receipt.fingerprint!==fingerprint)throw new CommerceError(409,'IDEMPOTENCY_CONFLICT','This confirmation key was already used for a different order.');
  const order=await storedOrder(user,receipt.order_id,database);
  if(!order)throw new CommerceError(503,'ORDER_RECOVERY_FAILED','Could not recover this order. Please try again.');
  return {...order,replayed:true,cart:await readCart(user,database)};
}
export async function checkout(user:string,body:CommerceBody,database:D1Database=db()):Promise<CheckoutResult>{
  const strict=body.contractVersion===2;
  if(body.contractVersion!==undefined&&!strict)throw new CommerceError(400,'INVALID_CONTRACT','Unsupported checkout contract.');
  const expectations=validateCheckoutExpectations(body,strict);
  if(expectations)throw new CommerceError(400,expectations.code,expectations.message);
  for(const field of ['cardNumber','cvv','pan','card','paymentDetails'])if(body[field]!==undefined)throw new CommerceError(400,'PAYMENT_DATA_NOT_ACCEPTED','Do not send card credentials to this demo checkout.');
  const validation=validateAddress(body.address,strict);
  if(!validation.address)throw new CommerceError(400,'ADDRESS_INVALID','Please check your delivery details.',{fields:validation.errors});
  if(!isPaymentMethod(body.paymentMethod))throw new CommerceError(400,'PAYMENT_METHOD_INVALID','Please select a valid payment option.');
  const simulation=body.simulation===undefined?'success':body.simulation;
  if(!isSimulation(simulation))throw new CommerceError(400,'SIMULATION_INVALID','Choose a valid demo payment outcome.');
  if(body.coupon!==undefined&&body.coupon!==null&&typeof body.coupon!=='string')throw new CommerceError(400,'COUPON_INVALID','Enter a valid coupon code.');
  const address=validation.address;
  const suppliedKey=keyOf(body.idempotencyKey,strict);
  const fingerprint=await digest(checkoutFingerprintInput(body,address,strict,simulation));
  if(suppliedKey){const replay=await checkoutReplay(user,suppliedKey,fingerprint,database);if(replay)return replay}
  const snapshot=await readCart(user,database);
  const expectedVersion=versionOf(body.expectedVersion,snapshot.version);
  const key=suppliedKey??`legacy:${expectedVersion}:${fingerprint}`;
  if(!suppliedKey){
    const replay=await checkoutReplay(user,key,fingerprint,database);if(replay)return replay;
    // Old clients have no key/revision. An uncertain retry after a successful clear
    // can recover only its recent identical legacy payload, never another guest's.
    if(!snapshot.items.length&&body.expectedVersion===undefined){
      const recent=await database.prepare('SELECT request_key FROM checkout_requests WHERE user=? AND fingerprint=? AND created_at>=? ORDER BY created_at DESC LIMIT 1').bind(user,fingerprint,new Date(Date.now()-10*60*1000).toISOString()).first<{request_key:string}>();
      if(recent){const recovered=await checkoutReplay(user,recent.request_key,fingerprint,database);if(recovered)return recovered}
    }
  }
  if(!snapshot.items.length)throw new CommerceError(400,'CART_EMPTY','Your cart is empty.',{cart:snapshot});
  if(expectedVersion!==snapshot.version)throw new CommerceError(409,'CART_CHANGED','Your cart changed. Review the latest order summary.',{cart:snapshot});
  if(snapshot.issues.length){const issue=snapshot.issues[0];throw new CommerceError(409,issue.code,issue.message,{...issue,cart:snapshot})}
  const coupon=body.coupon===undefined?snapshot.quote.coupon:typeof body.coupon==='string'?normalizeCoupon(body.coupon)||null:null;
  const context=await couponContext(user,coupon,database);
  const quote=calculateQuote(snapshot.quote.subtotalPaise,coupon,context);
  if(quote.couponError)throw new CommerceError(409,quote.couponError.code,quote.couponError.message,{cart:snapshot});
  if(body.expectedTotal!==undefined&&body.expectedTotal!==quote.total)throw new CommerceError(409,'TOTAL_CHANGED','The order total changed. Review it before confirming.',{cart:snapshot,quote});
  const failure=simulationFailure(simulation);
  if(failure)throw new CommerceError(failure.status,failure.code,failure.error,{paymentStatus:simulation,cart:snapshot});
  const id=crypto.randomUUID();const guardId=crypto.randomUUID();const createdAt=now();
  const couponExpiry=coupon?couponRules[coupon]?.expiresAt:undefined;
  const orderItems={products:snapshot.items,coupon,subtotal:quote.subtotal,discount:quote.discount,paymentMethod:body.paymentMethod,status:'demo-confirmed',contractVersion:strict?2:1,createdAt};
  try{
    await database.batch([
      database.prepare('INSERT OR IGNORE INTO cart_state(user,version) VALUES(?,0)').bind(user),
      guard(database,guardId,user,expectedVersion),
      ...(couponExpiry!==undefined?[database.prepare('INSERT INTO commerce_guards(id,permitted) VALUES(?,CASE WHEN unixepoch(\'now\')<? THEN 1 ELSE 0 END)').bind(`${guardId}:expiry`,couponExpiry/1000)]:[]),
      database.prepare('INSERT INTO checkout_requests(user,request_key,fingerprint,order_id,created_at) VALUES(?,?,?,?,?)').bind(user,key,fingerprint,id,createdAt),
      ...(coupon?[database.prepare('INSERT INTO coupon_redemptions(order_id,user,code,created_at) VALUES(?,?,?,?)').bind(id,user,coupon,createdAt)]:[]),
      database.prepare('INSERT INTO orders(id,user,items,total,address) VALUES(?,?,?,?,?)').bind(id,user,JSON.stringify(orderItems),quote.total,JSON.stringify(address)),
      database.prepare('DELETE FROM cart WHERE user=?').bind(user),
      database.prepare('UPDATE cart_state SET coupon=NULL,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE user=? AND coupon IS NOT NULL').bind(user),
      database.prepare('DELETE FROM commerce_guards WHERE id IN (?,?)').bind(guardId,`${guardId}:expiry`),
    ]);
  }catch{
    // Check the ledger before version errors: a successful identical request has
    // already cleared the cart and therefore necessarily changed its revision.
    const replay=await checkoutReplay(user,key,fingerprint,database);if(replay)return replay;
    const current=await readCart(user,database);
    if(current.version!==expectedVersion)throw new CommerceError(409,'CART_CHANGED','Your cart changed. Review the latest order summary.',{cart:current});
    const fresh=calculateQuote(snapshot.quote.subtotalPaise,coupon,await couponContext(user,coupon,database));
    if(fresh.couponError)throw new CommerceError(409,fresh.couponError.code,fresh.couponError.message,{cart:current});
    throw new CommerceError(503,'ORDER_SAVE_FAILED','Could not place the demo order. Retry safely with the same confirmation.');
  }
  return {id,subtotal:quote.subtotal,discount:quote.discount,total:quote.total,coupon,paymentMethod:body.paymentMethod,status:'demo-confirmed',replayed:false,cart:await readCart(user,database)};
}
export function errorResponse(error:unknown){
  if(error instanceof CommerceError)return Response.json({error:error.message,code:error.code,...error.details},{status:error.status,headers:{'Cache-Control':'private, no-store'}});
  return Response.json({error:'The shop is temporarily unavailable. Please try again.',code:'SHOP_UNAVAILABLE'},{status:503,headers:{'Cache-Control':'private, no-store'}});
}
