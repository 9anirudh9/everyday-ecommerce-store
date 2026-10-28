import {products} from '@/lib/products';
import {apiJson,methodNotAllowed} from '@/lib/api-contract';

export const dynamic='force-dynamic';
export function GET(request:Request){
  const categories=[...new Set(products.map(product=>product.category))];
  return apiJson(request,{categories});
}
const deny=(request:Request)=>methodNotAllowed(request,'GET');
export {deny as POST,deny as PUT,deny as PATCH,deny as DELETE,deny as OPTIONS};
