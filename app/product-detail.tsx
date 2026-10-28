'use client';
/* eslint-disable @next/next/no-html-link-for-pages -- Preserve the storefront's verified native navigation. */
import {useEffect,useState,type ReactNode} from 'react';
import {Minus,Plus,ShoppingBag} from 'lucide-react';
import {money,type Product} from '@/lib/products';
import {isProduct} from '@/lib/product-contract';
import {localizeCategory,localizeProduct} from '@/lib/i18n';
import {useLanguage} from './language-provider';
import {useProductCart} from './use-product-cart';
import ProductMedia from './product-media';
import ProductGrid from './product-grid';

type DetailResult={product:Product;related:Product[]};
export default function ProductDetail({id,wishlistSlot}:{id:number;wishlistSlot?:ReactNode}){
  const {language,t}=useLanguage();
  const [attempt,setAttempt]=useState(0);
  const key=`${id}|${attempt}`;
  const [state,setState]=useState<{key:string;data?:DetailResult;error?:string;missing?:boolean}>({key:''});
  const [quantity,setQuantity]=useState('1');
  const [quantityError,setQuantityError]=useState('');
  const {items,status,busy,error,addProduct}=useProductCart();
  useEffect(()=>{
    const controller=new AbortController();let timedOut=false;
    const timer=setTimeout(()=>{timedOut=true;controller.abort()},12000);
    async function load(){
      try{
        const response=await fetch(`/api/products/${id}`,{cache:'no-store',signal:controller.signal});
        if(response.status===404){if(!controller.signal.aborted)setState({key,missing:true});return}
        const data=await response.json() as DetailResult;
        if(!response.ok||!isProduct(data.product)||data.product.id!==id||!Array.isArray(data.related)||!data.related.every(isProduct))throw Error('Could not load this product. Please try again.');
        if(!controller.signal.aborted)setState({key,data});
      }catch{if(!controller.signal.aborted||timedOut)setState({key,error:timedOut?'The request timed out. Please try again.':'Could not load this product. Please try again.'})}
      finally{clearTimeout(timer)}
    }
    void load();return ()=>{clearTimeout(timer);controller.abort()};
  },[id,key]);
  if(state.key!==key)return <section className="catalog-state" role="status"><p>{t('Loading product…')}</p></section>;
  if(state.missing)return <section className="catalog-state"><h1>{t('Product not found')}</h1><p>{t('This product is no longer available. Explore the collection instead.')}</p><a className="primary" href="/products">{t('Back to products')}</a></section>;
  if(state.error||!state.data)return <section className="catalog-state" role="alert"><h1>{t('We could not load this product.')}</h1><p>{t(state.error??'Could not load this product. Please try again.')}</p><button type="button" className="primary" onClick={()=>setAttempt(value=>value+1)}>{t('Try again')}</button><a href="/products">{t('Back to products')}</a></section>;
  const original=state.data.product;
  const product=localizeProduct(original,language);
  const inCart=items.find(item=>item.product===id)?.qty??0;
  const maximum=Math.max(0,Math.min(10,product.stock)-inCart);
  const amount=Number(quantity);
  async function add(){
    if(!Number.isInteger(amount)||amount<1||amount>maximum){setQuantityError(t('Choose a quantity within the available stock.'));return}
    setQuantityError('');
    const result=await addProduct(original,amount);
    if(result.ok)setQuantity('1');
    else if(result.conflict){
      const {currentPrice,availableStock}=result.conflict;
      setState(current=>current.data?{...current,data:{...current.data,product:{...current.data.product,...(typeof currentPrice==='number'?{price:currentPrice}:{}),...(typeof availableStock==='number'?{stock:availableStock}:{})}}}:current);
    }
  }
  return <>
    <nav className="breadcrumb" aria-label={t('Breadcrumb')}><a href="/products">{t('All products')}</a><span aria-hidden="true"> / </span><span aria-current="page">{product.name}</span></nav>
    <section className="detail enhanced-detail">
      <ProductMedia key={id} images={product.images} name={product.name}/>
      <div className="detail-copy"><span className="eyebrow">{localizeCategory(product.category,language).toLocaleUpperCase(language)}</span><h1>{product.name}</h1><p className="price">{money(product.price)}</p><p>{product.description}</p>
        <p className={`detail-stock ${product.stock===0?'stock-unavailable':'stock-available'}`}>{product.stock===0?t('Out of stock'):t('{count} available · demo stock',{count:product.stock})}</p>
        <p className="demo-rating">★ {product.rating.toFixed(1)} / 5 · {t('Demo rating')}</p>
        {product.variantGroup&&<div className="variant-choices"><span>{t('Choose an option')}</span><div>{[original,...state.data.related.filter(item=>item.variantGroup===product.variantGroup)].map(item=><a key={item.id} href={`/products/${item.id}`} aria-current={item.id===id?'true':undefined}>{item.variantLabel?t(item.variantLabel):localizeProduct(item,language).name}</a>)}</div></div>}
        <div className="quantity-field"><label htmlFor="product-quantity">{t('Quantity')}</label><div className="quantity"><button type="button" aria-label={t('Decrease quantity')} disabled={maximum===0||!Number.isFinite(amount)||amount<=1} onClick={()=>setQuantity(String(amount-1))}><Minus size={17}/></button><input id="product-quantity" type="number" min="1" max={maximum||1} step="1" value={quantity} disabled={maximum===0} onChange={event=>setQuantity(event.target.value)}/><button type="button" aria-label={t('Increase quantity')} disabled={maximum===0||!Number.isFinite(amount)||amount>=maximum} onClick={()=>setQuantity(String(amount+1))}><Plus size={17}/></button></div><small>{t('Maximum {count} per cart',{count:Math.min(10,product.stock)})}</small></div>
        {inCart>0&&<p className="cart-note">{t('Already in your cart: {count}',{count:inCart})}</p>}
        {(error||quantityError)&&<p role="alert" className="product-error">{quantityError||error}</p>}
        <button type="button" className="primary detail-add" disabled={busy||status!=='ready'||maximum===0} onClick={()=>void add()}>{product.stock===0?t('Out of stock'):maximum===0?t('Cart limit reached'):t(busy?'Adding…':'Add to cart')}<ShoppingBag size={18}/></button>
        {wishlistSlot}
        <a className="text-link" href="/cart">{t('View your cart →')}</a><div className="details-note">{t('Free delivery · Prices include taxes')}<br/>{t('Sample product for demo shopping.')}<br/>{t('Stock is demonstration data, not an inventory reservation.')}</div>
      </div>
    </section>
    {state.data.related.length>0&&<section className="related-products"><div className="section-head"><h2>{t('You may also like')}</h2><a href="/products">{t('All products')}</a></div><ProductGrid products={state.data.related}/></section>}
  </>;
}
