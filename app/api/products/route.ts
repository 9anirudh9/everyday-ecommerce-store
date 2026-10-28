import {parseCatalogQuery,selectCatalog} from '@/lib/catalog';
import {apiJson,methodNotAllowed,productDto,requestId} from '@/lib/api-contract';

export const dynamic='force-dynamic';

export async function GET(request:Request){
  const params=new URL(request.url).searchParams;
  const {query,error}=parseCatalogQuery(params);
  if(error)return apiJson(request,{error,code:'INVALID_CATALOG_QUERY',message:error,requestId:requestId(request)},400);
  const result=selectCatalog(query,params.get('lang')==='fr'?'fr':'en');
  return apiJson(request,{...result,items:result.items.map(productDto)});
}
const deny=(request:Request)=>methodNotAllowed(request,'GET');
export {deny as POST,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
