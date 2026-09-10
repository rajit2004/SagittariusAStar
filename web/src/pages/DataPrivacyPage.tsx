import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import {
  confirmAccountDeletion,
  fetchDataExport,
  fetchDataSummary,
  requestAccountDeletion,
  type DataSummary,
  type DeletionPreview,
  type ExportFormat,
} from '../api/endpoints';

const CONFIRMATION_WORD = 'DELETE';

type Stage = 'idle' | 'previewing' | 'confirming';

function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString(locale);
}

function friendlyError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      response?: { status?: number; data?: { detail?: string } };
    };
    if (!axiosErr.response) return fallback;
    if (axiosErr.response.data?.detail) return axiosErr.response.data.detail;
  }
  return fallback;
}

export function DataPrivacyPage() {
  const { t, i18n } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<DataSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [downloading, setDownloading] = useState<ExportFormat | null>(null);
  const [exportError, setExportError] = useState('');
  const [exportedName, setExportedName] = useState('');

  const [stage, setStage] = useState<Stage>('idle');
  const [preview, setPreview] = useState<DeletionPreview | null>(null);
  const [typed, setTyped] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setSummary(await fetchDataSummary());
    } catch (err) {
      setError(friendlyError(err, t('privacy.loadError')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const download = async (format: ExportFormat) => {
    setDownloading(format);
    setExportError('');
    setExportedName('');
    try {
      const { blob, filename } = await fetchDataExport(format);

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      
      URL.revokeObjectURL(url);

      setExportedName(filename);
    } catch (err) {
      setExportError(friendlyError(err, t('privacy.exportError')));
    } finally {
      setDownloading(null);
    }
  };

  const startDeletion = async () => {
    setDeleteError('');
    setStage('previewing');
    try {
      setPreview(await requestAccountDeletion());
      setStage('confirming');
    } catch (err) {
      setDeleteError(friendlyError(err, t('privacy.deleteError')));
      setStage('idle');
    }
  };

  const cancelDeletion = () => {
    setStage('idle');
    setPreview(null);
    setTyped('');
    setDeleteError('');
  };

  const confirmDeletion = async () => {
    if (!preview) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await confirmAccountDeletion(preview.confirmationToken);
    } catch (err) {
      
      setDeleteError(friendlyError(err, t('privacy.deleteError')));
      setDeleting(false);
      return;
    }

    await logout('/login');
    navigate('/login', { replace: true });
  };

  if (loading && !summary) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  const impact = preview?.impact ?? summary;
  const canConfirm = typed.trim().toUpperCase() === CONFIRMATION_WORD && !deleting;

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('privacy.title')}</h1>
        <p className="card-sub">{t('privacy.subtitle')}</p>
      </header>

      {error ? (
        <div className="error-card">
          <p>{error}</p>
          <button type="button" className="primary-btn" onClick={() => void load()}>
            {t('common.retry')}
          </button>
        </div>
      ) : null}

      {summary ? (
        <section className="glass-card">
          <p className="card-label">{t('privacy.storedLabel')}</p>
          <p className="card-sub">
            {t('privacy.storedTotal', { count: summary.totalRecords })}
          </p>

          <ul className="data-category-list">
            {summary.categories.map((category) => (
              <li key={category.key} className="data-category">
                <div className="data-category-head">
                  <span className="data-category-label">{category.label}</span>
                  <span className="data-category-count">{category.recordCount}</span>
                </div>
                {category.earliestEntry ? (
                  <p className="card-sub">
                    {t('privacy.dateRange', {
                      from: formatDate(category.earliestEntry, i18n.language),
                      to: formatDate(category.latestEntry, i18n.language),
                    })}
                  </p>
                ) : null}
                <p className="card-sub">{category.retentionNote}</p>
                {category.storedFields.length > 0 ? (
                  <p className="data-category-fields">
                    {t('privacy.fields')}: {category.storedFields.join(', ')}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="glass-card">
        <p className="card-label">{t('privacy.exportLabel')}</p>
        <p className="card-sub">{t('privacy.exportBody')}</p>

        <div className="export-actions">
          <button
            type="button"
            className="primary-btn"
            disabled={downloading !== null}
            onClick={() => void download('json')}
          >
            {downloading === 'json' ? t('common.loading') : t('privacy.exportJson')}
          </button>
          <button
            type="button"
            className="ghost-btn"
            disabled={downloading !== null}
            onClick={() => void download('csv')}
          >
            {downloading === 'csv' ? t('common.loading') : t('privacy.exportCsv')}
          </button>
        </div>

        {exportedName ? (
          <p className="success-text">{t('privacy.exportReady', { filename: exportedName })}</p>
        ) : null}
        {exportError ? <p className="error-text">{exportError}</p> : null}
      </section>

      <section className="glass-card danger-zone">
        <p className="card-label">{t('privacy.deleteLabel')}</p>

        {stage !== 'confirming' ? (
          <>
            <p className="card-sub">{t('privacy.deleteBody')}</p>
            {deleteError ? <p className="error-text">{deleteError}</p> : null}
            <button
              type="button"
              className="danger-btn full"
              disabled={stage === 'previewing'}
              onClick={() => void startDeletion()}
            >
              {stage === 'previewing' ? t('common.loading') : t('privacy.deleteStart')}
            </button>
          </>
        ) : (
          <>
            {}
            <p className="warning-text">{preview?.warning}</p>

            {impact ? (
              <ul className="deletion-impact">
                {impact.categories
                  .filter((category) => category.recordCount > 0)
                  .map((category) => (
                    <li key={category.key}>
                      {t('privacy.willDelete', {
                        count: category.recordCount,
                        label: category.label,
                      })}
                    </li>
                  ))}
              </ul>
            ) : null}

            <p className="card-sub">{t('privacy.exportFirst')}</p>

            <label className="confirm-field">
              {t('privacy.typeToConfirm', { word: CONFIRMATION_WORD })}
              <input
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                aria-label={t('privacy.typeToConfirm', { word: CONFIRMATION_WORD })}
                autoComplete="off"
              />
            </label>

            {deleteError ? <p className="error-text">{deleteError}</p> : null}

            <div className="export-actions">
              <button
                type="button"
                className="danger-btn"
                disabled={!canConfirm}
                onClick={() => void confirmDeletion()}
              >
                {deleting ? t('common.loading') : t('privacy.deleteConfirm')}
              </button>
              <button
                type="button"
                className="ghost-btn"
                disabled={deleting}
                onClick={cancelDeletion}
              >
                {t('common.cancel')}
              </button>
            </div>
          </>
        )}
      </section>

      <Link to="/settings" className="text-link">
        {t('privacy.backToSettings')}
      </Link>
    </div>
  );
}
