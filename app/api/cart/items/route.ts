import {shopSession} from '@/lib/shop-session';
import {mutateCart,CommerceError} from '@/lib/commerce';
import {apiBody,apiError,apiJson,methodNotAllowed,requireMutationContract,requireSameOrigin} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export async function POST(request:Request){
  try{
    requireSameOrigin(request);
    const body=await apiBody(request,['product','qty','expectedPrice','expectedVersion','idempotencyKey']);
    requireMutationContract(body);
    if(!Number.isSafeInteger(body.product)||Number(body.product)<1)throw new CommerceError(400,'INVALID_PRODUCT','Provide a positive product ID.');
    if(!Number.isInteger(body.qty)||Number(body.qty)<1)throw new CommerceError(400,'INVALID_QUANTITY','Provide an absolute positive quantity.');
    return apiJson(request,await mutateCart((await shopSession()).userId,{...body,action:'update'}));
  }catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'POST');
export {deny as GET,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
