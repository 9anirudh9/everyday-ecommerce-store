import type {Metadata} from 'next';
import Link from 'next/link';
import {ShoppingBag} from 'lucide-react';
import './globals.css';
import SearchForm from './search-form';
export const metadata:Metadata={title:'Everyday — Little things. Lovely spaces.',description:'Shop simple home accessories at Everyday. A demo ecommerce store.'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body><div className="announcement">A little something for your everyday. <span>Free delivery on every order.</span></div><header><Link href="/" className="logo">everyday<span>®</span></Link><nav><Link href="/">Home</Link><Link href="/products">Shop</Link><Link href="/accessories">Accessories</Link></nav><SearchForm compact/><div className="header-right"><span className="guest-label">No sign-in needed</span><Link href="/cart" className="bag" aria-label="Shopping cart"><ShoppingBag size={20}/><span>Cart</span></Link></div></header>{children}<footer><Link href="/" className="logo">everyday<span>®</span></Link><p>Good things for your everyday.</p><div><a href="https://dummyjson.com" target="_blank" rel="noreferrer">Product images: DummyJSON</a><span>Demo store · No real transactions</span></div></footer></body></html>}
