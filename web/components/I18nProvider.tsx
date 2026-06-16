'use client';

import { ReactNode, useEffect, useState } from 'react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/lib/i18n';
import { normalizeEnabledLanguage } from '@/lib/language-features';

export function I18nProvider({ children }: { children: ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const syncDocumentLanguage = (language?: string) => {
      document.documentElement.lang = normalizeEnabledLanguage(
        language ?? i18n.resolvedLanguage ?? i18n.language,
      );
    };

    const handleInitialized = () => {
      syncDocumentLanguage();
      setIsInitialized(true);
    };

    if (i18n.isInitialized) {
      handleInitialized();
    } else {
      i18n.on('initialized', handleInitialized);
    }

    i18n.on('languageChanged', syncDocumentLanguage);

    return () => {
      i18n.off('initialized', handleInitialized);
      i18n.off('languageChanged', syncDocumentLanguage);
    };
  }, []);

  if (!isInitialized) {
    // Show a blank screen or a loading shimmer that matches Argus aesthetics
    return <div className="bg-[#191c1f] min-h-full" />;
  }

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}
