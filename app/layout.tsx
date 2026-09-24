import type {Metadata} from 'next';
import {cookies} from 'next/headers';
import {languageCookie,translate,type Language} from '@/lib/i18n';
import LanguageProvider from './language-provider';
import SiteFrame from './site-frame';
import './globals.css';
export async function generateMetadata():Promise<Metadata>{
  const saved=(await cookies()).get(languageCookie)?.value;
  const language:Language=saved==='fr'?'fr':'en';
  return {
    title:translate(language,'Everyday — Little things. Lovely spaces.'),
    description:translate(language,'Shop simple home accessories at Everyday. A demo ecommerce store.'),
  };
}
export default async function Layout({children}:{children:React.ReactNode}){
  const saved=(await cookies()).get(languageCookie)?.value;
  const language:Language|null=saved==='en'||saved==='fr'?saved:null;
  return <html lang={language??'en'}><body><LanguageProvider initialLanguage={language}><SiteFrame>{children}</SiteFrame></LanguageProvider></body></html>;
}
