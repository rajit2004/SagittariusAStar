
const RTL_LANGUAGES = new Set(['ar', 'fa', 'he', 'ur']);

export function toDocumentLang(language: string | undefined): string {
  if (!language) return 'en';
  const trimmed = language.trim();
  if (!trimmed) return 'en';
  return trimmed.replace(/_/g, '-');
}

export function directionFor(language: string | undefined): 'ltr' | 'rtl' {
  const base = toDocumentLang(language).toLowerCase().split('-')[0];
  return RTL_LANGUAGES.has(base) ? 'rtl' : 'ltr';
}

export function applyDocumentLanguage(language: string | undefined): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.setAttribute('lang', toDocumentLang(language));
  root.setAttribute('dir', directionFor(language));
}

export function applyDocumentTitle(title: string | undefined | null): void {
  if (typeof document === 'undefined') return;
  if (!title || !title.trim()) return;
  document.title = title.trim();
}

export function applyMetaTag(name: string, content: string | undefined | null): void {
  if (typeof document === 'undefined') return;
  if (!content || !content.trim()) return;

  let tag = document.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('name', name);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content.trim());
}

export function applyMetaProperty(
  property: string,
  content: string | undefined | null,
): void {
  if (typeof document === 'undefined') return;
  if (!content || !content.trim()) return;

  let tag = document.head.querySelector<HTMLMetaElement>(
    `meta[property="${property}"]`,
  );
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('property', property);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content.trim());
}

export function composeTitle(pageTitle: string | undefined, appName: string): string {
  const page = pageTitle?.trim();
  if (!page || page === appName) return appName;
  return `${page} · ${appName}`;
}
