import {shopSession} from '@/lib/shop-session';
import {errorResponse,getOrder} from '@/lib/commerce';

export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}){
  try{
    const {id}=await params;
    const user=await shopSession();
    return Response.json(await getOrder(user.userId,id),{headers:{'Cache-Control':'private, no-store'}});
  }catch(error){return errorResponse(error)}
}
