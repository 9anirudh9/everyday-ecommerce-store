import type {Metadata} from 'next';
import Shop from '../shop';
export const metadata:Metadata={title:'Search plants & home accessories | Everyday'};
export default async function Page({searchParams}:{searchParams:Promise<{q?:string|string[]}>}) {
  const params=await searchParams;
  const query=(typeof params.q==='string'?params.q:'').trim().slice(0,120);
  return <Shop view="search" query={query}/>;
}
