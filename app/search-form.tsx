'use client';
import Link from 'next/link';
import {useMemo,useRef,useState} from 'react';
import {Search} from 'lucide-react';
import {Input} from '@/components/ui/input';
import {Button} from '@/components/ui/button';
import {searchProducts} from '@/lib/search';
import {money} from '@/lib/products';

export default function SearchForm({query='',compact=false}:{query?:string;compact?:boolean}) {
  const [value,setValue]=useState(query),[open,setOpen]=useState(false);
  const blurTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const suggestions=useMemo(()=>value.trim()?searchProducts(value).slice(0,5):[],[value]);
  return <form action="/search" method="get" role="search" aria-label={compact?'Site product search':'Search collection'} className={compact?'search-form compact-search':'search-form'} onSubmit={()=>setOpen(false)}>
    <div className="search-field">
      <Input type="search" name="q" aria-label="Search products" aria-autocomplete="list" aria-expanded={open&&suggestions.length>0} aria-controls="search-suggestion-list" value={value} onChange={e=>{setValue(e.target.value);setOpen(true)}} onFocus={()=>{if(blurTimer.current)clearTimeout(blurTimer.current);setOpen(true)}} onBlur={()=>{blurTimer.current=setTimeout(()=>setOpen(false),120)}} onKeyDown={e=>{if(e.key==='Escape')setOpen(false)}} placeholder="Search plants, watches, bags…" maxLength={120} autoComplete="off"/>
      {open&&value.trim()&&<div id="search-suggestion-list" className="suggestion-panel" role="listbox">
        {suggestions.length?suggestions.map(product=><Link role="option" aria-selected="false" key={product.id} href={`/products/${product.id}`}><img src={product.image} alt=""/><span><b>{product.name}</b><small>{product.category} · {money(product.price)}</small></span></Link>):<Link href={`/search?q=${encodeURIComponent(value.trim())}`} className="no-suggestion"><span><b>No quick matches</b><small>View full search results</small></span></Link>}
        {suggestions.length>0&&<Link href={`/search?q=${encodeURIComponent(value.trim())}`} className="all-results"><span>See all results for “{value.trim()}”</span></Link>}
      </div>}
    </div>
    <Button type="submit" aria-label="Search products"><Search size={18}/>{!compact&&<span>Search</span>}</Button>
  </form>;
}
