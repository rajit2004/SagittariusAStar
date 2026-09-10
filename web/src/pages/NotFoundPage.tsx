import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useDocumentMeta } from '../lib/useDocumentMeta';

export function NotFoundPage() {
  useDocumentMeta('meta.notFound.title', 'meta.notFound.description');
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <div className="page not-found-page">
      <h1>{t('errors.notFoundTitle')}</h1>
      <p className="card-sub">{t('errors.notFoundBody')}</p>

      <p className="card-sub">
        <code className="not-found-path">{location.pathname}</code>
      </p>

      <div className="error-boundary-actions">
        <Link className="primary-btn" to="/">
          {t('errors.goHome')}
        </Link>
      </div>
    </div>
  );
}
