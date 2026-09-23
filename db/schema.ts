import { sqliteTable, text, integer, primaryKey } from 'drizzle-orm/sqlite-core';
export const cart = sqliteTable('cart', { user: text('user').notNull(), product: integer('product').notNull(), qty: integer('qty').notNull() }, t=>[primaryKey({columns:[t.user,t.product]})]);
export const orders = sqliteTable('orders',{id:text('id').primaryKey(), user:text('user').notNull(), items:text('items').notNull(), total:integer('total').notNull(), address:text('address').notNull()});
