'use client';
import {useState} from 'react';
import {toast} from 'sonner';
import type {Product} from '@/lib/products';
import {useCart} from './cart-provider';
import {useLanguage} from './language-provider';
export type CartConflict={currentPrice?:number;availableStock?:number;maxQuantity?:number};

export function useProductCart(){
  const {items,status,busy,addItem}=useCart();
  const {t}=useLanguage();
  const [error,setError]=useState('');
  async function addProduct(product:Product,amount=1):Promise<{ok:boolean;conflict?:CartConflict}>{
    if(status!=='ready'){setError(t('Wait for your cart to finish loading.'));return {ok:false}}
    if(!Number.isInteger(amount)||amount<1){setError(t('Choose a quantity within the available stock.'));return {ok:false}}
    setError('');const result=await addItem(product,amount);
    if(result.ok){toast.success(t('Cart updated'));return {ok:true}}
    let message=result.error??t('Could not update the cart. Please try again.');
    if(result.data?.currentPrice!==undefined&&result.data.currentPrice!==product.price)message=t('The price changed. Review the current price before adding again.');
    setError(message);toast.error(message);
    return {ok:false,conflict:result.data as CartConflict|undefined};
  }
  return {items,status,busy,error,addProduct};
}
