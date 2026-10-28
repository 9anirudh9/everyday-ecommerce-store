'use client';
/* eslint-disable @next/next/no-html-link-for-pages -- Native storefront navigation. */
import {ArrowRight} from 'lucide-react';
import {products} from '@/lib/products';
import {Toaster} from '@/components/ui/sonner';
import {useLanguage} from './language-provider';
import CatalogView from './catalog-view';
import ProductDetail from './product-detail';
import ProductGrid from './product-grid';
import CartPanel from './cart-panel';
import CheckoutPanel from './checkout-panel';

export default function Shop({view,id}:{view:string;id?:number;query?:string}){
  const {t}=useLanguage();
  return <><Toaster/><main>{view==='home'?<>
    <section className="hero"><div className="hero-copy"><span className="eyebrow">{t('THE EVERYDAY COLLECTION')}</span><h1>{t('Little things.')}<br/>{t('Lovely spaces.')}</h1><p>{t('Simple finds to make your corner of the world feel a little more like you.')}</p><a className="primary" href="/products">{t('Shop the collection')}<ArrowRight size={18}/></a><span className="hero-note">{t('Thoughtful details. Everyday prices.')}</span></div><a className="hero-image" href="/products/46"><img src="/products/46.webp" alt={t('Decorative plant pot from the home collection')}/><span>{t('Find your everyday favourite')}<ArrowRight size={18}/></span></a></section>
    <section><div className="section-head"><div><span className="eyebrow">{t('A FEW GOOD FINDS')}</span><h2>{t('Made for your everyday')}</h2></div><a href="/products">{t('View all products ↗')}</a></div><ProductGrid products={products.slice(0,4)}/></section>
  </>:view==='search'||view==='accessories'||view==='products'?<CatalogView mode={view}/>:view==='product'?<ProductDetail id={id??NaN}/>:view==='cart'?<CartPanel/>:<CheckoutPanel/>}</main></>;
}
