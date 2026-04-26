'use client';

import { ReactNode, useEffect, useState } from 'react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/lib/i18n';

export function I18nProvider({ children }: { children: ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    if (i18n.isInitialized) {
      setIsInitialized(true);
    } else {
      i18n.on('initialized', () => {
        setIsInitialized(true);
      });
    }
  }, []);

  if (!isInitialized) {
    // Show a blank screen or a loading shimmer that matches Argus aesthetics
    return <div className="bg-[#191c1f] min-h-full" />;
  }

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}
