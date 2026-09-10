import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { MAIN_CONTENT_ID } from './SkipToContent';
import { routeTitleKey } from '../lib/routeTitles';

export function RouteAnnouncer() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [message, setMessage] = useState('');
  const isFirstRender = useRef(true);

  useEffect(() => {
    
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    setMessage(t('a11y.navigatedTo', { page: t(routeTitleKey(pathname)) }));

    const main = document.getElementById(MAIN_CONTENT_ID);
    
    main?.focus({ preventScroll: true });
  }, [pathname, t]);

  return (
    
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {message}
    </div>
  );
}
