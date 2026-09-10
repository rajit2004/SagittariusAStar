import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from './useAuth';

export function ProviderRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const { t } = useTranslation();

  if (loading) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  if (!user) {
    return <Navigate to="/provider/login" replace />;
  }

  if (user.role !== 'provider') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
