'use client';
import {useState, type ImgHTMLAttributes} from 'react';

export default function ProductImage({src,alt,...props}:ImgHTMLAttributes<HTMLImageElement>){
  const [failed,setFailed]=useState(false);
  // A local placeholder also protects the page when a product asset disappears.
  return <img {...props} src={failed?'/product-fallback.svg':src} alt={alt} onError={()=>setFailed(true)} data-image-fallback={failed||undefined}/>;
}
