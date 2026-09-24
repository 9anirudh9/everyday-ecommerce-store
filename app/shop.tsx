'use client';
/* eslint-disable @next/next/no-html-link-for-pages -- This demo intentionally uses document navigation for shop routes. */
import {FormEvent,useCallback,useEffect,useRef,useState} from 'react';
import {products,money,Product} from '@/lib/products';
import {searchProducts} from '@/lib/search';
import {formatCardExpiry} from '@/lib/payment';
import {localizeCategory,localizeProduct,translate} from '@/lib/i18n';
import SearchForm from './search-form';
import {useLanguage} from './language-provider';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Toaster} from '@/components/ui/sonner';
import {toast} from 'sonner';
import {ArrowRight,Check,CircleCheck,Clock3,CreditCard,Minus,Plus,ShoppingBag,Tag,Wallet,X} from 'lucide-react';

type Item={product:number,qty:number};
type ApiResponse={error?:string;items?:Item[];id?:string;total?:number};
type Address={name:string;email:string;street:string;city:string;pin:string};
type PaymentMethod='card'|'paypal'|'pay-later';

export default function Shop({view,id,query=''}:{view:string,id?:number,query?:string}){
  const {language,t}=useLanguage();
  const [items,setItems]=useState<Item[]>([]);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [order,setOrder]=useState('');
  const [couponInput,setCouponInput]=useState('');
  const [coupon,setCoupon]=useState('');
  const [checkoutStep,setCheckoutStep]=useState<1|2|3>(1);
  const [address,setAddress]=useState<Address|null>(null);
  const [paymentMethod,setPaymentMethod]=useState<PaymentMethod>('card');
  const [paymentSummary,setPaymentSummary]=useState('');
  const [cardExpiry,setCardExpiry]=useState('');
  const initiallyLoaded=useRef(false);

  useEffect(()=>{
    const timer=window.setTimeout(()=>{
      const saved=localStorage.getItem('everyday-coupon');
      if(saved==='EVERYDAY'){setCoupon(saved);setCouponInput(saved)}
    },0);
    return ()=>window.clearTimeout(timer);
  },[]);
  const load=useCallback(async()=>{
    setLoading(true);
    try{
      const response=await fetch('/api/shop');
      const data=await response.json() as ApiResponse;
      if(!response.ok)throw Error(translate(language,data.error||'Unable to load your cart.'));
      setItems(data.items||[]);setError('');
    }catch(cause){setError((cause as Error).message)}finally{setLoading(false)}
  },[language]);
  useEffect(()=>{
    if(initiallyLoaded.current)return;
    const timer=window.setTimeout(()=>{
      if(initiallyLoaded.current)return;
      initiallyLoaded.current=true;
      void load();
    },0);
    return ()=>window.clearTimeout(timer);
  },[load]);

  async function update(product:number,qty:number){
    setBusy(true);
    try{
      const response=await fetch('/api/shop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product,qty})});
      const data=await response.json() as ApiResponse;
      if(!response.ok)throw Error(t(data.error||'Could not update the cart.'));
      setItems(current=>[...current.filter(item=>item.product!==product),...(qty?[{product,qty}]:[])]);
      toast.success(t(qty?'Cart updated':'Item removed'));
    }catch(cause){toast.error((cause as Error).message)}finally{setBusy(false)}
  }

  function applyCoupon(event:FormEvent){
    event.preventDefault();
    const code=couponInput.trim().toUpperCase();
    if(code==='EVERYDAY'){
      setCoupon(code);setCouponInput(code);localStorage.setItem('everyday-coupon',code);
      toast.success(t('Coupon applied — 50% off'));
    }else{
      setCoupon('');localStorage.removeItem('everyday-coupon');
      toast.error(t('That coupon code is not valid.'));
    }
  }

  function removeCoupon(){setCoupon('');setCouponInput('');localStorage.removeItem('everyday-coupon');toast.success(t('Coupon removed'))}

  function saveDelivery(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    const values=Object.fromEntries(new FormData(event.currentTarget)) as Record<string,string>;
    setAddress({name:values.name,email:values.email,street:values.street,city:values.city,pin:values.pin});
    setCheckoutStep(2);
    window.scrollTo({top:0,behavior:'smooth'});
  }

  function savePayment(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    const values=Object.fromEntries(new FormData(event.currentTarget)) as Record<string,string>;
    if(paymentMethod==='card')setPaymentSummary(values.cardNumber.replace(/\D/g,'').slice(-4));
    if(paymentMethod==='paypal')setPaymentSummary(values.paypalEmail);
    if(paymentMethod==='pay-later')setPaymentSummary('');
    setCheckoutStep(3);
    window.scrollTo({top:0,behavior:'smooth'});
  }

  async function placeOrder(){
    if(!address)return setCheckoutStep(1);
    setBusy(true);
    try{
      const response=await fetch('/api/shop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'checkout',address,coupon,paymentMethod})});
      const data=await response.json() as ApiResponse;
      if(!response.ok)throw Error(t(data.error||'Could not place the order.'));
      setOrder(data.id||'');setItems([]);setCoupon('');localStorage.removeItem('everyday-coupon');
    }catch(cause){toast.error((cause as Error).message)}finally{setBusy(false)}
  }

  const results=searchProducts(query,language);
  const accessoryProducts=products.filter(product=>product.category==='Accessories');
  const subtotal=items.reduce((sum,item)=>sum+(products.find(product=>product.id===item.product)?.price||0)*item.qty,0);
  const discount=coupon==='EVERYDAY'?Math.round(subtotal*.5):0;
  const total=subtotal-discount;
  const add=(productId:number)=>update(productId,Math.min(10,(items.find(item=>item.product===productId)?.qty||0)+1));

  const cards=(list:Product[])=><div className="grid">{list.map(item=>{const product=localizeProduct(item,language);return <article className="product-card" key={product.id}>
    <a href={`/products/${product.id}`} className="photo"><img src={product.image} alt={product.name}/><span>{localizeCategory(product.category,language).toLocaleUpperCase(language)}</span></a>
    <div className="card-bottom"><div><a href={`/products/${product.id}`}><h3>{product.name}</h3></a><p>{money(product.price)}</p></div><Button aria-label={t('Add {product} to cart',{product:product.name})} disabled={busy||loading} variant="outline" size="icon" onClick={()=>add(product.id)}><Plus/></Button></div>
  </article>})}</div>;

  const summary=<aside className="summary"><h2>{t('Order summary')}</h2>
    <div><span>{t('Subtotal')}</span><b>{money(subtotal)}</b></div>
    {discount>0&&<div className="discount-line"><span>{t('EVERYDAY · 50% off')}</span><b>−{money(discount)}</b></div>}
    <div><span>{t('Delivery')}</span><b>{t('Free')}</b></div>
    <div className="total"><span>{t('Total')}</span><b>{money(total)}</b></div>
    <p>{t('All prices include taxes.')}</p>
    {view==='cart'&&<><form className="coupon-form" onSubmit={applyCoupon}><label htmlFor="coupon">{t('Coupon code')}</label><div><Input id="coupon" value={couponInput} onChange={event=>setCouponInput(event.target.value)} placeholder={t('Enter code')} maxLength={30}/><Button type="submit" variant="outline">{t('Apply')}</Button></div></form>{coupon&&<button className="coupon-applied" onClick={removeCoupon}><Tag size={15}/> {t('EVERYDAY applied')} <X size={14}/></button>}<a className="primary" href="/checkout">{t('Continue to checkout')} <ArrowRight size={17}/></a></>}
    {view==='checkout'&&discount>0&&<div className="coupon-applied static"><Tag size={15}/> {t('EVERYDAY applied')}</div>}
    <small>{t('Demo store · no real payment or delivery.')}</small>
  </aside>;

  const checkoutPanel=<div className="checkout-panel">
    <ol className="checkout-steps" aria-label={t('Checkout progress')}>
      {['Delivery','Payment','Confirm'].map((label,index)=>{const step=(index+1) as 1|2|3;return <li key={label} className={checkoutStep===step?'active':checkoutStep>step?'complete':''} aria-current={checkoutStep===step?'step':undefined}><span>{checkoutStep>step?<Check size={15}/>:step}</span>{t(label)}</li>})}
    </ol>
    {checkoutStep===1&&<form className="delivery checkout-stage" onSubmit={saveDelivery}>
      <span className="eyebrow">{t('STEP 1 OF 3')}</span><h2>{t('Delivery details')}</h2><p>{t('Where should this demo order be delivered?')}</p>
      {[['name','Full name','text'],['email','Email address','email'],['street','Street address','text'],['city','City','text'],['pin','PIN code','text']].map(([name,label,type])=><label key={name} htmlFor={name}>{t(label)}<Input id={name} name={name} type={type} required defaultValue={address?.[name as keyof Address]||''} maxLength={name==='pin'?6:200} pattern={name==='pin'?'[0-9]{6}':undefined} inputMode={name==='pin'?'numeric':undefined} placeholder={t(name==='pin'?'6-digit PIN code':label)}/></label>)}
      <Button className="primary" type="submit">{t('Continue to payment')} <ArrowRight size={18}/></Button>
    </form>}
    {checkoutStep===2&&<form className="payment-form checkout-stage" onSubmit={savePayment}>
      <span className="eyebrow">{t('STEP 2 OF 3')}</span><h2>{t('Choose how to pay')}</h2><p>{t('Select an option and enter demo payment details.')}</p>
      <fieldset className="payment-options"><legend>{t('Payment options')}</legend>
        <label className={paymentMethod==='card'?'payment-option selected':'payment-option'}><input type="radio" name="paymentChoice" value="card" checked={paymentMethod==='card'} onChange={()=>setPaymentMethod('card')}/><CreditCard/><span><b>{t('Card')}</b><small>{t('Visa, Mastercard or RuPay')}</small></span></label>
        <label className={paymentMethod==='paypal'?'payment-option selected':'payment-option'}><input type="radio" name="paymentChoice" value="paypal" checked={paymentMethod==='paypal'} onChange={()=>setPaymentMethod('paypal')}/><Wallet/><span><b>{t('PayPal')}</b><small>{t('Pay with your PayPal email')}</small></span></label>
        <label className={paymentMethod==='pay-later'?'payment-option selected':'payment-option'}><input type="radio" name="paymentChoice" value="pay-later" checked={paymentMethod==='pay-later'} onChange={()=>setPaymentMethod('pay-later')}/><Clock3/><span><b>{t('Pay later')}</b><small>{t('Pay the demo balance in 30 days')}</small></span></label>
      </fieldset>
      {paymentMethod==='card'&&<div className="payment-fields"><label htmlFor="cardName">{t('Name on card')}<Input id="cardName" name="cardName" required autoComplete="cc-name" placeholder={t('Demo cardholder')} maxLength={80}/></label><label className="wide" htmlFor="cardNumber">{t('Card number')}<Input id="cardNumber" name="cardNumber" required autoComplete="cc-number" inputMode="numeric" pattern="[0-9 ]{12,19}" placeholder="4242 4242 4242 4242" maxLength={19}/></label><label htmlFor="expiry">{t('Expiry')}<Input id="expiry" name="expiry" required autoComplete="cc-exp" inputMode="numeric" pattern="(0[1-9]|1[0-2])/[0-9]{2}" placeholder={t('MM/YY')} maxLength={5} value={cardExpiry} onChange={event=>setCardExpiry(formatCardExpiry(event.target.value))}/></label><label htmlFor="cvv">CVV<Input id="cvv" name="cvv" required autoComplete="cc-csc" inputMode="numeric" pattern="[0-9]{3,4}" placeholder="123" maxLength={4}/></label></div>}
      {paymentMethod==='paypal'&&<div className="payment-fields single"><label htmlFor="paypalEmail">{t('PayPal email')}<Input id="paypalEmail" name="paypalEmail" type="email" required defaultValue={address?.email||''} placeholder={t('you@example.com')} maxLength={200}/></label></div>}
      {paymentMethod==='pay-later'&&<div className="payment-fields single"><label htmlFor="mobile">{t('Mobile number')}<Input id="mobile" name="mobile" type="tel" required inputMode="tel" pattern="[0-9 ]{8,20}" placeholder="98765 43210" maxLength={20}/></label></div>}
      <div className="demo-note"><b>{t('Demo payment')}</b><p>{t('Use test details only. Nothing is charged, and payment details are not stored.')}</p></div>
      <div className="stage-actions"><Button type="button" variant="outline" onClick={()=>setCheckoutStep(1)}>{t('Back')}</Button><Button className="primary" type="submit">{t('Review order')} <ArrowRight size={18}/></Button></div>
    </form>}
    {checkoutStep===3&&<div className="confirmation checkout-stage">
      <span className="eyebrow">{t('STEP 3 OF 3')}</span><h2>{t('Confirm your order')}</h2><p>{t('Review the details below before placing your demo order.')}</p>
      <div className="review-card"><div><h3>{t('Delivery')}</h3><button onClick={()=>setCheckoutStep(1)}>{t('Edit')}</button></div><p><b>{address?.name}</b><br/>{address?.street}<br/>{address?.city} · {address?.pin}<br/>{address?.email}</p></div>
      <div className="review-card"><div><h3>{t('Payment')}</h3><button onClick={()=>setCheckoutStep(2)}>{t('Edit')}</button></div><p><b>{t(paymentMethod==='card'?'Card':paymentMethod==='paypal'?'PayPal':'Pay later')}</b><br/>{paymentMethod==='card'?t('Card ending {digits}',{digits:paymentSummary}):paymentMethod==='paypal'?`PayPal · ${paymentSummary}`:t('Pay later · due in 30 days')}</p></div>
      <div className="review-card items-review"><div><h3>{t('Items')}</h3><span>{t('{count} total',{count:items.reduce((sum,item)=>sum+item.qty,0)})}</span></div>{items.map(item=>{const product=products.find(candidate=>candidate.id===item.product);return product?<p key={item.product}><span>{item.qty} × {localizeProduct(product,language).name}</span><b>{money(product.price*item.qty)}</b></p>:null})}</div>
      <div className="demo-note"><b>{t('Ready to confirm?')}</b><p>{t('Your cart is only cleared after you press the button below.')}</p></div>
      <div className="stage-actions"><Button type="button" variant="outline" onClick={()=>setCheckoutStep(2)}>{t('Back')}</Button><Button className="primary confirm-order" type="button" disabled={busy} onClick={placeOrder}>{t(busy?'Placing order…':'Confirm and place order')} <CircleCheck size={18}/></Button></div>
    </div>}
  </div>;

  return <><Toaster/><main>{
    view==='home'?<><section className="hero"><div className="hero-copy"><span className="eyebrow">{t('THE EVERYDAY COLLECTION')}</span><h1>{t('Little things.')}<br/>{t('Lovely spaces.')}</h1><p>{t('Simple finds to make your corner of the world feel a little more like you.')}</p><a className="primary" href="/products">{t('Shop the collection')} <ArrowRight size={18}/></a><span className="hero-note">{t('Thoughtful details. Everyday prices.')}</span></div><a className="hero-image" href="/products/46"><img src="/products/46.webp" alt={t('Decorative plant pot from the home collection')}/><span>{t('Find your everyday favourite')} <ArrowRight size={18}/></span></a></section><section><div className="section-head"><div><span className="eyebrow">{t('A FEW GOOD FINDS')}</span><h2>{t('Made for your everyday')}</h2></div><a href="/products">{t('View all products ↗')}</a></div>{cards(products.slice(0,4))}</section></>
    :view==='search'?<section className="search-landing"><div className="page-head"><span className="eyebrow">{t('FIND YOUR EVERYDAY FAVOURITE')}</span><h1>{query?t('Results for “{query}”',{query}):t('Search the whole collection.')}</h1><p>{query?t(results.length===1?'{count} product found':'{count} products found',{count:results.length}):t('Start typing to see product suggestions instantly.')}</p><SearchForm key={query} query={query}/><div className="search-suggestions"><span>{t('Try:')}</span><a href={`/search?q=${language==='fr'?'plante':'plant'}`}>{t('Plants')}</a><a href={`/search?q=${language==='fr'?'montre':'watch'}`}>{t('Watches')}</a><a href={`/search?q=${language==='fr'?'sac':'bag'}`}>{t('Bags')}</a><a href={`/search?q=${language==='fr'?'lunettes':'sunglasses'}`}>{t('Sunglasses')}</a>{query&&<a href="/search">{t('Clear search')}</a>}</div></div>{query?(results.length?cards(results):<div className="empty" role="status"><h2>{t('No matching products.')}</h2><p>{t('Try a shorter search, such as “plant”, “watch” or “bag”.')}</p><a className="primary" href="/products">{t('Browse all products')}</a></div>):<><div className="section-head"><h2>{t('Popular searches')}</h2><a href="/products">{t('View all products ↗')}</a></div>{cards([...searchProducts('plant'),...accessoryProducts.slice(0,2)])}</>}</section>
    :view==='accessories'?<section><div className="page-head collection-head"><span className="eyebrow">{t('Accessories').toLocaleUpperCase(language)}</span><h1>{t('Finishing touches for every day.')}</h1><p>{t('{count} watches, sunglasses and bags selected for the collection.',{count:accessoryProducts.length})}</p></div>{cards(accessoryProducts)}</section>
    :view==='products'?<section><div className="page-head"><span className="eyebrow">{t('THE FULL COLLECTION')}</span><h1>{t('Small touches. Big difference.')}</h1><p>{t('{count} simple finds for your space and style.',{count:products.length})}</p></div>{cards(products)}</section>
    :view==='product'?(()=>{const found=products.find(candidate=>candidate.id===id);const product=found&&localizeProduct(found,language);return product?<><div className="breadcrumb"><a href="/products">{t('All products')}</a> / {product.name}</div><section className="detail"><div className="detail-photo"><img src={product.image} alt={product.name}/></div><div className="detail-copy"><span className="eyebrow">{localizeCategory(product.category,language).toLocaleUpperCase(language)}</span><h1>{product.name}</h1><p className="price">{money(product.price)}</p><p>{product.description}</p><Button disabled={busy||loading} onClick={()=>add(product.id)} className="primary">{t('Add to cart')} <ShoppingBag size={18}/></Button><a className="text-link" href="/cart">{t('View your cart →')}</a><div className="details-note">{t('Free delivery · Prices include taxes')}<br/>{t('Sample product for demo shopping.')}</div></div></section></>:<section><h1>{t('Product not found')}</h1><a href="/products">{t('Back to products')}</a></section>})()
    :order?<section className="auth"><div className="success-icon"><Check/></div><h1>{t('Thanks for shopping.')}</h1><p>{t('Your demo order has been saved.')}</p><p>{t('Order #{id}',{id:order.slice(0,8).toUpperCase()})}</p><p>{t('No payment was collected and no items will be shipped.')}</p><a href="/products" className="primary">{t('Continue shopping')}</a></section>
    :<section>
      <div className="page-head"><span className="eyebrow">{t('YOUR EVERYDAY FINDS')}</span><h1>{t(view==='cart'?'Your shopping cart':'Checkout')}</h1>{view==='cart'&&<p>{t('Use EVERYDAY at checkout for 50% off.')}</p>}</div>
      {loading?<p role="status">{t('Loading your cart…')}</p>:error?<div role="alert"><p>{error}</p><Button onClick={load}>{t('Try again')}</Button></div>:!items.length?<div className="empty"><ShoppingBag size={42}/><h2>{t('Your cart is waiting.')}</h2><p>{t('Find a little something for your home or wardrobe.')}</p><a href="/products" className="primary">{t('Explore products')}</a></div>:<div className="checkout-grid">
        {view==='cart'?<div>{items.map(item=>{const product=localizeProduct(products.find(candidate=>candidate.id===item.product)!,language);return <div className="cart-row" key={item.product}><a href={`/products/${product.id}`}><img src={product.image} alt={product.name}/></a><div><a href={`/products/${product.id}`}><h3>{product.name}</h3></a><p>{money(product.price)}</p><button className="remove" disabled={busy} onClick={()=>update(product.id,0)}>{t('Remove')}</button></div><div className="quantity"><Button size="icon" variant="ghost" aria-label={t('Decrease {product}',{product:product.name})} disabled={busy||item.qty<=1} onClick={()=>update(product.id,item.qty-1)}><Minus/></Button><span>{item.qty}</span><Button size="icon" variant="ghost" aria-label={t('Increase {product}',{product:product.name})} disabled={busy||item.qty>=10} onClick={()=>update(product.id,item.qty+1)}><Plus/></Button></div><b>{money(product.price*item.qty)}</b></div>})}<a className="text-link" href="/products">{t('← Continue shopping')}</a></div>:checkoutPanel}
        {summary}
      </div>}
    </section>
  }</main></>;
}
