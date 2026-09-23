import {shopSession} from '@/lib/shop-session';
import {db} from '@/lib/db';
import {products} from '@/lib/products';

export const dynamic='force-dynamic';

type CartRow={product:number,qty:number};
type RequestBody={action?:string;address?:Record<string,string>;product?:number;qty?:number;coupon?:string;paymentMethod?:string};

export async function GET(){
  try{
    const user=await shopSession();
    const result=await db().prepare('SELECT product, qty FROM cart WHERE user=?').bind(user.userId).all();
    return Response.json({items:result.results},{headers:{'Cache-Control':'private, no-store'}});
  }catch{return Response.json({error:'Unable to load your cart. Please try again.'},{status:503})}
}

export async function POST(request:Request){
  try{
    if(request.headers.get('origin')!==new URL(request.url).origin)return Response.json({error:'Invalid request'},{status:403});
    const user=await shopSession();
    const body=await request.json() as RequestBody;
    if(body.action==='checkout'){
      const address=body.address;
      if(!address||!['name','email','street','city','pin'].every(key=>typeof address[key]==='string'&&address[key].trim().length>0&&address[key].length<300)||!/^\d{6}$/.test(address.pin)||!/^\S+@\S+\.\S+$/.test(address.email))return Response.json({error:'Please enter a valid delivery address.'},{status:400});
      if(!body.paymentMethod||!['card','paypal','pay-later'].includes(body.paymentMethod))return Response.json({error:'Please select a valid payment option.'},{status:400});
      const rows=await db().prepare('SELECT product, qty FROM cart WHERE user=?').bind(user.userId).all<CartRow>();
      if(!rows.results.length)return Response.json({error:'Your cart is empty.'},{status:400});
      const subtotal=rows.results.reduce((sum,item)=>sum+(products.find(product=>product.id===item.product)?.price||0)*item.qty,0);
      const validCoupon=body.coupon?.trim().toUpperCase()==='EVERYDAY';
      const discount=validCoupon?Math.round(subtotal*.5):0;
      const total=subtotal-discount;
      const id=crypto.randomUUID();
      const orderItems={products:rows.results,coupon:validCoupon?'EVERYDAY':null,subtotal,discount,paymentMethod:body.paymentMethod};
      await db().batch([
        db().prepare('INSERT INTO orders (id,user,items,total,address) VALUES (?,?,?,?,?)').bind(id,user.userId,JSON.stringify(orderItems),total,JSON.stringify(address)),
        db().prepare('DELETE FROM cart WHERE user=?').bind(user.userId),
      ]);
      return Response.json({id,total,discount});
    }
    if(!Number.isInteger(body.product)||!products.some(product=>product.id===body.product)||!Number.isInteger(body.qty)||body.qty!<0||body.qty!>10)return Response.json({error:'Invalid quantity.'},{status:400});
    if(body.qty===0)await db().prepare('DELETE FROM cart WHERE user=? AND product=?').bind(user.userId,body.product).run();
    else await db().prepare('INSERT INTO cart (user,product,qty) VALUES (?,?,?) ON CONFLICT(user,product) DO UPDATE SET qty=excluded.qty').bind(user.userId,body.product,body.qty).run();
    return Response.json({ok:true});
  }catch{return Response.json({error:'Could not save. Please try again.'},{status:503})}
}
