
export const ASSISTANT_LANGUAGES = [
  'en',
  'hi',
  'mr',
  'ta',
  'te',
  'kn',
  'ml',
  'gu',
] as const;

export type AssistantLanguage = (typeof ASSISTANT_LANGUAGES)[number];

const SUPPORTED = new Set<string>(ASSISTANT_LANGUAGES);

export function toAssistantLanguage(uiLanguage: string | undefined): AssistantLanguage {
  if (!uiLanguage) return 'en';

  const base = uiLanguage.trim().toLowerCase().replace(/_/g, '-').split('-')[0];

  return SUPPORTED.has(base) ? (base as AssistantLanguage) : 'en';
}

export function isAssistantLanguageFallback(uiLanguage: string | undefined): boolean {
  if (!uiLanguage) return false;
  const base = uiLanguage.trim().toLowerCase().replace(/_/g, '-').split('-')[0];
  return base !== 'en' && !SUPPORTED.has(base);
}
