import {products,type Product} from './products';
import {searchProducts} from './search';
import {localizeProduct,type Language} from './i18n';

export type CatalogQuery={
  q:string;
  category:'all'|'Home'|'Accessories';
  minPrice:number|null;
  maxPrice:number|null;
  inStock:boolean;
  sort:'featured'|'price-asc'|'price-desc'|'name';
  page:number;
  rating:number;
};
export type CatalogResult={items:Product[];total:number;page:number;pageSize:number;totalPages:number;query:CatalogQuery};
export const catalogPageSize=10;

export function parseCatalogQuery(params:URLSearchParams):{query:CatalogQuery;error?:string}{
  const category=params.get('category')||'all';
  const sort=params.get('sort')||'featured';
  const value=(key:string)=>{
    const raw=params.get(key);
    return raw===null||raw.trim()===''?null:Number(raw);
  };
  const minPrice=value('minPrice'),maxPrice=value('maxPrice');
  const rating=value('rating')??0;
  const page=value('page')??1;
  const query:CatalogQuery={q:(params.get('q')||'').trim().slice(0,120),
    category:category==='Home'||category==='Accessories'?category:'all',minPrice,maxPrice,
    inStock:params.get('inStock')==='true'||params.get('inStock')==='1',
    sort:['featured','price-asc','price-desc','name'].includes(sort)?sort as CatalogQuery['sort']:'featured',page,rating};
  if(!['all','Home','Accessories'].includes(category))return {query,error:'Choose a valid category.'};
  if(!['featured','price-asc','price-desc','name'].includes(sort))return {query,error:'Choose a valid sort order.'};
  if([minPrice,maxPrice].some(price=>price!==null&&(!Number.isFinite(price)||price<0||price>10000000)))return {query,error:'Enter valid non-negative price limits.'};
  if(minPrice!==null&&maxPrice!==null&&minPrice>maxPrice)return {query,error:'Minimum price must not exceed maximum price.'};
  if(!Number.isFinite(rating)||rating<0||rating>5)return {query,error:'Choose a rating between 0 and 5.'};
  if(!Number.isInteger(page)||page<1)return {query,error:'Choose a valid page number.'};
  return {query};
}

export function selectCatalog(query:CatalogQuery,language:Language='en'):CatalogResult{
  const matches=searchProducts(query.q,language).filter(product=>
    (query.category==='all'||product.category===query.category)&&
    (query.minPrice===null||product.price>=query.minPrice)&&
    (query.maxPrice===null||product.price<=query.maxPrice)&&
    (!query.inStock||product.stock>0)&&product.rating>=query.rating);
  matches.sort((a,b)=>{
    const primary=query.sort==='price-asc'?a.price-b.price:
      query.sort==='price-desc'?b.price-a.price:
      query.sort==='name'?localizeProduct(a,language).name.localeCompare(localizeProduct(b,language).name,language):0;
    return primary||a.id-b.id;
  });
  const total=matches.length;
  const totalPages=Math.max(1,Math.ceil(total/catalogPageSize));
  const page=Math.min(query.page,totalPages);
  return {items:matches.slice((page-1)*catalogPageSize,page*catalogPageSize),total,page,pageSize:catalogPageSize,totalPages,query:{...query,page}};
}

export function productById(id:number){return products.find(product=>product.id===id)}

export function relatedProducts(product:Product,limit=4){
  return products.filter(candidate=>candidate.id!==product.id&&candidate.category===product.category)
    .sort((a,b)=>(Number(b.variantGroup===product.variantGroup&&!!product.variantGroup)-Number(a.variantGroup===product.variantGroup&&!!product.variantGroup))||Math.abs(a.price-product.price)-Math.abs(b.price-product.price)||a.id-b.id)
    .slice(0,limit);
}
