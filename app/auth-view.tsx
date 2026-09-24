'use client';
import Link from 'next/link';
import {useLanguage} from './language-provider';

export default function AuthView(){
  const {t}=useLanguage();
  return <main className="auth">
    <span className="eyebrow">{t('SHOP AS A GUEST')}</span>
    <h1>{t('No account needed.')}</h1>
    <p>{t('Your cart is kept securely for this browser, so you can browse and checkout without signing in.')}</p>
    <Link className="primary" href="/products">{t('Continue shopping')}</Link>
  </main>
}
