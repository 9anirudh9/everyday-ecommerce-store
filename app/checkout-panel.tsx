'use client';
/* eslint-disable @next/next/no-html-link-for-pages -- Native storefront navigation. */
import {useEffect,useRef,useState,type FormEvent} from 'react';
import {Check,CircleCheck,CreditCard,ShoppingBag,Wallet} from 'lucide-react';
import type {Address,CheckoutResult,PaymentMethod,Simulation} from '@/lib/commerce-types';
import {isPaymentMethod,validateAddress} from '@/lib/checkout';
import {formatCardExpiry} from '@/lib/payment';
import {products,money} from '@/lib/products';
import {localizeProduct} from '@/lib/i18n';
import {parseCartSnapshot,useCart} from './cart-provider';
import {useLanguage} from './language-provider';
import OrderSummary from './order-summary';

type Payload={action:'checkout';contractVersion:2;address:Address;paymentMethod:PaymentMethod;simulation:Simulation;idempotencyKey:string;expectedVersion:number;expectedTotal:number};
const emptyAddress:Address={name:'',email:'',phone:'',street:'',city:'',state:'',pin:''};
const draftKey='everyday-checkout-draft-v2';
const labels:Record<keyof Address,string>={name:'Full name',email:'Email address',phone:'Phone number',street:'Street address',city:'City',state:'State',pin:'PIN code'};
const fields=Object.keys(labels) as (keyof Address)[];

export default function CheckoutPanel(){
  const cart=useCart();const {language,t}=useLanguage();
  const [step,setStep]=useState<1|2|3>(1);
  const [address,setAddress]=useState<Address>(emptyAddress);
  const [fieldErrors,setFieldErrors]=useState<Record<string,string>>({});
  const [method,setMethod]=useState<PaymentMethod>('card');
  const [simulation,setSimulation]=useState<Simulation>('success');
  const [card,setCard]=useState({name:'',number:'',expiry:'',cvv:''});
  const [paypal,setPaypal]=useState(''),[payLater,setPayLater]=useState(false);
  const [paymentError,setPaymentError]=useState('');
  const [requestError,setRequestError]=useState('');
  const [pendingPayload,setPendingPayload]=useState<Payload|null>(null);
  const [uncertain,setUncertain]=useState(false),[confirming,setConfirming]=useState(false);
  const [receipt,setReceipt]=useState<CheckoutResult|null>(null);
  const [reviewVersion,setReviewVersion]=useState(-1);
  const [draftLoaded,setDraftLoaded]=useState(false),[restored,setRestored]=useState(false);
  const confirmingRef=useRef(false);
  const deliveryForm=useRef<HTMLFormElement>(null);

  useEffect(()=>{
    const timer=setTimeout(()=>{
      try{
        const raw=sessionStorage.getItem(draftKey);
        if(raw){
          const draft=JSON.parse(raw);
          if(typeof draft.savedAt==='number'&&Date.now()-draft.savedAt<30*60*1000&&draft.address&&typeof draft.address==='object'){
            const safe=Object.fromEntries(fields.map(field=>[field,typeof draft.address[field]==='string'?draft.address[field].slice(0,299):''])) as Address;
            setAddress(safe);setMethod(['card','paypal','pay-later'].includes(draft.method)?draft.method:'card');
            setSimulation(['success','decline','cancel','timeout'].includes(draft.simulation)?draft.simulation:'success');
            const candidate=draft.pendingPayload;
            if(candidate&&candidate.contractVersion===2&&typeof candidate.idempotencyKey==='string'&&Number.isInteger(candidate.expectedVersion)&&typeof candidate.expectedTotal==='number'&&validateAddress(candidate.address).address&&['card','paypal','pay-later'].includes(candidate.paymentMethod)&&['success','decline','cancel','timeout'].includes(candidate.simulation)){
              const safePayload:Payload={action:'checkout',contractVersion:2,address:validateAddress(candidate.address).address!,paymentMethod:candidate.paymentMethod,simulation:candidate.simulation,idempotencyKey:candidate.idempotencyKey,expectedVersion:candidate.expectedVersion,expectedTotal:candidate.expectedTotal};
              setPendingPayload(safePayload);setUncertain(true);setStep(3);setReviewVersion(candidate.expectedVersion);
            }else setStep(draft.step>=2?2:1);
            setRestored(true);
          }else sessionStorage.removeItem(draftKey);
        }
      }catch{try{sessionStorage.removeItem(draftKey)}catch{}}
      setDraftLoaded(true);
    },0);
    return ()=>clearTimeout(timer);
  },[]);
  useEffect(()=>{
    if(!draftLoaded||receipt)return;
    const timer=setTimeout(()=>{
      try{sessionStorage.setItem(draftKey,JSON.stringify({savedAt:Date.now(),address,step,method,simulation,pendingPayload}))}catch{}
    },0);
    return ()=>clearTimeout(timer);
  },[address,step,method,simulation,pendingPayload,draftLoaded,receipt]);

  function delivery(event:FormEvent){
    event.preventDefault();const result=validateAddress(address);setFieldErrors(result.errors);
    if(!result.address){const field=Object.keys(result.errors)[0];deliveryForm.current?.querySelector<HTMLInputElement>(`[name="${field}"]`)?.focus();return}
    setAddress(result.address);setStep(2);setRequestError('');setPendingPayload(null);
  }
  function review(event:FormEvent){
    event.preventDefault();setPaymentError('');
    if(method==='card'){
      const month=Number(card.expiry.slice(0,2)),year=2000+Number(card.expiry.slice(3));
      const now=new Date();
      if(!card.name.trim()||card.number.replace(/\D/g,'')!=='4242424242424242'||!/^\d{2}\/\d{2}$/.test(card.expiry)||month<1||month>12||year<now.getUTCFullYear()||(year===now.getUTCFullYear()&&month<now.getUTCMonth()+1)||card.cvv!=='123'){
        setPaymentError(t('Use the demo card 4242 4242 4242 4242, a future expiry, and CVV 123.'));return;
      }
    }else if(method==='paypal'&&!/^\S+@\S+\.\S+$/.test(paypal)){setPaymentError(t('Enter a valid demo PayPal email.'));return}
    else if(method==='pay-later'&&!payLater){setPaymentError(t('Confirm the demo pay-later choice.'));return}
    setReviewVersion(cart.version);setStep(3);setPendingPayload(null);setUncertain(false);setRequestError('');
  }
  async function confirm(retry=false){
    if(confirmingRef.current)return;
    const payload=retry&&pendingPayload?pendingPayload:{action:'checkout' as const,contractVersion:2 as const,address,paymentMethod:method,simulation,idempotencyKey:crypto.randomUUID(),expectedVersion:cart.version,expectedTotal:cart.quote.total};
    if(!retry&&(!cart.quote.valid||cart.stale||cart.status!=='ready'||cart.busy||reviewVersion!==cart.version))return;
    confirmingRef.current=true;setConfirming(true);setRequestError('');setPendingPayload(payload);
    try{sessionStorage.setItem(draftKey,JSON.stringify({savedAt:Date.now(),address,step:3,method,simulation,pendingPayload:payload}))}catch{}
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch('/api/shop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
      const data=await response.json() as Record<string,unknown>;
      if(!response.ok){
        if(data.cart){try{cart.acceptSnapshot(parseCartSnapshot(data.cart))}catch{}}
        const code=String(data.code??'');
        setRequestError(t(typeof data.error==='string'?data.error:'Could not place the demo order. Retry safely with the same confirmation.'));
        if(response.status>=500){setUncertain(true)}
        else if(response.status===408){setUncertain(false)}
        else{
          setUncertain(false);setPendingPayload(null);
          if(data.fields&&typeof data.fields==='object'){const errors=data.fields as Record<string,unknown>;setFieldErrors(Object.fromEntries(fields.filter(field=>typeof errors[field]==='string').map(field=>[field,String(errors[field])])));setStep(1)}
          if(['CART_CHANGED','TOTAL_CHANGED'].includes(code))setReviewVersion(-1);
        }
        return;
      }
      if(typeof data.id!=='string'||!data.id||data.status!=='demo-confirmed'||!isPaymentMethod(data.paymentMethod)||typeof data.replayed!=='boolean'||(data.coupon!==null&&typeof data.coupon!=='string')||![data.subtotal,data.discount,data.total].every(number=>typeof number==='number'&&Number.isFinite(number)&&number>=0)||Number(data.discount)>Number(data.subtotal)||data.total!==Number(data.subtotal)-Number(data.discount))throw Error('Invalid order response');
      const next=parseCartSnapshot(data.cart);
      setReceipt(data as unknown as CheckoutResult);setPendingPayload(null);setUncertain(false);setCard({name:'',number:'',expiry:'',cvv:''});setPaypal('');setPayLater(false);
      try{sessionStorage.removeItem(draftKey)}catch{}
      cart.acceptSnapshot(next);
      cart.notifyChanged();
    }catch{
      setUncertain(true);setRequestError(t('The confirmation response was lost. Retry the same confirmation to recover its result.'));
    }finally{clearTimeout(timer);confirmingRef.current=false;setConfirming(false)}
  }
  if(receipt)return <section className="auth"><div className="success-icon"><Check/></div><h1>{t('Thanks for shopping.')}</h1><p>{t('Your demo order has been saved.')}</p><p>{t('Order #{id}',{id:receipt.id.slice(0,8).toUpperCase()})}</p><div className="receipt-totals"><p>{t('Subtotal')}: {money(receipt.subtotal)}</p><p>{t('Discount')}: {money(receipt.discount)}</p><p><b>{t('Total')}: {money(receipt.total)}</b></p></div><p>{t('No payment was collected and no items will be shipped.')}</p><a href="/products" className="primary">{t('Continue shopping')}</a></section>;
  if(!draftLoaded||(!cart.hasLoaded&&cart.status==='loading'))return <section className="catalog-state" role="status"><p>{t('Loading your cart…')}</p></section>;
  if(!cart.hasLoaded)return <section className="catalog-state" role="alert"><h1>{t('Checkout')}</h1><p>{cart.error}</p><button type="button" className="primary" onClick={()=>void cart.refresh()}>{t('Try again')}</button></section>;
  const empty=!cart.items.length;
  const quoteChanged=reviewVersion!==cart.version;
  const localSubtotal=cart.items.reduce((sum,item)=>sum+(products.find(product=>product.id===item.product)?.price??0)*item.qty,0);
  return <section><div className="page-head"><span className="eyebrow">{t('YOUR EVERYDAY FINDS')}</span><h1>{t('Checkout')}</h1><p>{t('Demo checkout · no real payment or delivery')}</p></div>
    {restored&&!uncertain&&<p role="status" className="recovery-banner">{t('Your delivery details were restored. Re-enter demo payment details.')}</p>}
    {cart.status==='error'&&<div className="recovery-banner" role="alert"><p>{cart.error}</p><button type="button" onClick={()=>void cart.refresh()}>{t('Try again')}</button></div>}
    {(cart.stale||cart.status==='loading')&&cart.hasLoaded&&<p role="status" className="recovery-banner">{t('Refreshing your cart. Checkout is paused until it is up to date.')}</p>}
    {requestError&&<div className="recovery-banner" role="alert"><p>{requestError}</p>{pendingPayload&&<button type="button" disabled={confirming} onClick={()=>void confirm(true)}>{t('Retry confirmation')}</button>}{!uncertain&&step===3&&<button type="button" disabled={confirming} onClick={()=>{setStep(2);setPendingPayload(null);setRequestError('')}}>{t('Change payment outcome')}</button>}</div>}
    {uncertain&&<div className="recovery-banner" role="status"><p>{t('Resolve the previous confirmation before starting another order.')}</p>{!requestError&&<button type="button" disabled={confirming} onClick={()=>void confirm(true)}>{t('Retry confirmation')}</button>}</div>}
    {empty&&!uncertain?<div className="empty"><ShoppingBag size={42}/><h2>{t('Your cart is empty or your guest session changed.')}</h2><p>{t('Review your cart and add items before checkout.')}</p><a className="primary" href="/products">{t('Explore products')}</a></div>:<div className="checkout-grid"><div className="checkout-panel">
      <ol className="checkout-steps" aria-label={t('Checkout progress')}>{(['Delivery','Payment','Review'] as const).map((label,index)=><li key={label} className={step===index+1?'active':step>index+1?'complete':''} aria-current={step===index+1?'step':undefined}><span>{index+1}</span>{t(label)}</li>)}</ol>
      {step===1&&<form ref={deliveryForm} className="checkout-stage delivery" onSubmit={delivery} noValidate><h2>{t('Delivery details')}</h2>{fields.map(field=><label key={field} htmlFor={`delivery-${field}`}>{t(labels[field])}<input id={`delivery-${field}`} name={field} type={field==='email'?'email':field==='phone'?'tel':'text'} value={address[field]} maxLength={299} aria-invalid={Boolean(fieldErrors[field])} aria-describedby={fieldErrors[field]?`error-${field}`:undefined} onChange={event=>setAddress(current=>({...current,[field]:event.target.value}))}/>{fieldErrors[field]&&<span className="field-error" id={`error-${field}`}>{t(fieldErrors[field])}</span>}</label>)}<label className="shipping-choice"><input type="radio" name="shipping" checked readOnly/>{t('Standard delivery · free')}</label><button className="primary" type="submit">{t('Continue to payment')}</button></form>}
      {step===2&&<form className="checkout-stage" onSubmit={review} noValidate><h2>{t('Choose how to pay')}</h2><p>{t('Use demonstration details only. Payment fields stay in this tab’s memory.')}</p><fieldset className="payment-options"><legend>{t('Payment method')}</legend>{(['card','paypal','pay-later'] as PaymentMethod[]).map(option=><label className={`payment-option ${method===option?'selected':''}`} key={option}><input type="radio" aria-label={t(option==='card'?'Card':option==='paypal'?'PayPal':'Pay later')} name="paymentMethod" value={option} checked={method===option} onChange={()=>{setMethod(option);setPaymentError('')}}/>{option==='card'?<CreditCard size={22}/>:<Wallet size={22}/>}<span><b>{t(option==='card'?'Card':option==='paypal'?'PayPal':'Pay later')}</b><small>{t('Demonstration only')}</small></span></label>)}</fieldset>
        {method==='card'?<div className="payment-fields"><label className="wide" htmlFor="card-name">{t('Name on card')}<input id="card-name" autoComplete="off" value={card.name} onChange={event=>setCard(current=>({...current,name:event.target.value}))}/></label><label className="wide" htmlFor="card-number">{t('Card number')}<input id="card-number" autoComplete="off" inputMode="numeric" value={card.number} maxLength={19} placeholder="4242 4242 4242 4242" onChange={event=>setCard(current=>({...current,number:event.target.value}))}/></label><label htmlFor="expiry">{t('Expiry')}<input id="expiry" autoComplete="off" inputMode="numeric" value={card.expiry} onChange={event=>setCard(current=>({...current,expiry:formatCardExpiry(event.target.value)}))} maxLength={5}/></label><label htmlFor="cvv">{t('CVV')}<input id="cvv" autoComplete="off" type="password" inputMode="numeric" value={card.cvv} onChange={event=>setCard(current=>({...current,cvv:event.target.value}))} maxLength={3}/></label></div>:method==='paypal'?<div className="payment-fields single"><label htmlFor="paypal-email">{t('PayPal email')}<input id="paypal-email" autoComplete="off" type="email" value={paypal} onChange={event=>setPaypal(event.target.value)}/></label></div>:<label className="pay-later-confirm"><input type="checkbox" checked={payLater} onChange={event=>setPayLater(event.target.checked)}/>{t('I understand this is a demo pay-later order.')}</label>}
        <div className="outcome-field"><label htmlFor="payment-outcome">{t('Payment outcome')}</label><select id="payment-outcome" value={simulation} onChange={event=>setSimulation(event.target.value as Simulation)}><option value="success">{t('Success')}</option><option value="decline">{t('Decline')}</option><option value="cancel">{t('Cancel')}</option><option value="timeout">{t('Timeout')}</option></select></div>
        {paymentError&&<p className="product-error" role="alert">{paymentError}</p>}<div className="stage-actions"><button type="button" onClick={()=>setStep(1)}>{t('Back')}</button><button className="primary" type="submit">{t('Review order')}</button></div>
      </form>}
      {step===3&&<div className="checkout-stage confirmation"><h2>{t('Confirm your order')}</h2><div className="review-card"><div><h3>{t('Delivery')}</h3><button type="button" disabled={uncertain||confirming} onClick={()=>setStep(1)}>{t('Edit')}</button></div><p>{address.name}<br/>{address.street}<br/>{address.city}, {address.state} {address.pin}<br/>{address.email}<br/>{address.phone}</p></div><div className="review-card"><div><h3>{t('Payment')}</h3><button type="button" disabled={uncertain||confirming} onClick={()=>setStep(2)}>{t('Edit')}</button></div><p>{t(method==='card'?'Card':method==='paypal'?'PayPal':'Pay later')} · {t('Demonstration only')}<br/>{t('Payment outcome')}: {t(simulation==='success'?'Success':simulation==='decline'?'Decline':simulation==='cancel'?'Cancel':'Timeout')}</p></div><div className="review-card items-review"><h3>{t('Items')}</h3>{cart.items.map(item=>{const product=products.find(product=>product.id===item.product);return <p key={item.product}><span>{item.qty} × {product?localizeProduct(product,language).name:t('Unavailable product')}</span><b>{product?money(product.price*item.qty):'—'}</b></p>})}</div>
        {quoteChanged&&!uncertain&&<div className="recovery-banner" role="alert"><p>{t('Your cart or offers changed. Review the updated total before confirming.')}</p><button type="button" disabled={!cart.quote.valid||cart.status!=='ready'} onClick={()=>setReviewVersion(cart.version)}>{t('Accept updated summary')}</button></div>}
        {(!cart.quote.valid||localSubtotal!==cart.quote.subtotal)&&!uncertain&&<div className="recovery-banner" role="alert"><p>{t('Review your cart before continuing to checkout.')}</p><a href="/cart">{t('View your cart →')}</a></div>}
        <div className="demo-note"><b>{t('Ready to confirm?')}</b><p>{t('Your cart is only cleared after you press the button below.')}</p></div><div className="stage-actions"><button type="button" disabled={confirming||uncertain} onClick={()=>setStep(2)}>{t('Back')}</button><button className="primary confirm-order" type="button" disabled={confirming||uncertain||cart.busy||cart.stale||cart.status!=='ready'||!cart.quote.valid||quoteChanged||localSubtotal!==cart.quote.subtotal} onClick={()=>void confirm()}>{t(confirming?'Placing order…':'Confirm and place order')}<CircleCheck size={18}/></button></div>
      </div>}
    </div><OrderSummary/></div>}
  </section>;
}
