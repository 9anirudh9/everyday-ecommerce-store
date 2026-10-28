import type {Address,PaymentMethod,Simulation} from './commerce-types';

export function validateAddress(input:unknown,strict=true):{address?:Address;errors:Record<string,string>}{
  const errors:Record<string,string>={};
  if(!input||typeof input!=='object'||Array.isArray(input))return {errors:{address:'Please enter a valid delivery address.'}};
  const source=input as Record<string,unknown>;
  const address={} as Address;
  for(const field of ['name','email','phone','street','city','state','pin'] as const){
    const value=typeof source[field]==='string'?(source[field] as string).trim():'';
    address[field]=value;
    if((strict||!['phone','state'].includes(field))&&(!value||value.length>299))errors[field]='This field is required and must be shorter than 300 characters.';
  }
  if(address.email&&!/^\S+@\S+\.\S+$/.test(address.email))errors.email='Enter a valid email address.';
  if(address.pin&&!/^\d{6}$/.test(address.pin))errors.pin='Enter a six-digit PIN code.';
  if(address.phone){
    const digits=address.phone.replace(/\D/g,'');
    if(!/^\+?[\d\s()-]+$/.test(address.phone)||!(digits.length===10||(digits.length===12&&digits.startsWith('91'))))errors.phone='Enter a valid phone number.';
  }
  return {address:Object.keys(errors).length?undefined:address,errors};
}
export function isPaymentMethod(value:unknown):value is PaymentMethod{return value==='card'||value==='paypal'||value==='pay-later'}
export function isSimulation(value:unknown):value is Simulation{return value==='success'||value==='decline'||value==='cancel'||value==='timeout'}
export function validateCheckoutExpectations(body:Record<string,unknown>,strict:boolean){
  if((strict||Object.prototype.hasOwnProperty.call(body,'expectedVersion'))&&(!Number.isInteger(body.expectedVersion)||Number(body.expectedVersion)<0))return {code:'INVALID_CART_VERSION',message:'Review the current cart before confirming.'};
  if(Object.prototype.hasOwnProperty.call(body,'expectedTotal')&&(typeof body.expectedTotal!=='number'||!Number.isFinite(body.expectedTotal)||body.expectedTotal<0))return {code:'INVALID_EXPECTED_TOTAL',message:'Use a valid expected order total.'};
  return null;
}
export function checkoutFingerprintInput(body:Record<string,unknown>,address:Address,strict:boolean,simulation:Simulation){
  const intent=(key:string)=>({provided:Object.prototype.hasOwnProperty.call(body,key),value:Object.prototype.hasOwnProperty.call(body,key)?body[key]:null});
  return {address,paymentMethod:body.paymentMethod,simulation,couponOverride:intent('coupon'),contractVersion:strict?2:1,expectedVersion:intent('expectedVersion'),expectedTotal:intent('expectedTotal')};
}
export function simulationFailure(simulation:Simulation){
  if(simulation==='decline')return {status:422,code:'PAYMENT_DECLINED',error:'The demo payment was declined. Your cart is unchanged.'};
  if(simulation==='cancel')return {status:409,code:'PAYMENT_CANCELLED',error:'The demo payment was cancelled. Your cart is unchanged.'};
  if(simulation==='timeout')return {status:408,code:'PAYMENT_TIMEOUT',error:'The demo payment timed out. Retry safely with the same confirmation.'};
  return null;
}
