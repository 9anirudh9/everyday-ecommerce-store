'use client';
/* eslint-disable @next/next/no-html-link-for-pages -- Native storefront navigation. */
import {useEffect,useRef,useState} from 'react';
import {Minus,Plus,ShoppingBag} from 'lucide-react';
import {toast} from 'sonner';
import {products,money} from '@/lib/products';
import {localizeProduct} from '@/lib/i18n';
import {useCart} from './cart-provider';
import {useLanguage} from './language-provider';
import OrderSummary from './order-summary';
import ProductImage from './product-image';

export default function CartPanel(){
  const cart=useCart();const {language,t}=useLanguage();
  const dialog=useRef<HTMLDialogElement>(null),clearTrigger=useRef<HTMLButtonElement>(null);
  const [removed,setRemoved]=useState<{product:number;qty:number;version:number}|null>(null);
  useEffect(()=>{if(!removed)return;const timer=setTimeout(()=>setRemoved(null),8000);return ()=>clearTimeout(timer)},[removed]);
  async function remove(product:number,qty:number){const result=await cart.changeQuantity(product,0);if(result.ok){const snapshot=result.data?.cart as {version?:number}|undefined;setRemoved({product,qty,version:snapshot?.version??cart.version+1});toast.success(t('Item removed'))}}
  async function undo(){if(!removed)return;if(cart.version!==removed.version||cart.items.some(item=>item.product===removed.product)){setRemoved(null);toast.error(t('Your cart changed. Undo was cancelled to preserve the newer changes.'));return}const result=await cart.changeQuantity(removed.product,removed.qty,removed.version);if(result.ok)setRemoved(null)}
  const localSubtotal=cart.items.reduce((sum,item)=>sum+(products.find(product=>product.id===item.product)?.price??0)*item.qty,0);
  return <section><div className="page-head"><span className="eyebrow">{t('YOUR EVERYDAY FINDS')}</span><h1>{t('Your shopping cart')}</h1><p>{t('Use EVERYDAY at checkout for 50% off.')}</p></div>
    {!cart.hasLoaded&&cart.status==='loading'?<p role="status">{t('Loading your cart…')}</p>:<>
      {cart.status==='error'&&<div role="alert" className="recovery-banner"><p>{cart.error}</p><button type="button" onClick={()=>void cart.refresh()}>{t('Try again')}</button></div>}
      {cart.stale&&cart.hasLoaded&&<p className="recovery-banner" role="status">{t('Refreshing your cart. Checkout is paused until it is up to date.')}</p>}
      {cart.mutationError&&<div className="recovery-banner" role="alert"><p>{cart.mutationError.message}</p>{cart.mutationError.canRetry?<button type="button" disabled={cart.busy} onClick={()=>void cart.retryLastMutation()}>{t('Retry cart update')}</button>:<button type="button" disabled={cart.busy} onClick={()=>{cart.clearMutationError();void cart.refresh()}}>{t('Review refreshed cart')}</button>}</div>}
      {cart.issues.length>0&&<div className="recovery-banner" role="alert">{cart.issues.map((issue,index)=><p key={`${issue.product}-${index}`}>{t(issue.message)}</p>)}<p>{t('Remove unavailable items or adjust quantities to continue.')}</p></div>}
      {cart.hasLoaded&&localSubtotal!==cart.quote.subtotal&&<div className="recovery-banner" role="alert"><p>{t('Prices changed. Reload the current product prices before checkout.')}</p><a href="/cart">{t('Reload current prices')}</a></div>}
      {removed&&<div className="undo-notice" role="status"><span>{t('Item removed')}</span><button type="button" disabled={cart.busy} onClick={()=>void undo()}>{t('Undo')}</button></div>}
      {!cart.hasLoaded?null:!cart.items.length?<div className="empty"><ShoppingBag size={42}/><h2>{t('Your cart is waiting.')}</h2><p>{t('Find a little something for your home or wardrobe.')}</p><a href="/products" className="primary">{t('Explore products')}</a></div>:<div className="checkout-grid"><div>
        <div className="cart-toolbar"><span>{t('{count} total',{count:cart.items.reduce((sum,item)=>sum+item.qty,0)})}</span><button ref={clearTrigger} type="button" disabled={cart.busy||cart.status!=='ready'} onClick={()=>dialog.current?.showModal()}>{t('Clear cart')}</button></div>
        {cart.items.map(item=>{const found=products.find(product=>product.id===item.product);const product=found?localizeProduct(found,language):null;return <div className="cart-row" key={item.product}>
          {product?<a href={`/products/${product.id}`}><ProductImage key={product.image} src={product.image} alt={product.name}/></a>:<ShoppingBag size={40}/>}
          <div>{product?<a href={`/products/${product.id}`}><h3>{product.name}</h3></a>:<h3>{t('Unavailable product')}</h3>}<p>{product?money(product.price):t('Review this item')}</p><button className="remove" type="button" disabled={cart.busy} onClick={()=>void remove(item.product,item.qty)}>{t('Remove')}</button></div>
          <div className="quantity"><button type="button" aria-label={t('Decrease {product}',{product:product?.name??String(item.product)})} disabled={cart.busy||cart.status!=='ready'||item.qty<=1} onClick={()=>void cart.changeQuantity(item.product,item.qty-1)}><Minus size={16}/></button><span>{item.qty}</span><button type="button" aria-label={t('Increase {product}',{product:product?.name??String(item.product)})} disabled={cart.busy||cart.status!=='ready'||!product||item.qty>=Math.min(10,product.stock)} onClick={()=>void cart.changeQuantity(item.product,item.qty+1)}><Plus size={16}/></button></div><b>{product?money(product.price*item.qty):'—'}</b>
        </div>})}<a className="text-link" href="/products">{t('← Continue shopping')}</a>
      </div><OrderSummary cart/></div>}
    </>}
    <dialog className="confirm-dialog" ref={dialog} aria-labelledby="clear-cart-title" onClose={()=>clearTrigger.current?.focus()}><h2 id="clear-cart-title">{t('Clear your cart?')}</h2><p>{t('All items will be removed. You can keep shopping afterward.')}</p><div><button type="button" onClick={()=>dialog.current?.close()}>{t('Keep items')}</button><button type="button" className="primary" disabled={cart.busy} onClick={()=>{void cart.clearCart().then(result=>{dialog.current?.close();if(result.ok)setRemoved(null)})}}>{t('Clear cart')}</button></div></dialog>
  </section>;
}
