import {shopSession} from '@/lib/shop-session';
import {getOrder} from '@/lib/commerce';
import {apiError,apiJson,methodNotAllowed} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
  try{
    const {id}=await params;
    const user=await shopSession();
    return apiJson(request,await getOrder(user.userId,id));
  }catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'GET');
export {deny as POST,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
