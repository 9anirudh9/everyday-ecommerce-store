'use client';
import {useEffect,useState} from 'react';
import {usePathname,useSearchParams} from 'next/navigation';
import {parseCatalogQuery} from '@/lib/catalog';
import type {Product} from '@/lib/products';
import {isProduct} from '@/lib/product-contract';
import {useLanguage} from './language-provider';
import ProductGrid from './product-grid';

type CatalogResult={items:Product[];total:number;page:number;pageSize:number;totalPages:number};
function isResult(value:unknown):value is CatalogResult{
  if(!value||typeof value!=='object')return false;
  const data=value as CatalogResult;
  return Array.isArray(data.items)&&data.items.length<=10&&data.items.every(isProduct)&&[data.total,data.page,data.pageSize,data.totalPages].every(Number.isInteger)&&data.page>=1&&data.pageSize===10&&data.total>=0&&data.totalPages>=1;
}

export default function CatalogView({mode}:{mode:'products'|'search'|'accessories'}){
  const {language,t}=useLanguage();
  const pathname=usePathname();
  const search=useSearchParams();
  const params=new URLSearchParams(search.toString());
  if(mode==='accessories'&&!params.has('category'))params.set('category','Accessories');
  const criteria=params.toString();
  const {query,error:validationError}=parseCatalogQuery(params);
  const [attempt,setAttempt]=useState(0);
  const key=`${criteria}|${language}|${attempt}`;
  const [state,setState]=useState<{key:string;data?:CatalogResult;error?:string}>({key:''});
  useEffect(()=>{
    if(validationError)return;
    const controller=new AbortController();
    let timedOut=false;
    const timer=setTimeout(()=>{timedOut=true;controller.abort()},12000);
    const requestParams=new URLSearchParams(criteria);requestParams.set('lang',language);
    async function load(){
      try{
        const response=await fetch(`/api/products?${requestParams}`,{signal:controller.signal,cache:'no-store'});
        const data=await response.json();
        if(!response.ok)throw Error('Could not load products. Please try again.');
        if(!isResult(data))throw Error('Could not load products. Please try again.');
        if(!controller.signal.aborted)setState({key,data});
      }catch(error){
        if(!controller.signal.aborted||timedOut)setState({key,error:timedOut?'The request timed out. Please try again.':(error as Error).message});
      }finally{clearTimeout(timer)}
    }
    void load();
    return ()=>{clearTimeout(timer);controller.abort()};
  },[criteria,language,key,validationError]);
  const pending=state.key!==key;
  const result=state.key===key?state.data:undefined;
  const failure=validationError||(state.key===key?state.error:undefined);
  const reset=mode==='accessories'?'/accessories':mode==='search'?'/search':'/products';
  const pageHref=(page:number)=>{
    const next=new URLSearchParams(criteria);next.set('page',String(page));return `${pathname}?${next}`;
  };
  return <section className="catalog-page">
    <div className={`page-head ${mode==='accessories'?'collection-head':''}`}>
      <span className="eyebrow">{t(mode==='search'?'FIND YOUR EVERYDAY FAVOURITE':mode==='accessories'?'Accessories':'THE FULL COLLECTION')}</span>
      <h1>{mode==='search'?(query.q?t('Results for “{query}”',{query:query.q}):t('Search the whole collection.')):t(mode==='accessories'?'Finishing touches for every day.':'Small touches. Big difference.')}</h1>
      <p>{t('Find your next everyday favourite with filters that fit.')}</p>
    </div>
    <form className="catalog-filters" action={mode==='search'?'/search':'/products'} method="get" aria-label={t('Catalog filters')}>
      <div className="catalog-search"><label htmlFor="catalog-query">{t('Search catalog')}</label><input id="catalog-query" type="search" name="q" defaultValue={query.q} maxLength={120} placeholder={t('Search plants, watches, bags…')}/></div>
      <div><label htmlFor="catalog-category">{t('Category')}</label><select id="catalog-category" name="category" defaultValue={query.category}><option value="all">{t('All categories')}</option><option value="Home">{t('Home collection')}</option><option value="Accessories">{t('Accessories')}</option></select></div>
      <div><label htmlFor="catalog-min">{t('Minimum price')}</label><input id="catalog-min" type="number" name="minPrice" min="0" step="1" defaultValue={query.minPrice??''} placeholder="₹ 0"/></div>
      <div><label htmlFor="catalog-max">{t('Maximum price')}</label><input id="catalog-max" type="number" name="maxPrice" min="0" step="1" defaultValue={query.maxPrice??''} placeholder={t('No maximum')}/></div>
      <div><label htmlFor="catalog-rating">{t('Minimum rating')}</label><select id="catalog-rating" name="rating" defaultValue={query.rating}><option value="0">{t('Any rating')}</option><option value="3">3 ★ +</option><option value="4">4 ★ +</option><option value="4.5">4.5 ★ +</option></select></div>
      <div><label htmlFor="catalog-sort">{t('Sort by')}</label><select id="catalog-sort" name="sort" defaultValue={query.sort}><option value="featured">{t('Featured')}</option><option value="price-asc">{t('Price: low to high')}</option><option value="price-desc">{t('Price: high to low')}</option><option value="name">{t('Name')}</option></select></div>
      <label className="stock-filter"><input type="checkbox" name="inStock" value="true" defaultChecked={query.inStock}/>{t('In stock only')}</label>
      <div className="filter-actions"><button className="primary" type="submit">{t('Apply filters')}</button><a href={reset}>{t('Reset filters')}</a></div>
      <small>{t('Ratings and stock are demo catalog data.')}</small>
    </form>
    {failure?<div className="catalog-state" role="alert"><h2>{t('We could not load this collection.')}</h2><p>{t(failure)}</p>{!validationError&&<button className="primary" type="button" onClick={()=>setAttempt(value=>value+1)}>{t('Try again')}</button>}<a href={reset}>{t('Reset filters')}</a></div>
    :pending?<div className="catalog-state" role="status" aria-live="polite"><p>{t('Loading products…')}</p><div className="catalog-skeleton" aria-hidden="true">{Array.from({length:8},(_,index)=><span key={index}/>)}</div></div>
    :result&&<div data-testid="catalog-results">
      <div className="catalog-results-heading"><p role="status" data-testid="catalog-result-count">{t(result.total===1?'{count} product found':'{count} products found',{count:result.total})}</p>{result.total>0&&<span>{t('Showing {start}–{end} of {total}',{start:(result.page-1)*10+1,end:Math.min(result.page*10,result.total),total:result.total})}</span>}</div>
      {query.page!==result.page&&<p className="catalog-feedback" role="status">{t('That page is unavailable. Showing the closest available page.')}</p>}
      {result.total?<><ProductGrid products={result.items}/>{result.totalPages>1&&<nav className="pagination" aria-label={t('Catalog pages')}>
        {result.page>1&&<a href={pageHref(result.page-1)} aria-label={t('Previous page')}>{t('Previous')}</a>}
        {Array.from({length:result.totalPages},(_,index)=>index+1).map(page=><a key={page} href={pageHref(page)} aria-label={t('Page {number}',{number:page})} aria-current={page===result.page?'page':undefined}>{page}</a>)}
        {result.page<result.totalPages&&<a href={pageHref(result.page+1)} aria-label={t('Next page')}>{t('Next')}</a>}
      </nav>}</>:<div className="empty" role="status"><h2>{t('No matching products.')}</h2><p>{t('Try a shorter search or remove a filter.')}</p><a href={reset} className="primary">{t('Reset filters')}</a></div>}
    </div>}
  </section>;
}
