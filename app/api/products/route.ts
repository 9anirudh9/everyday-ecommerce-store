import {parseCatalogQuery,selectCatalog} from '@/lib/catalog';

export const dynamic='force-dynamic';

export async function GET(request:Request){
  const params=new URL(request.url).searchParams;
  const {query,error}=parseCatalogQuery(params);
  const headers={'Cache-Control':'no-store'};
  if(error)return Response.json({error,code:'INVALID_CATALOG_QUERY'},{status:400,headers});
  return Response.json(selectCatalog(query,params.get('lang')==='fr'?'fr':'en'),{headers});
}
