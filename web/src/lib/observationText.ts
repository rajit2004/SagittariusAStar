
import type { TFunction } from 'i18next';

import type { Observation } from '../api/endpoints';

export interface KeyExistenceCheck {
  exists(key: string): boolean;
}

export function interpolationValues(
  evidence: Record<string, unknown> | undefined,
): Record<string, string | number> {
  const values: Record<string, string | number> = {};
  if (!evidence) return values;

  for (const [key, value] of Object.entries(evidence)) {
    if (value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      const items = value.filter((item) => item !== null && item !== undefined);
      if (items.length > 0) values[key] = items.join(', ');
      continue;
    }

    if (typeof value === 'number' || typeof value === 'string') {
      values[key] = value;
      continue;
    }

    if (typeof value === 'boolean') {
      values[key] = String(value);
    }
    
  }

  return values;
}

export function translatedOr(
  t: TFunction,
  i18n: KeyExistenceCheck,
  key: string,
  fallback: string,
  evidence?: Record<string, unknown>,
): string {
  if (!key || typeof i18n.exists !== 'function' || !i18n.exists(key)) {
    return fallback;
  }

  const rendered = t(key, interpolationValues(evidence));

  return typeof rendered === 'string' && rendered && rendered !== key
    ? rendered
    : fallback;
}

export function observationTitle(
  t: TFunction,
  i18n: KeyExistenceCheck,
  observation: Observation,
): string {
  return translatedOr(
    t,
    i18n,
    observation.titleKey,
    observation.title,
    observation.evidence,
  );
}

export function observationBody(
  t: TFunction,
  i18n: KeyExistenceCheck,
  observation: Observation,
): string {
  return translatedOr(
    t,
    i18n,
    observation.bodyKey,
    observation.body,
    observation.evidence,
  );
}
