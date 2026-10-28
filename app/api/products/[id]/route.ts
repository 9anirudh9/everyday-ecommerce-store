import {productById,relatedProducts} from '@/lib/catalog';
import {apiError,apiJson,methodNotAllowed,positiveId,productDto} from '@/lib/api-contract';
import {CommerceError} from '@/lib/commerce';

export const dynamic='force-dynamic';

export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
  try{
    const product=productById(positiveId((await params).id));
    if(!product)throw new CommerceError(404,'PRODUCT_NOT_FOUND','Product not found.');
    return apiJson(request,{product:productDto(product),related:relatedProducts(product).map(productDto)});
  }catch(error){return apiError(request,error)}
}
const deny=(request:Request)=>methodNotAllowed(request,'GET');
export {deny as POST,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
