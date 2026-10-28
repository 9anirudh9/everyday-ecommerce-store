import {shopSession} from '@/lib/shop-session';
import {checkout,CommerceError} from '@/lib/commerce';
import {apiBody,apiError,apiJson,methodNotAllowed,requireMutationContract,requireSameOrigin} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export async function POST(request:Request){
  try{
    requireSameOrigin(request);
    const body=await apiBody(request,['contractVersion','address','paymentMethod','simulation','coupon','expectedVersion','expectedTotal','idempotencyKey']);
    requireMutationContract(body);
    if(body.contractVersion!==2)throw new CommerceError(400,'INVALID_CONTRACT','Use checkout contractVersion 2.');
    if(body.address&&typeof body.address==='object'&&!Array.isArray(body.address)){
      const unknown=Object.keys(body.address).find(field=>!['name','email','phone','street','city','state','pin'].includes(field));
      if(unknown)throw new CommerceError(400,'UNKNOWN_FIELD',`Unexpected address field: ${unknown}.`);
    }
    const result=await checkout((await shopSession()).userId,body);
    return apiJson(request,result,result.replayed?200:201);
  }catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'POST');
export {deny as GET,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
