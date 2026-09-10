import { useTranslation } from 'react-i18next';

import './SkipToContent.css';

export const MAIN_CONTENT_ID = 'main-content';

export function SkipToContent() {
  const { t } = useTranslation();

  return (
    <a className="skip-to-content" href={`#${MAIN_CONTENT_ID}`}>
      {t('a11y.skipToContent')}
    </a>
  );
}
