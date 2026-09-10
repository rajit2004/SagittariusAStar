import { useTranslation } from 'react-i18next';
import type { DashboardPrediction } from '../api/endpoints';

interface PredictionCardProps {
  prediction: DashboardPrediction | null | undefined;
  
  fallbackDays: number | null;
}

function formatDate(value: string | null, locale: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString(locale, { day: 'numeric', month: 'short' });
}

export function PredictionCard({ prediction, fallbackDays }: PredictionCardProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  if (!prediction) {
    return (
      <div className="prediction-card-body">
        <p className="card-label">{t('home.nextPeriod')}</p>
        <p className="cycle-next-number">{fallbackDays == null ? '—' : fallbackDays}</p>
        <p className="card-sub">{t('home.days')}</p>
        {}
        <p className="fertile-window-disclaimer">{t('home.fertileWindowDisclaimer')}</p>
      </div>
    );
  }

  const { isOverdue, daysOverdue, daysUntilNextPeriod, phase, confidence, estimateSource } =
    prediction;
  const nextDate = formatDate(prediction.nextPeriodDate, locale);
  const earliest = formatDate(prediction.predictedRange?.earliest ?? null, locale);
  const latest = formatDate(prediction.predictedRange?.latest ?? null, locale);
  const fertileStart = formatDate(prediction.fertileWindow?.start ?? null, locale);
  const fertileEnd = formatDate(prediction.fertileWindow?.end ?? null, locale);

  return (
    <div className="prediction-card-body">
      {isOverdue ? (
        <>
          <p className="card-label">{t('prediction.overdueLabel')}</p>
          <p className="cycle-next-number is-overdue">{daysOverdue}</p>
          <p className="card-sub">{t('prediction.daysLate', { count: daysOverdue })}</p>
        </>
      ) : (
        <>
          <p className="card-label">{t('home.nextPeriod')}</p>
          <p className="cycle-next-number">
            {daysUntilNextPeriod == null ? '—' : daysUntilNextPeriod}
          </p>
          <p className="card-sub">
            {daysUntilNextPeriod === 0 ? t('prediction.dueToday') : t('home.days')}
          </p>
        </>
      )}

      {nextDate ? <p className="prediction-date">{nextDate}</p> : null}

      {}
      {earliest && latest && earliest !== latest ? (
        <p className="prediction-range">{t('prediction.range', { from: earliest, to: latest })}</p>
      ) : null}

      <div className="prediction-tags">
        <span className={`status-pill phase-${phase}`}>{t(`prediction.phase.${phase}`)}</span>
        <span className={`status-pill confidence-${confidence}`}>
          {t(`prediction.confidence.${confidence}`)}
        </span>
      </div>

      {}
      <p className="prediction-source">{t(`prediction.source.${estimateSource}`)}</p>

      {fertileStart && fertileEnd ? (
        <p className="fertile-window">
          {t('prediction.fertileWindow', { from: fertileStart, to: fertileEnd })}
        </p>
      ) : null}

      <p className="fertile-window-disclaimer">{t('home.fertileWindowDisclaimer')}</p>
    </div>
  );
}
