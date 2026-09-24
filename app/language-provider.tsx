'use client';

import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { languageCookie, translate, type Language } from '@/lib/i18n';

type LanguageContextValue = {
  language: Language;
  chooseLanguage: (language: Language) => void;
  t: (english: string, values?: Record<string, string | number>) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used inside LanguageProvider');
  return context;
}

export default function LanguageProvider({ initialLanguage, children }: {
  initialLanguage: Language | null;
  children: React.ReactNode;
}) {
  const [language, setLanguage] = useState<Language>(initialLanguage ?? 'en');
  const [selected, setSelected] = useState(initialLanguage !== null);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!selected) {
      if (!dialog.current?.open) dialog.current?.showModal();
    } else if (dialog.current?.open) {
      dialog.current.close();
    }
  }, [selected]);

  function chooseLanguage(next: Language) {
    document.cookie = `${languageCookie}=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
    document.documentElement.lang = next;
    setLanguage(next);
    setSelected(true);
  }

  const t = (english: string, values?: Record<string, string | number>) => translate(language, english, values);

  return <LanguageContext.Provider value={{ language, chooseLanguage, t }}>
    {children}
    {!selected && <dialog ref={dialog} className="language-dialog" aria-labelledby="language-dialog-title" aria-describedby="language-dialog-description" onCancel={event => event.preventDefault()}>
      <span className="eyebrow">EVERYDAY</span>
      <h2 id="language-dialog-title">Choose your language / Choisissez votre langue</h2>
      <p id="language-dialog-description">Select a language to start shopping. / Choisissez une langue pour commencer vos achats.</p>
      <div className="language-options">
        <button type="button" autoFocus data-testid="language-english" onClick={() => chooseLanguage('en')} lang="en">English</button>
        <button type="button" data-testid="language-french" onClick={() => chooseLanguage('fr')} lang="fr">Français</button>
      </div>
    </dialog>}
  </LanguageContext.Provider>;
}
