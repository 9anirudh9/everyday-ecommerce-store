'use client';
import {createContext,useCallback,useContext,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {products,type Product} from '@/lib/products';
import type {CartItem,CartSnapshot,Quote} from '@/lib/commerce-types';
import {translate} from '@/lib/i18n';
import {useLanguage} from './language-provider';
export type {CartItem} from '@/lib/commerce-types';

type CartStatus='loading'|'ready'|'error';
export type MutationResult={ok:boolean;error?:string;code?:string;data?:Record<string,unknown>};
type Operation={kind:'quantity';product:number;qty:number;expectedVersion?:number}|{kind:'add';product:Product;amount:number}|{kind:'clear'}|{kind:'coupon';code:string};
type Prepared={url:string;body:Record<string,unknown>};
type MutationError={message:string;code?:string;canRetry:boolean};
const initialQuote:Quote={subtotal:0,discount:0,total:0,delivery:0,coupon:null,subtotalPaise:0,discountPaise:0,totalPaise:0,currency:'INR',valid:false};
const initial:CartSnapshot={items:[],version:0,quote:initialQuote,issues:[],checkedAt:''};
type Context={items:CartItem[];version:number;quote:Quote;issues:CartSnapshot['issues'];status:CartStatus;hasLoaded:boolean;error:string;busy:boolean;stale:boolean;mutationError:MutationError|null;refresh:()=>Promise<void>;addItem:(product:Product,amount:number)=>Promise<MutationResult>;changeQuantity:(product:number,qty:number,expectedVersion?:number)=>Promise<MutationResult>;clearCart:()=>Promise<MutationResult>;applyCoupon:(code:string)=>Promise<MutationResult>;retryLastMutation:()=>Promise<MutationResult>;clearMutationError:()=>void;acceptSnapshot:(snapshot:CartSnapshot)=>void;notifyChanged:()=>void;setReadyItems:(items:CartItem[]|((current:CartItem[])=>CartItem[]))=>void};
const CartContext=createContext<Context|null>(null);
export function useCart(){const value=useContext(CartContext);if(!value)throw Error('useCart must be used inside CartProvider');return value}

export function parseCartSnapshot(data:unknown):CartSnapshot{
  if(!data||typeof data!=='object')throw Error('Unable to load your cart.');
  const value=data as CartSnapshot;
  if(!Array.isArray(value.items)||value.items.some(item=>!item||!Number.isInteger(item.product)||item.product<1||!Number.isInteger(item.qty)||item.qty<1||item.qty>10))throw Error('Unable to load your cart.');
  if(value.quote===undefined){
    const subtotal=value.items.reduce((sum,item)=>sum+(products.find(product=>product.id===item.product)?.price??0)*item.qty,0);
    return {...initial,items:value.items,quote:{...initialQuote,subtotal,total:subtotal,subtotalPaise:subtotal*100,totalPaise:subtotal*100}};
  }
  const quote=value.quote;
  if(!Number.isInteger(value.version)||value.version<0||!quote||![quote.subtotal,quote.discount,quote.total,quote.subtotalPaise,quote.discountPaise,quote.totalPaise].every(number=>typeof number==='number'&&Number.isFinite(number)&&number>=0)||typeof quote.valid!=='boolean'||quote.currency!=='INR'||quote.delivery!==0||(quote.coupon!==null&&typeof quote.coupon!=='string')||quote.discount>quote.subtotal||quote.total!==quote.subtotal-quote.discount||!Array.isArray(value.issues)||value.issues.some(issue=>!issue||typeof issue.code!=='string'||typeof issue.message!=='string')||(quote.couponError&&typeof quote.couponError.message!=='string'))throw Error('Unable to load your cart.');
  return value;
}

export default function CartProvider({children}:{children:ReactNode}){
  const {language}=useLanguage();
  const [snapshot,setSnapshot]=useState<CartSnapshot>(initial);
  const current=useRef(initial);
  const [status,setStatus]=useState<CartStatus>('loading');
  const [hasLoaded,setHasLoaded]=useState(false);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [stale,setStale]=useState(false);
  const [mutationError,setMutationError]=useState<MutationError|null>(null);
  const sequence=useRef(0),pending=useRef(0),needsRefresh=useRef(false);
  const queue=useRef<Promise<unknown>>(Promise.resolve());
  const inFlight=useRef(new Map<string,Promise<MutationResult>>());
  const lastFailed=useRef<Prepared|null>(null);
  const channel=useRef<BroadcastChannel|null>(null);
  const legacyMigration=useRef(false);
  const invalidate=useCallback(()=>{sequence.current++},[]);

  const acceptSnapshot=useCallback((next:CartSnapshot)=>{
    sequence.current++;current.current=next;setSnapshot(next);setHasLoaded(true);setError('');setStatus('ready');setStale(false);
  },[]);
  const announce=useCallback(()=>{
    channel.current?.postMessage({type:'changed'});
    try{localStorage.setItem('everyday-cart-changed',crypto.randomUUID())}catch{}
  },[]);
  const refresh=useCallback(async()=>{
    if(pending.current){needsRefresh.current=true;return}
    const id=++sequence.current;
    setStatus('loading');setError('');
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),12000);
    try{
      const response=await fetch('/api/shop',{cache:'no-store',signal:controller.signal});
      const data=await response.json();
      if(!response.ok)throw Error('Unable to load your cart.');
      const next=parseCartSnapshot(data);
      if(id!==sequence.current)return;
      acceptSnapshot(next);
    }catch{
      if(id!==sequence.current)return;
      setError(translate(language,'Unable to load your cart. Please try again.'));setStatus('error');setStale(true);
    }finally{clearTimeout(timer)}
  },[acceptSnapshot,language]);

  const perform=useCallback(async(prepared:Prepared):Promise<MutationResult>=>{
    sequence.current++;
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),12000);
    try{
      const response=await fetch(prepared.url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(prepared.body),signal:controller.signal});
      const data=await response.json() as Record<string,unknown>;
      if(!response.ok){
        const code=typeof data.code==='string'?data.code:undefined;
        if(data.cart){try{acceptSnapshot(parseCartSnapshot(data.cart))}catch{}}
        else if(response.status===409)needsRefresh.current=true;
        const text=code==='CART_CONFLICT'||code==='VERSION_CONFLICT'||code==='CART_CHANGED'
          ?'Your cart changed in another tab. Review the refreshed cart and try again.'
          :code==='STOCK_CHANGED'||code==='OUT_OF_STOCK'?'Availability changed. Review the stock before adding again.':code==='PRICE_CHANGED'?'The price changed. Review the current price before adding again.':typeof data.error==='string'?data.error:'Could not update the cart. Please try again.';
        const message=translate(language,text);
        const canRetry=response.status>=500||response.status===408;
        lastFailed.current=canRetry?prepared:null;setMutationError({message,code,canRetry});
        return {ok:false,error:message,code,data};
      }
      const value=data.cart??(Array.isArray(data.items)?data:null);
      if(value)acceptSnapshot(parseCartSnapshot(value));else needsRefresh.current=true;
      lastFailed.current=null;setMutationError(null);announce();
      return {ok:true,data};
    }catch{
      const message=translate(language,'The update could not be confirmed. Retry safely to check its result.');
      lastFailed.current=prepared;setMutationError({message,canRetry:true});return {ok:false,error:message};
    }finally{clearTimeout(timer)}
  },[acceptSnapshot,announce,language]);

  const enqueue=useCallback((operation:Operation|Prepared):Promise<MutationResult>=>{
    const signature=JSON.stringify(operation);
    const duplicate=inFlight.current.get(signature);if(duplicate)return duplicate;
    pending.current++;setBusy(true);
    const result=queue.current.catch(()=>{}).then(async()=>{
      let prepared:Prepared;
      if('url' in operation)prepared=operation;
      else{
        const state=current.current;
        const body:Record<string,unknown>={expectedVersion:state.version,idempotencyKey:crypto.randomUUID()};
        if(operation.kind==='coupon'){body.code=operation.code;body.apply=true;prepared={url:'/api/coupons/validate',body}}
        else if(operation.kind==='clear'){body.action='clear';prepared={url:'/api/shop',body}}
        else{
          const product=operation.kind==='add'?operation.product:products.find(product=>product.id===operation.product);
          const productId=operation.kind==='add'?operation.product.id:operation.product;
          const qty=operation.kind==='add'?(state.items.find(item=>item.product===productId)?.qty??0)+operation.amount:operation.qty;
          if(!Number.isInteger(qty)||qty<0||qty>10||(qty>0&&product&&qty>product.stock)){
            const message=translate(language,'Choose a quantity within the available stock.');setMutationError({message,canRetry:false});return {ok:false,error:message};
          }
          body.product=productId;body.qty=qty;if(operation.kind==='quantity'&&operation.expectedVersion!==undefined)body.expectedVersion=operation.expectedVersion;if(qty>0&&product)body.expectedPrice=product.price;
          prepared={url:'/api/shop',body};
        }
      }
      return perform(prepared);
    }).finally(()=>{
      inFlight.current.delete(signature);pending.current--;
      if(pending.current===0){setBusy(false);if(needsRefresh.current){needsRefresh.current=false;void refresh()}}
    });
    queue.current=result;inFlight.current.set(signature,result);return result;
  },[language,perform,refresh]);

  const setReadyItems=useCallback((next:CartItem[]|((current:CartItem[])=>CartItem[]))=>{
    const items=typeof next==='function'?next(current.current.items):next;
    acceptSnapshot({...current.current,items,quote:{...current.current.quote,valid:false}});
  },[acceptSnapshot]);
  useEffect(()=>{
    const timer=setTimeout(()=>void refresh(),0);
    const changed=()=>{setStale(true);void refresh()};
    const storage=(event:StorageEvent)=>{if(event.key==='everyday-cart-changed')changed()};
    if(typeof BroadcastChannel!=='undefined'){channel.current=new BroadcastChannel('everyday-cart');channel.current.onmessage=changed}
    window.addEventListener('focus',changed);window.addEventListener('storage',storage);
    return ()=>{invalidate();clearTimeout(timer);channel.current?.close();channel.current=null;window.removeEventListener('focus',changed);window.removeEventListener('storage',storage)};
  },[refresh,invalidate]);
  useEffect(()=>{
    if(!hasLoaded||status!=='ready'||legacyMigration.current)return;
    legacyMigration.current=true;
    let saved:string|null=null;try{saved=localStorage.getItem('everyday-coupon')}catch{}
    if(saved==='EVERYDAY'&&!snapshot.quote.coupon){const timer=setTimeout(()=>{void enqueue({kind:'coupon',code:'EVERYDAY'}).then(result=>{if(result.ok)localStorage.removeItem('everyday-coupon')})},0);return ()=>clearTimeout(timer)}
  },[hasLoaded,status,snapshot.quote.coupon,enqueue]);
  const value=useMemo<Context>(()=>({...snapshot,status,hasLoaded,error,busy,stale,mutationError,refresh,acceptSnapshot,notifyChanged:announce,setReadyItems,
    addItem:(product,amount)=>enqueue({kind:'add',product,amount}),changeQuantity:(product,qty,expectedVersion)=>enqueue({kind:'quantity',product,qty,expectedVersion}),clearCart:()=>enqueue({kind:'clear'}),applyCoupon:code=>enqueue({kind:'coupon',code}),retryLastMutation:()=>lastFailed.current?enqueue(lastFailed.current):Promise.resolve({ok:false}),clearMutationError:()=>setMutationError(null)}),[snapshot,status,hasLoaded,error,busy,stale,mutationError,refresh,acceptSnapshot,setReadyItems,enqueue,announce]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
