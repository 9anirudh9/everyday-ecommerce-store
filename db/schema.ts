import { sqliteTable, text, integer, primaryKey, check, index, uniqueIndex } from 'drizzle-orm/sqlite-core';
import {sql} from 'drizzle-orm';
export const cart = sqliteTable('cart', { user: text('user').notNull(), product: integer('product').notNull(), qty: integer('qty').notNull() }, t=>[primaryKey({columns:[t.user,t.product]})]);
export const orders = sqliteTable('orders',{id:text('id').primaryKey(), user:text('user').notNull(), items:text('items').notNull(), total:integer('total').notNull(), address:text('address').notNull()});
export const cartState=sqliteTable('cart_state',{
  user:text('user').primaryKey().notNull(),version:integer('version').notNull().default(0),coupon:text('coupon'),updatedAt:text('updated_at').notNull().default(sql`CURRENT_TIMESTAMP`),
},table=>[check('cart_state_version_nonnegative',sql`${table.version} >= 0`)]);
export const commerceGuards=sqliteTable('commerce_guards',{
  id:text('id').primaryKey().notNull(),permitted:integer('permitted').notNull(),
},table=>[check('commerce_precondition',sql`${table.permitted} = 1`)]);
export const commerceMutations=sqliteTable('commerce_mutations',{
  user:text('user').notNull(),requestKey:text('request_key').notNull(),fingerprint:text('fingerprint').notNull(),createdAt:text('created_at').notNull(),
},table=>[primaryKey({columns:[table.user,table.requestKey]})]);
export const checkoutRequests=sqliteTable('checkout_requests',{
  user:text('user').notNull(),requestKey:text('request_key').notNull(),fingerprint:text('fingerprint').notNull(),orderId:text('order_id').notNull(),createdAt:text('created_at').notNull(),
},table=>[primaryKey({columns:[table.user,table.requestKey]}),uniqueIndex('checkout_order_unique').on(table.orderId),index('checkout_fingerprint').on(table.user,table.fingerprint,table.createdAt)]);
export const couponLimits=sqliteTable('coupon_limits',{
  code:text('code').primaryKey().notNull(),maxUses:integer('max_uses').notNull(),
},table=>[check('coupon_limits_nonnegative',sql`${table.maxUses} >= 0`)]);
export const couponRedemptions=sqliteTable('coupon_redemptions',{
  orderId:text('order_id').primaryKey().notNull(),user:text('user').notNull(),code:text('code').notNull(),createdAt:text('created_at').notNull(),
},table=>[index('coupon_redemptions_code').on(table.code),uniqueIndex('coupon_once_per_guest').on(table.user,table.code).where(sql`${table.code} IN ('FIRSTBUY','LIMITED20')`)]);
