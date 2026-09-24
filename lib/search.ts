import { products } from './products';
import {localizeCategory,localizeProduct,type Language} from './i18n';
function normalizeWord(word:string){
  if(word.length<=3)return word;
  if(word.endsWith('ies'))return `${word.slice(0,-3)}y`;
  if(word.endsWith('sses'))return word.slice(0,-2);
  if(word.endsWith('es'))return word.slice(0,-2);
  if(word.endsWith('s'))return word.slice(0,-1);
  return word;
}
export function searchProducts(query: string, language:Language='en') {
  const words = query.trim().toLocaleLowerCase(language).normalize('NFD').replace(/[\u0300-\u036f]/g,'').split(/\s+/).filter(Boolean).map(normalizeWord);
  return products.filter(product => {
    const localized=localizeProduct(product,language);
    const searchable = `${product.name} ${product.description} ${product.category} ${localized.name} ${localized.description} ${localizeCategory(product.category,language)}`.toLocaleLowerCase(language).normalize('NFD').replace(/[\u0300-\u036f]/g,'');
    const compact=searchable.replace(/[\s-]+/g,'');
    return words.every(word => searchable.includes(word)||compact.includes(word));
  });
}
