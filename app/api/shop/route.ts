import {shopSession} from '@/lib/shop-session';
import {checkout,CommerceError,errorResponse,mutateCart,readCart,type CommerceBody} from '@/lib/commerce';

export const dynamic='force-dynamic';

export async function GET(request:Request){
  try{
    const user=await shopSession();
    const snapshot=await readCart(user.userId);
    const existing=/(?:^|;\s*)__Host-everyday-guest=[a-f0-9]{64}(?:;|$)/.test(request.headers.get('cookie')??'');
    return Response.json({...snapshot,sessionStatus:existing?'active':'new'},{headers:{'Cache-Control':'private, no-store'}});
  }catch(error){return errorResponse(error)}
}

export async function POST(request:Request){
  try{
    if(request.headers.get('origin')!==new URL(request.url).origin)throw new CommerceError(403,'INVALID_ORIGIN','Invalid request');
    let input:unknown;
    try{input=await request.json()}catch{throw new CommerceError(400,'INVALID_BODY','Enter a valid request body.')}
    if(!input||typeof input!=='object'||Array.isArray(input))throw new CommerceError(400,'INVALID_BODY','Enter a valid request body.');
    const body=input as CommerceBody;
    const user=await shopSession();
    const result=body.action==='checkout'?await checkout(user.userId,body):await mutateCart(user.userId,body);
    return Response.json(result,{headers:{'Cache-Control':'private, no-store'}});
  }catch(error){return errorResponse(error)}
}
