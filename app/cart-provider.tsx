'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { translate } from '@/lib/i18n';
import { useLanguage } from './language-provider';

export type CartItem = { product: number; qty: number };
type CartStatus = 'loading' | 'ready' | 'error';
type CartContextValue = {
  items: CartItem[];
  status: CartStatus;
  hasLoaded: boolean;
  error: string;
  setReadyItems: (items: CartItem[]) => void;
  refresh: () => Promise<void>;
};

const CartContext = createContext<CartContextValue | null>(null);

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error('useCart must be used inside CartProvider');
  return context;
}

export default function CartProvider({ children }: { children: ReactNode }) {
  const { language } = useLanguage();
  const [items, setItems] = useState<CartItem[]>([]);
  const [status, setStatus] = useState<CartStatus>('loading');
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState('');
  const requestVersion = useRef(0);
  const invalidateReads = useCallback(() => { requestVersion.current++; }, []);

  const refresh = useCallback(async () => {
    const version = ++requestVersion.current;
    setStatus('loading');
    setError('');
    try {
      const response = await fetch('/api/shop', { cache: 'no-store' });
      const data = await response.json() as { error?: string; items?: CartItem[] };
      if (!response.ok) throw Error(translate(language, data.error || 'Unable to load your cart.'));
      if (!Array.isArray(data.items) || data.items.some(item => !item || typeof item !== 'object' || !Number.isInteger(item.product) || !Number.isInteger(item.qty) || item.qty < 1 || item.qty > 10)) {
        throw Error(translate(language, 'Unable to load your cart.'));
      }
      if (version !== requestVersion.current) return;
      setItems(data.items);
      setHasLoaded(true);
      setStatus('ready');
    } catch (cause) {
      if (version !== requestVersion.current) return;
      setError((cause as Error).message || translate(language, 'Unable to load your cart.'));
      setStatus('error');
    }
  }, [language]);

  const setReadyItems = useCallback((nextItems: CartItem[]) => {
    // A successful write is newer than any read already in flight.
    invalidateReads();
    setItems(nextItems);
    setHasLoaded(true);
    setError('');
    setStatus('ready');
  }, [invalidateReads]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    const handleFocus = () => { void refresh(); };
    window.addEventListener('focus', handleFocus);
    return () => { invalidateReads(); window.clearTimeout(timer); window.removeEventListener('focus', handleFocus); };
  }, [refresh, invalidateReads]);

  const value = useMemo(() => ({ items, status, hasLoaded, error, setReadyItems, refresh }), [items, status, hasLoaded, error, setReadyItems, refresh]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
