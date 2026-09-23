import { products } from './products';
function normalizeWord(word:string){
  if(word.length<=3)return word;
  if(word.endsWith('ies'))return `${word.slice(0,-3)}y`;
  if(word.endsWith('sses'))return word.slice(0,-2);
  if(word.endsWith('es'))return word.slice(0,-2);
  if(word.endsWith('s'))return word.slice(0,-1);
  return word;
}
export function searchProducts(query: string) {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean).map(normalizeWord);
  return products.filter(product => {
    const searchable = `${product.name} ${product.description} ${product.category}`.toLowerCase();
    const compact=searchable.replace(/[\s-]+/g,'');
    return words.every(word => searchable.includes(word)||compact.includes(word));
  });
}
