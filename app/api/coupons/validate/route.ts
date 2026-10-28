import {shopSession} from '@/lib/shop-session';
import {CommerceError,errorResponse,validateAndApplyCoupon,type CommerceBody} from '@/lib/commerce';

export const dynamic='force-dynamic';
export async function POST(request:Request){
  try{
    if(request.headers.get('origin')!==new URL(request.url).origin)throw new CommerceError(403,'INVALID_ORIGIN','Invalid request');
    let input:unknown;
    try{input=await request.json()}catch{throw new CommerceError(400,'INVALID_BODY','Enter a valid request body.')}
    if(!input||typeof input!=='object'||Array.isArray(input))throw new CommerceError(400,'INVALID_BODY','Enter a valid request body.');
    const user=await shopSession();
    return Response.json(await validateAndApplyCoupon(user.userId,input as CommerceBody),{headers:{'Cache-Control':'private, no-store'}});
  }catch(error){return errorResponse(error)}
}
