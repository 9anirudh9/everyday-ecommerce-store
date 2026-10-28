import type {CouponError,Quote} from './commerce-types';

export type CouponContext={now:number;orderCount:number;guestUses:number;globalUses:number;globalLimit:number};
type CouponRule={label:string;percent?:number;fixed?:number;minimum?:number;cap?:number;expiresAt?:number;firstOrder?:boolean;limited?:boolean};
export const couponRules:Record<string,CouponRule>={
  EVERYDAY:{label:'50% off',percent:50},
  SAVE100:{label:'₹100 off orders from ₹1,000',fixed:100,minimum:1000},
  EXPIRED10:{label:'Expired 10% offer',percent:10,expiresAt:Date.parse('2020-01-01T00:00:00Z')},
  FIRSTBUY:{label:'10% off your first guest order, up to ₹500',percent:10,cap:500,firstOrder:true},
  LIMITED20:{label:'20% off, up to ₹500; five total uses and one per guest',percent:20,cap:500,limited:true,expiresAt:Date.parse('2030-01-01T00:00:00Z')},
  FREESHIP:{label:'Free delivery',fixed:0},
};
export const normalizeCoupon=(value:string)=>value.trim().toUpperCase();
export function evaluateCoupon(code:string,subtotalPaise:number,context:CouponContext):{discountPaise:number;error?:CouponError}{
  const rule=Object.prototype.hasOwnProperty.call(couponRules,code)?couponRules[code]:undefined;
  const fail=(errorCode:string,message:string)=>({discountPaise:0,error:{code:errorCode,message}});
  if(!rule)return fail('COUPON_INVALID','That coupon code is not valid.');
  if(rule.expiresAt!==undefined&&context.now>=rule.expiresAt)return fail('COUPON_EXPIRED','This coupon has expired.');
  if(subtotalPaise<(rule.minimum??0)*100)return fail('COUPON_MINIMUM','This coupon requires a subtotal of at least ₹1,000.');
  if(rule.firstOrder&&(context.orderCount>0||context.guestUses>0))return fail('FIRST_ORDER_ONLY','This coupon is available for your first guest order only.');
  if(rule.limited&&context.guestUses>0)return fail('COUPON_ALREADY_USED','This guest has already used this coupon.');
  if(rule.limited&&context.globalUses>=context.globalLimit)return fail('COUPON_LIMIT_REACHED','This coupon has reached its usage limit.');
  // Keep the original whole-rupee 50% rounding (₹1,499 -> ₹750 discount).
  const raw=rule.percent!==undefined?Math.round((subtotalPaise/100)*rule.percent/100)*100:(rule.fixed??0)*100;
  return {discountPaise:Math.max(0,Math.min(subtotalPaise,raw,(rule.cap??Number.MAX_SAFE_INTEGER)*100))};
}
export function calculateQuote(subtotalPaise:number,coupon:string|null,context:CouponContext,valid=true):Quote{
  const safe=Number.isSafeInteger(subtotalPaise)&&subtotalPaise>=0;
  if(!safe){subtotalPaise=0;valid=false}
  const applied=coupon?evaluateCoupon(coupon,subtotalPaise,context):{discountPaise:0};
  const discountPaise=applied.discountPaise;
  return {subtotal:subtotalPaise/100,discount:discountPaise/100,total:(subtotalPaise-discountPaise)/100,delivery:0,coupon,
    ...(applied.error?{couponError:applied.error}:{}),subtotalPaise,discountPaise,totalPaise:subtotalPaise-discountPaise,currency:'INR',valid:valid&&!applied.error};
}
