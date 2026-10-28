'use client';
/* eslint-disable @next/next/no-location-assign-relative-destination -- Keyboard suggestions use the verified native navigation path. */
import {useEffect,useId,useMemo,useRef,useState} from 'react';
import {Search} from 'lucide-react';
import {Input} from '@/components/ui/input';
import {Button} from '@/components/ui/button';
import {searchProducts} from '@/lib/search';
import {money} from '@/lib/products';
import {localizeCategory,localizeProduct} from '@/lib/i18n';
import {useLanguage} from './language-provider';
import ProductImage from './product-image';

export default function SearchForm({query='',compact=false}:{query?:string;compact?:boolean}){
  const {language,t}=useLanguage();
  const [value,setValue]=useState(query),[open,setOpen]=useState(false),[active,setActive]=useState(-1);
  const [debounced,setDebounced]=useState(query.trim());
  const listId=useId();
  const blurTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  useEffect(()=>{const timer=setTimeout(()=>setDebounced(value.trim()),180);return ()=>clearTimeout(timer)},[value]);
  useEffect(()=>()=>{if(blurTimer.current)clearTimeout(blurTimer.current)},[]);
  const suggestions=useMemo(()=>debounced?searchProducts(debounced,language).slice(0,5):[],[debounced,language]);
  const show=open&&Boolean(value.trim())&&debounced===value.trim();
  return <form action="/search" method="get" role="search" aria-label={t(compact?'Site product search':'Search collection')} className={compact?'search-form compact-search':'search-form'} onSubmit={()=>setOpen(false)}>
    <div className="search-field">
      <Input role="combobox" type="search" name="q" aria-label={t('Search products')} aria-autocomplete="list" aria-haspopup="listbox" aria-expanded={show&&suggestions.length>0} aria-controls={listId} aria-activedescendant={show&&active>=0&&active<suggestions.length?`${listId}-${active}`:undefined} value={value}
        onChange={event=>{setValue(event.target.value);setOpen(true);setActive(-1)}}
        onFocus={()=>{if(blurTimer.current)clearTimeout(blurTimer.current);setOpen(true)}}
        onBlur={()=>{blurTimer.current=setTimeout(()=>{setOpen(false);setActive(-1)},120)}}
        onKeyDown={event=>{
          if(event.key==='Escape'){event.preventDefault();setOpen(false);setActive(-1)}
          if((event.key==='ArrowDown'||event.key==='ArrowUp')&&show&&suggestions.length){event.preventDefault();setActive(current=>event.key==='ArrowDown'?(current+1)%suggestions.length:(current<=0?suggestions.length-1:current-1))}
          if(event.key==='Enter'&&show&&active>=0&&suggestions[active]){event.preventDefault();window.location.assign(`/products/${suggestions[active].id}`)}
        }} placeholder={t('Search plants, watches, bags…')} maxLength={120} autoComplete="off"/>
      {show&&<div className="suggestion-panel">
        <div id={listId} className="suggestion-list" role="listbox" aria-label={t('Product suggestions')}>{suggestions.map((product,index)=><a role="option" aria-selected={active===index} id={`${listId}-${index}`} key={product.id} href={`/products/${product.id}`} onMouseEnter={()=>setActive(index)}><ProductImage key={product.image} src={product.image} alt=""/><span><b>{localizeProduct(product,language).name}</b><small>{localizeCategory(product.category,language)} · {money(product.price)}</small></span></a>)}</div>
        {!suggestions.length&&<a href={`/search?q=${encodeURIComponent(value.trim())}`} className="no-suggestion"><span><b>{t('No quick matches')}</b><small>{t('View full search results')}</small></span></a>}
        {suggestions.length>0&&<a href={`/search?q=${encodeURIComponent(value.trim())}`} className="all-results"><span>{t('See all results for “{query}”',{query:value.trim()})}</span></a>}
      </div>}
    </div>
    <Button type="submit" aria-label={t('Search products')}><Search size={18}/>{!compact&&<span>{t('Search')}</span>}</Button>
  </form>;
}
