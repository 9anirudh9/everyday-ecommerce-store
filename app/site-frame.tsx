/* eslint-disable @next/next/no-html-link-for-pages -- Native navigation preserves the verified Cart navigation behavior. */
'use client';

import {usePathname} from 'next/navigation';
import {useEffect} from 'react';
import { ShoppingBag } from 'lucide-react';
import SearchForm from './search-form';
import { useLanguage } from './language-provider';
import CartProvider, { useCart } from './cart-provider';

function SiteFrameContent({ children }: { children: React.ReactNode }) {
  const { language, chooseLanguage, t } = useLanguage();
  const { items, status } = useCart();
  const pathname=usePathname();
  const quantity = status === 'ready' ? items.reduce((sum,item)=>sum+item.qty,0) : null;
  const cartLabel = quantity !== null
    ? t('Shopping cart, {count} items', {count:quantity})
    : status === 'error'
      ? `${t('Shopping cart')}, ${t('Cart quantity unavailable')}`
      : t('Shopping cart');
  useEffect(()=>{
    document.title=t(pathname==='/search'?'Search plants & home accessories | Everyday':'Everyday — Little things. Lovely spaces.');
    document.querySelector('meta[name="description"]')?.setAttribute('content',t('Shop simple home accessories at Everyday. A demo ecommerce store.'));
  },[language,pathname,t]);
  return <>
    <div className="announcement">{t('A little something for your everyday.')} <span>{t('Free delivery on every order.')}</span></div>
    <header>
      <a href="/" className="logo">everyday<span>®</span></a>
      <nav aria-label={t('Shop')}>
        <a href="/" aria-current={pathname==='/'?'page':undefined}>{t('Home')}</a>
        <a href="/products" aria-current={pathname==='/products'||pathname.startsWith('/products/')?'page':undefined}>{t('Shop')}</a>
        <a href="/accessories" aria-current={pathname==='/accessories'?'page':undefined}>{t('Accessories')}</a>
      </nav>
      <SearchForm compact />
      <div className="header-right">
        <span className="guest-label">{t('No sign-in needed')}</span>
        <label className="language-control">
          <span>{t('Language')}</span>
          <select aria-label={t('Language')} data-testid="language-switcher" value={language} onChange={event => chooseLanguage(event.target.value as 'en' | 'fr')}>
            <option value="en">English</option><option value="fr">Français</option>
          </select>
        </label>
        <a href="/cart" className="bag" aria-label={cartLabel} aria-current={pathname==='/cart'?'page':undefined}>
          <ShoppingBag size={20}/><span>{t('Cart')}</span>
          {quantity!==null&&<span className="cart-count" aria-hidden="true">{quantity}</span>}
          {status==='error'&&<span className="cart-count cart-count-unavailable" aria-hidden="true">—</span>}
        </a>
      </div>
    </header>
    {children}
    <footer>
      <a href="/" className="logo">everyday<span>®</span></a>
      <p>{t('Good things for your everyday.')}</p>
      <div><a href="https://dummyjson.com" target="_blank" rel="noreferrer">{t('Product images: DummyJSON')}</a><span>{t('Demo store · No real transactions')}</span></div>
    </footer>
  </>;
}

export default function SiteFrame({ children }: { children: React.ReactNode }) {
  return <CartProvider><SiteFrameContent>{children}</SiteFrameContent></CartProvider>;
}
