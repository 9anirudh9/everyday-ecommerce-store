'use client';
import {Plus} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {money,type Product} from '@/lib/products';
import {localizeCategory,localizeProduct} from '@/lib/i18n';
import {useLanguage} from './language-provider';
import {useProductCart} from './use-product-cart';
import ProductImage from './product-image';

export default function ProductGrid({products}:{products:Product[]}){
  const {language,t}=useLanguage();
  const {items,status,busy,error,addProduct}=useProductCart();
  return <>{error&&<p className="catalog-feedback" role="alert">{error}</p>}<div className="grid">{products.map(item=>{
    const product=localizeProduct(item,language);
    const qty=items.find(line=>line.product===item.id)?.qty??0;
    const full=qty>=Math.min(10,item.stock);
    return <article className="product-card" key={item.id} data-product-id={item.id}>
      <a href={`/products/${item.id}`} className="photo"><ProductImage key={item.image} src={item.image} alt={product.name} loading="lazy"/><span>{localizeCategory(item.category,language).toLocaleUpperCase(language)}</span></a>
      <div className="card-bottom"><div><a href={`/products/${item.id}`}><h3>{product.name}</h3></a><p>{money(item.price)}</p></div><Button aria-label={t('Add {product} to cart',{product:product.name})} disabled={busy||status!=='ready'||full} variant="outline" size="icon" onClick={()=>void addProduct(item)}><Plus/></Button></div>
      <div className="product-meta"><span className={item.stock===0?'stock-unavailable':'stock-available'}>{item.stock===0?t('Out of stock'):item.stock<=3?t('Only {count} left',{count:item.stock}):t('In stock')}</span><span aria-label={t('Demo rating {rating} out of 5',{rating:item.rating.toFixed(1)})}>★ {item.rating.toFixed(1)}</span></div>
    </article>;
  })}</div></>;
}
