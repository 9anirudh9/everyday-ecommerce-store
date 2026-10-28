import {shopSession} from '@/lib/shop-session';
import {checkout,CommerceError,mutateCart,readCart,type CommerceBody} from '@/lib/commerce';
import {apiError,apiJson,methodNotAllowed,requireSameOrigin} from '@/lib/api-contract';

export const dynamic='force-dynamic';

export async function GET(request:Request){
  try{
    const user=await shopSession();
    const snapshot=await readCart(user.userId);
    const existing=/(?:^|;\s*)__Host-everyday-guest=[a-f0-9]{64}(?:;|$)/.test(request.headers.get('cookie')??'');
    return apiJson(request,{...snapshot,sessionStatus:existing?'active':'new'});
  }catch(error){return apiError(request,error)}
}

export async function POST(request:Request){
  try{
    requireSameOrigin(request);
    let input:unknown;
    try{input=await request.json()}catch{throw new CommerceError(400,'INVALID_BODY','Enter a valid request body.')}
    if(!input||typeof input!=='object'||Array.isArray(input))throw new CommerceError(400,'INVALID_BODY','Enter a valid request body.');
    const body=input as CommerceBody;
    const user=await shopSession();
    const result=body.action==='checkout'?await checkout(user.userId,body):await mutateCart(user.userId,body);
    return apiJson(request,result);
  }catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'GET, POST');
export {deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
