import {shopSession} from '@/lib/shop-session';
import {mutateCart,CommerceError} from '@/lib/commerce';
import {apiBody,apiError,apiJson,methodNotAllowed,positiveId,requireMutationContract,requireSameOrigin} from '@/lib/api-contract';

export const dynamic='force-dynamic';
type Context={params:Promise<{id:string}>};
async function update(request:Request,context:Context,remove:boolean){
  try{
    requireSameOrigin(request);
    const product=positiveId((await context.params).id);
    const body=await apiBody(request,remove?['expectedVersion','idempotencyKey']:['qty','expectedPrice','expectedVersion','idempotencyKey']);
    requireMutationContract(body);
    if(!remove&&(!Number.isInteger(body.qty)||Number(body.qty)<1))throw new CommerceError(400,'INVALID_QUANTITY','Provide an absolute positive quantity.');
    return apiJson(request,await mutateCart((await shopSession()).userId,{...body,product,qty:remove?0:body.qty,action:'update'}));
  }catch(error){return apiError(request,error)}
}
export const PATCH=(request:Request,context:Context)=>update(request,context,false);
export const DELETE=(request:Request,context:Context)=>update(request,context,true);
const deny=(request:Request)=>methodNotAllowed(request,'PATCH, DELETE');
export {deny as GET,deny as POST,deny as PUT,deny as OPTIONS};
