'use client';
import {useState,type FormEvent} from 'react';
import {ArrowRight,Tag,X} from 'lucide-react';
import {money} from '@/lib/products';
import {useCart} from './cart-provider';
import {useLanguage} from './language-provider';

export default function OrderSummary({cart=false}:{cart?:boolean}){
  const {quote,busy,stale,status,applyCoupon,mutationError}=useCart();
  const {t}=useLanguage();
  const [code,setCode]=useState('');
  const [couponError,setCouponError]=useState('');
  async function apply(event:FormEvent){event.preventDefault();setCouponError('');const result=await applyCoupon(code);if(!result.ok)setCouponError(result.error??t('That coupon code is not valid.'));else setCode('')}
  return <aside className="summary"><h2>{t('Order summary')}</h2>
    <div><span>{t('Subtotal')}</span><b>{money(quote.subtotal)}</b></div>
    {quote.coupon&&<div className="discount-line"><span>{quote.coupon}</span><b>−{money(quote.discount)}</b></div>}
    <div><span>{t('Delivery')}</span><b>{t('Free')}</b></div><div className="total"><span>{t('Total')}</span><b>{money(quote.total)}</b></div>
    <p>{t('All prices include taxes.')}</p>
    {cart&&<>
      <form className="coupon-form" onSubmit={event=>void apply(event)}><label htmlFor="coupon">{t('Coupon code')}</label><div><input id="coupon" value={code} onChange={event=>setCode(event.target.value)} placeholder={t('Enter code')} maxLength={30}/><button type="submit" disabled={busy||status!=='ready'}>{t('Apply')}</button></div></form>
      {(couponError||quote.couponError)&&<p className="coupon-error" role={mutationError?undefined:'alert'}>{couponError||t(quote.couponError?.message??'That coupon code is not valid.')}</p>}
      {quote.coupon&&<button className="coupon-applied" type="button" aria-label={t('Remove coupon')} disabled={busy} onClick={()=>{setCouponError('');void applyCoupon('')}}><Tag size={15}/>{quote.coupon}<X size={14}/></button>}
      <details className="coupon-help"><summary>{t('Demo coupon offers')}</summary><ul><li>EVERYDAY · {t('50% off')}</li><li>SAVE100 · {t('₹100 off from ₹1,000')}</li><li>FIRSTBUY · {t('First guest order: 10%, up to ₹500')}</li><li>LIMITED20 · {t('20%, up to ₹500; five total uses, one per guest')}</li><li>FREESHIP · {t('Delivery is already free')}</li><li>EXPIRED10 · {t('Expired offer')}</li></ul></details>
      {quote.coupon==='FREESHIP'&&<p role="status">{t('Delivery is already free. This code has no additional charge or discount.')}</p>}
      {!busy&&!stale&&status==='ready'&&quote.valid?<a className="primary" href="/checkout">{t('Continue to checkout')}<ArrowRight size={17}/></a>:<p role="status">{t('Review your cart before continuing to checkout.')}</p>}
    </>}
    {!cart&&quote.coupon&&<div className="coupon-applied static"><Tag size={15}/>{quote.coupon}</div>}
  </aside>;
}
