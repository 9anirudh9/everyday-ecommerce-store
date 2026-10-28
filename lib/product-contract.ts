import type {Product} from './products';

export function isProduct(value:unknown):value is Product{
  if(!value||typeof value!=='object')return false;
  const product=value as Product;
  return Number.isInteger(product.id)&&product.id>0&&
    typeof product.name==='string'&&product.name.length>0&&typeof product.description==='string'&&
    Number.isFinite(product.price)&&product.price>=0&&
    (product.category==='Home'||product.category==='Accessories')&&
    typeof product.image==='string'&&product.image.length>0&&
    Array.isArray(product.images)&&product.images.length>0&&product.images.every(image=>typeof image==='string'&&image.length>0)&&
    Number.isInteger(product.stock)&&product.stock>=0&&
    Number.isFinite(product.rating)&&product.rating>=0&&product.rating<=5&&
    [product.nameFr,product.descriptionFr,product.variantGroup,product.variantLabel].every(value=>value===undefined||typeof value==='string');
}
