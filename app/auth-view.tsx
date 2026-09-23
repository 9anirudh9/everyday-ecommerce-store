import Link from 'next/link';

export default function AuthView(){
  return <main className="auth">
    <span className="eyebrow">SHOP AS A GUEST</span>
    <h1>No account needed.</h1>
    <p>Your cart is kept securely for this browser, so you can browse and checkout without signing in.</p>
    <Link className="primary" href="/products">Continue shopping</Link>
  </main>
}
