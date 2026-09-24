import type {Metadata} from 'next';
import {cookies} from 'next/headers';
import {languageCookie,translate} from '@/lib/i18n';
import Shop from '../shop';
export async function generateMetadata():Promise<Metadata>{
  const language=(await cookies()).get(languageCookie)?.value==='fr'?'fr':'en';
  return {title:translate(language,'Search plants & home accessories | Everyday')};
}
export default async function Page({searchParams}:{searchParams:Promise<{q?:string|string[]}>}) {
  const params=await searchParams;
  const query=(typeof params.q==='string'?params.q:'').trim().slice(0,120);
  return <Shop view="search" query={query}/>;
}
