import type {Product} from './products';

/** Demo stock is shared by browser hints and authoritative request validation. */
export function maxProductQuantity(product:Pick<Product,'stock'>){
  return Math.min(10,Math.max(0,Math.floor(product.stock)));
}

export function validateStockQuantity(product:Pick<Product,'stock'>,qty:number){
  if(!Number.isInteger(qty)||qty<1)return {valid:false,error:'Choose a whole quantity of at least 1.',code:'INVALID_QUANTITY'};
  if(product.stock<=0)return {valid:false,error:'This product is out of stock. Please choose another item.',code:'OUT_OF_STOCK'};
  if(qty>maxProductQuantity(product))return {valid:false,error:`Only ${maxProductQuantity(product)} can be added to this cart. Please update the quantity.`,code:'STOCK_CHANGED'};
  return {valid:true};
}
