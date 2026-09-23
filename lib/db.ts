import { env } from 'cloudflare:workers';
export const db=()=> (env as unknown as {DB:D1Database}).DB;
