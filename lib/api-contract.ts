import {CommerceError,type CommerceBody} from './commerce';
import type {Product} from './products';

const headers=(id:string,extra:HeadersInit={})=>{
  const result=new Headers(extra);
  result.set('Cache-Control','private, no-store');
  result.set('X-API-Version','1');
  result.set('X-Request-ID',id);
  return result;
};
const requestIds=new WeakMap<Request,string>();
export function requestId(request:Request){
  let id=requestIds.get(request);
  if(!id){id=crypto.randomUUID();requestIds.set(request,id)}
  return id;
}
export function apiJson(request:Request,value:unknown,status=200,extra:HeadersInit={}){
  return Response.json(value,{status,headers:headers(requestId(request),extra)});
}
async function discardRejectedBody(request:Request){
  // Finish small rejected uploads before replying. Leaving unread request bytes
  // behind can corrupt the next local keep-alive exchange. Never parse or use
  // untrusted contents, and bound draining so oversized uploads are cancelled.
  if(!request.body||request.bodyUsed)return;
  const reader=request.body.getReader();
  try{
    let bytes=0;
    while(bytes<=65536){
      const part=await reader.read();
      if(part.done)return;
      bytes+=part.value.byteLength;
    }
    await reader.cancel();
  }catch{/* Preserve the intended safe error even if the upload disconnects. */}
  finally{reader.releaseLock()}
}
export async function apiError(request:Request,error:unknown){
  await discardRejectedBody(request);
  const known=error instanceof CommerceError;
  const status=known?error.status:503;
  const code=known?error.code:'SHOP_UNAVAILABLE';
  const message=known?error.message:'The shop is temporarily unavailable. Please try again.';
  return apiJson(request,{...(known?error.details:{}),code,message,error:message,requestId:requestId(request)},status);
}
export async function methodNotAllowed(request:Request,allow:string){
  await discardRejectedBody(request);
  return apiJson(request,{code:'METHOD_NOT_ALLOWED',message:'Method not allowed.',error:'Method not allowed.',requestId:requestId(request)},405,{Allow:allow});
}
export function requireSameOrigin(request:Request){
  if(request.headers.get('origin')!==new URL(request.url).origin)throw new CommerceError(403,'INVALID_ORIGIN','Invalid request origin.');
}
export async function apiBody(request:Request,fields:readonly string[]|null):Promise<CommerceBody>{
  let input:unknown;
  try{input=await request.json()}catch{throw new CommerceError(400,'INVALID_BODY','Enter a valid JSON object.')} 
  if(!input||typeof input!=='object'||Array.isArray(input))throw new CommerceError(400,'INVALID_BODY','Enter a valid JSON object.');
  const body=input as CommerceBody;
  const unknown=fields?Object.keys(body).find(field=>!fields.includes(field)):undefined;
  if(unknown)throw new CommerceError(400,'UNKNOWN_FIELD',`Unexpected field: ${unknown}.`);
  return body;
}
export function requireMutationContract(body:CommerceBody){
  if(!Number.isSafeInteger(body.expectedVersion)||Number(body.expectedVersion)<0)throw new CommerceError(400,'INVALID_CART_VERSION','Provide a non-negative expectedVersion.');
  if(typeof body.idempotencyKey!=='string'||!/^[A-Za-z0-9._:-]{8,128}$/.test(body.idempotencyKey))throw new CommerceError(400,'INVALID_IDEMPOTENCY_KEY','Provide a valid idempotencyKey.');
}
export function positiveId(raw:string){
  const id=Number(raw);
  if(!/^[1-9]\d*$/.test(raw)||!Number.isSafeInteger(id))throw new CommerceError(400,'INVALID_ID','Use a positive integer ID.');
  return id;
}
export function productDto(product:Product){return {...product,priceMinor:Math.round(product.price*100),currency:'INR' as const}}
