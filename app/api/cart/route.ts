import {shopSession} from '@/lib/shop-session';
import {readCart} from '@/lib/commerce';
import {apiError,apiJson,methodNotAllowed} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export async function GET(request:Request){
  try{return apiJson(request,await readCart((await shopSession()).userId))}
  catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'GET');
export {deny as POST,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
