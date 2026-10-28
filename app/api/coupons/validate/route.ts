import {shopSession} from '@/lib/shop-session';
import {validateAndApplyCoupon} from '@/lib/commerce';
import {apiBody,apiError,apiJson,methodNotAllowed,requireSameOrigin} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export async function POST(request:Request){
  try{
    requireSameOrigin(request);
    // Existing coupon clients may omit revision/key and send ignored fields.
    // The service remains authoritative and applies its atomic legacy defaults.
    const body=await apiBody(request,null);
    const user=await shopSession();
    return apiJson(request,await validateAndApplyCoupon(user.userId,body));
  }catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'POST');
export {deny as GET,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
