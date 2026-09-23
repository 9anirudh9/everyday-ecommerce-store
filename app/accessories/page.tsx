import type {Metadata} from 'next';
import Shop from '../shop';
export const metadata:Metadata={title:'Accessories | Everyday',description:'Browse watches, sunglasses and bags from the Everyday accessories collection.'};
export default function Page(){return <Shop view="accessories"/>}
