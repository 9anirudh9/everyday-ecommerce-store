'use client';

import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {useEffect} from 'react';
import { ShoppingBag } from 'lucide-react';
import SearchForm from './search-form';
import { useLanguage } from './language-provider';

export default function SiteFrame({ children }: { children: React.ReactNode }) {
  const { language, chooseLanguage, t } = useLanguage();
  const pathname=usePathname();
  useEffect(()=>{
    document.title=t(pathname==='/search'?'Search plants & home accessories | Everyday':'Everyday — Little things. Lovely spaces.');
    document.querySelector('meta[name="description"]')?.setAttribute('content',t('Shop simple home accessories at Everyday. A demo ecommerce store.'));
  },[language,pathname,t]);
  return <>
    <div className="announcement">{t('A little something for your everyday.')} <span>{t('Free delivery on every order.')}</span></div>
    <header>
      <Link href="/" className="logo">everyday<span>®</span></Link>
      <nav aria-label={t('Shop')}>
        <Link href="/">{t('Home')}</Link>
        <Link href="/products">{t('Shop')}</Link>
        <Link href="/accessories">{t('Accessories')}</Link>
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
        <Link href="/cart" className="bag" aria-label={t('Shopping cart')}><ShoppingBag size={20}/><span>{t('Cart')}</span></Link>
      </div>
    </header>
    {children}
    <footer>
      <Link href="/" className="logo">everyday<span>®</span></Link>
      <p>{t('Good things for your everyday.')}</p>
      <div><a href="https://dummyjson.com" target="_blank" rel="noreferrer">{t('Product images: DummyJSON')}</a><span>{t('Demo store · No real transactions')}</span></div>
    </footer>
  </>;
}
