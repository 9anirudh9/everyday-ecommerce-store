import {productById,relatedProducts} from '@/lib/catalog';

export const dynamic='force-dynamic';

export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}){
  const {id}=await params;
  const product=/^\d+$/.test(id)?productById(Number(id)):undefined;
  const headers={'Cache-Control':'no-store'};
  if(!product)return Response.json({error:'Product not found.',code:'PRODUCT_NOT_FOUND'},{status:404,headers});
  return Response.json({product,related:relatedProducts(product)},{headers});
}
