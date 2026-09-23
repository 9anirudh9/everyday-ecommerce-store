# Everyday Ecommerce Store

A responsive demo ecommerce application for home décor and accessories.

Live site: [Everyday Shop](https://everyday-shop-anirudh.cidirianirudh.chatgpt.site)

## Features

- Product catalogue and individual product pages
- Accessories collection
- Live search suggestions and search results
- Persistent guest cart with quantity controls
- `EVERYDAY` coupon for a 50% demo discount
- Three-step checkout: delivery, payment and confirmation
- Card, PayPal and pay-later demo payment options
- Automatic `MM/YY` card-expiry formatting
- Responsive desktop and mobile layouts

## Tech stack

- TypeScript and React
- Next-compatible Vinext runtime
- Tailwind CSS
- Cloudflare D1 with Drizzle migrations
- Lucide icons and Shadcn UI primitives

## Local setup

Requires Node.js 22.13 or newer and pnpm 11 or newer.

```bash
pnpm install
pnpm dev
```

Then open the local URL printed in the terminal.

The application expects a Cloudflare D1 database bound as `DB`. Apply the
included migration at `drizzle/0000_legal_the_twelve.sql` to the bound database
before using cart or checkout features. For example, with a Wrangler
configuration that declares the `DB` binding:

```bash
pnpm exec wrangler d1 execute DB --local --file drizzle/0000_legal_the_twelve.sql
```

## Build

```bash
pnpm build
```

## Important demo notes

This project is a portfolio/demo store. It does not process payments or ship orders. Payment fields accept test data only, and sensitive payment details are not stored. Product images are sourced from [DummyJSON](https://dummyjson.com/).

No authentication, payment API keys or image-service configuration are
required. Payments are demonstrations only; no real transactions occur.

The current runtime uses Vinext, Cloudflare Workers and D1. Deploying directly
to Vercel requires replacing D1 with a Vercel-compatible database such as
Postgres or Neon.
