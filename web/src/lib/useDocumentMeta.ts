import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import {
  applyDocumentLanguage,
  applyDocumentTitle,
  applyMetaProperty,
  applyMetaTag,
  composeTitle,
} from './documentMeta';

export function useDocumentMeta(titleKey: string, descriptionKey?: string): void {
  const { t, i18n } = useTranslation();
  const language = i18n.language;

  useEffect(() => {
    const appName = t('meta.appName');
    const title = composeTitle(t(titleKey), appName);

    applyDocumentTitle(title);
    
    applyMetaProperty('og:title', title);

    if (descriptionKey) {
      const description = t(descriptionKey);
      applyMetaTag('description', description);
      applyMetaProperty('og:description', description);
    }
    
  }, [t, i18n, language, titleKey, descriptionKey]);
}

export function useDocumentLanguage(): void {
  const { i18n } = useTranslation();
  const language = i18n.language;

  useEffect(() => {
    applyDocumentLanguage(language);
  }, [language]);
}

export function DocumentLanguage(): null {
  useDocumentLanguage();
  return null;
}
