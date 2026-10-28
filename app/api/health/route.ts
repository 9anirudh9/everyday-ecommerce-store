import {db} from '@/lib/db';
import {apiJson,methodNotAllowed,requestId} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export async function GET(request:Request){
  try{
    const row=await db().prepare('SELECT 1 AS healthy').first<{healthy:number}>();
    if(row?.healthy!==1)throw new Error('Health check failed');
    return apiJson(request,{status:'ok'});
  }catch{return apiJson(request,{code:'SERVICE_UNAVAILABLE',message:'Service unavailable.',error:'Service unavailable.',requestId:requestId(request)},503)}
}
const deny=(request:Request)=>methodNotAllowed(request,'GET');
export {deny as POST,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
