import { cookies } from 'next/headers';

// A host-only, HTTP-only capability keeps each guest's cart separate.
export async function shopSession() {
  const jar = await cookies();
  let token = jar.get('__Host-everyday-guest')?.value;
  if (!token || !/^[a-f0-9]{64}$/.test(token)) {
    token = Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join('');
    jar.set('__Host-everyday-guest', token, {
      httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: 60 * 60 * 24 * 30,
    });
  }
  return { userId: `guest:${token}` };
}
