'use client';
import {useRef,useState} from 'react';
import {ZoomIn,X} from 'lucide-react';
import ProductImage from './product-image';
import {useLanguage} from './language-provider';

export default function ProductMedia({images,name}:{images:string[];name:string}){
  const {t}=useLanguage();
  const [selected,setSelected]=useState(0);
  const dialog=useRef<HTMLDialogElement>(null);
  const zoom=useRef<HTMLButtonElement>(null);
  const sources=images.length?images:['/product-fallback.svg'];
  const source=sources[selected]??sources[0];
  return <div className="product-media">
    <div className="detail-photo"><ProductImage key={source} src={source} alt={name} data-testid="product-gallery-main"/><button ref={zoom} className="zoom-trigger" type="button" aria-label={t('Zoom image')} onClick={()=>dialog.current?.showModal()}><ZoomIn size={19}/>{t('Zoom image')}</button></div>
    <div className="gallery-thumbnails" role="group" aria-label={t('Product images')}>{sources.map((image,index)=><button type="button" key={image+index} aria-label={t('View image {number}',{number:index+1})} aria-pressed={selected===index} onClick={()=>setSelected(index)}><ProductImage key={image} src={image} alt=""/></button>)}</div>
    <p className="media-note">{t('Additional views are product illustrations.')}</p>
    <dialog className="image-dialog" ref={dialog} aria-label={t('Zoomed product image')} onClose={()=>zoom.current?.focus()} onClick={event=>{if(event.target===event.currentTarget)dialog.current?.close()}}><button type="button" aria-label={t('Close')} onClick={()=>dialog.current?.close()}><X size={22}/></button><ProductImage key={source} src={source} alt={name}/></dialog>
  </div>;
}
