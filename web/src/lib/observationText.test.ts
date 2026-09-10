import { describe, expect, it, vi } from 'vitest';
import type { TFunction } from 'i18next';

import type { Observation } from '../api/endpoints';
import type { KeyExistenceCheck } from './observationText';
import {
  interpolationValues,
  observationBody,
  observationTitle,
  translatedOr,
} from './observationText';

import en from '../i18n/locales/en.json';
import hi from '../i18n/locales/hi.json';
import kn from '../i18n/locales/kn.json';
import ml from '../i18n/locales/ml.json';
import mr from '../i18n/locales/mr.json';
import ta from '../i18n/locales/ta.json';
import te from '../i18n/locales/te.json';

function fakeI18n(knownKeys: string[]) {
  return { exists: (key: string) => knownKeys.includes(key) };
}

const observation = (overrides: Partial<Observation> = {}): Observation => ({
  code: 'long_cycle_observed',
  severity: 'attention',
  title: 'A longer cycle than most',
  body: 'One of your recent cycles was 41 days, longer than the 35 days most cycles stay within.',
  titleKey: 'observations.long_cycle_observed.title',
  bodyKey: 'observations.long_cycle_observed.body',
  evidence: { longest_cycle_days: 41, threshold_days: 35, occurrences: 1 },
  isMedicalAdvice: false,
  disclaimerKey: 'insights.disclaimer',
  ...overrides,
});

describe('translatedOr', () => {
  it('renders the translation when the key exists', () => {
    const t = vi.fn(() => 'ஒரு நீண்ட சுழற்சி') as unknown as TFunction;

    const result = translatedOr(
      t,
      fakeI18n(['observations.long_cycle_observed.title']),
      'observations.long_cycle_observed.title',
      'A longer cycle than most',
    );

    expect(result).toBe('ஒரு நீண்ட சுழற்சி');
  });

  it('falls back to the English the server sent when the key is missing', () => {
    
    const t = vi.fn() as unknown as TFunction;

    const result = translatedOr(
      t,
      fakeI18n([]),
      'observations.a_rule_added_last_week.title',
      'Something the client has no string for yet',
    );

    expect(result).toBe('Something the client has no string for yet');
    expect(t).not.toHaveBeenCalled();
  });

  it('never renders a raw dotted key to the reader', () => {
    
    const key = 'observations.long_cycle_observed.title';
    const t = vi.fn(() => key) as unknown as TFunction;

    const result = translatedOr(t, fakeI18n([key]), key, 'A longer cycle than most');

    expect(result).toBe('A longer cycle than most');
  });

  it('falls back when a locale file has an empty string for the key', () => {
    const key = 'observations.long_cycle_observed.title';
    const t = vi.fn(() => '') as unknown as TFunction;

    expect(translatedOr(t, fakeI18n([key]), key, 'English')).toBe('English');
  });

  it('falls back when the i18n instance has no exists method', () => {
    const t = vi.fn(() => 'translated') as unknown as TFunction;

    const result = translatedOr(
      t,
      { exists: undefined } as unknown as KeyExistenceCheck,
      'observations.long_cycle_observed.title',
      'English',
    );

    expect(result).toBe('English');
  });

  it('passes the evidence through as interpolation values', () => {
    const key = 'observations.long_cycle_observed.body';
    const t = vi.fn(() => 'rendered') as unknown as TFunction;

    translatedOr(t, fakeI18n([key]), key, 'English', {
      longest_cycle_days: 41,
      threshold_days: 35,
    });

    expect(t).toHaveBeenCalledWith(key, {
      longest_cycle_days: 41,
      threshold_days: 35,
    });
  });
});

describe('interpolationValues', () => {
  it('passes numbers and strings straight through', () => {
    expect(
      interpolationValues({ longest_cycle_days: 41, start_date: '2026-05-01' }),
    ).toEqual({ longest_cycle_days: 41, start_date: '2026-05-01' });
  });

  it('joins arrays rather than letting them stringify themselves', () => {
    
    expect(
      interpolationValues({ symptoms_seen: ['cramps', 'back pain'] }),
    ).toEqual({ symptoms_seen: 'cramps, back pain' });
  });

  it('drops an empty array instead of rendering an empty placeholder', () => {
    expect(interpolationValues({ start_dates: [] })).toEqual({});
  });

  it('drops null and undefined rather than rendering the word "null"', () => {
    expect(
      interpolationValues({ a: null, b: undefined, c: 1 }),
    ).toEqual({ c: 1 });
  });

  it('skips nested objects', () => {
    expect(interpolationValues({ nested: { a: 1 }, count: 2 })).toEqual({ count: 2 });
  });

  it('handles a missing evidence object', () => {
    expect(interpolationValues(undefined)).toEqual({});
  });
});

describe('observationTitle and observationBody', () => {
  it('read the key and evidence off the observation', () => {
    const t = vi.fn((key: string) => `translated:${key}`) as unknown as TFunction;
    const i18n = fakeI18n([
      'observations.long_cycle_observed.title',
      'observations.long_cycle_observed.body',
    ]);

    expect(observationTitle(t, i18n, observation())).toBe(
      'translated:observations.long_cycle_observed.title',
    );
    expect(observationBody(t, i18n, observation())).toBe(
      'translated:observations.long_cycle_observed.body',
    );
  });

  it('fall back independently of each other', () => {
    
    const t = vi.fn(() => 'शीर्षक') as unknown as TFunction;
    const i18n = fakeI18n(['observations.long_cycle_observed.title']);

    expect(observationTitle(t, i18n, observation())).toBe('शीर्षक');
    expect(observationBody(t, i18n, observation())).toBe(observation().body);
  });
});

const BACKEND_OBSERVATION_CODES = [
  'insufficient_data',
  'no_recent_period_logged',
  'prolonged_bleeding',
  'repeated_heavy_flow',
  'short_cycle_observed',
  'long_cycle_observed',
  'variable_cycle_lengths',
  'period_later_than_usual',
  'symptom_increase',
  'sustained_high_stress',
  'short_sleep_trend',
  'severe_pain_pattern',
  'repeated_heavy_flow_concern',
  'frequent_bleeding_pattern',
] as const;

const TRANSLATED = { en, hi, kn, ml, mr, ta, te } as const;

type Catalogue = Record<string, { title?: string; body?: string }>;

describe('observation translation catalogue', () => {
  it.each(Object.keys(TRANSLATED))(
    '%s defines a title and body for every backend observation code',
    (code) => {
      const observations = (TRANSLATED[code as keyof typeof TRANSLATED] as {
        observations?: Catalogue;
      }).observations;

      expect(observations, `${code}.json has no observations block`).toBeDefined();

      const missing = BACKEND_OBSERVATION_CODES.filter(
        (observationCode) =>
          !observations?.[observationCode]?.title ||
          !observations?.[observationCode]?.body,
      );

      expect(missing, `${code} is missing: ${missing.join(', ')}`).toEqual([]);
    },
  );

  it('defines no observation the backend does not emit', () => {
    
    const extra = Object.keys((en as { observations: Catalogue }).observations).filter(
      (code) => !BACKEND_OBSERVATION_CODES.includes(code as never),
    );

    expect(extra, `unexpected observation codes: ${extra.join(', ')}`).toEqual([]);
  });

  it('translates the two seek_care rules in every locale', () => {
    
    for (const [locale, bundle] of Object.entries(TRANSLATED)) {
      const observations = (bundle as { observations: Catalogue }).observations;
      for (const code of ['no_recent_period_logged', 'prolonged_bleeding']) {
        expect(
          observations[code]?.body,
          `${locale} has no body for ${code}`,
        ).toBeTruthy();
      }
    }
  });

  it('keeps every placeholder the English string uses', () => {
    
    const placeholders = (text: string) =>
      [...text.matchAll(/\{\{(\w+)\}\}/g)].map((match) => match[1]).sort().join();

    const english = (en as { observations: Catalogue }).observations;

    for (const [locale, bundle] of Object.entries(TRANSLATED)) {
      if (locale === 'en') continue;
      const observations = (bundle as { observations: Catalogue }).observations;

      for (const code of BACKEND_OBSERVATION_CODES) {
        for (const field of ['title', 'body'] as const) {
          expect(
            placeholders(observations[code]?.[field] ?? ''),
            `${locale}.${code}.${field} placeholder mismatch`,
          ).toBe(placeholders(english[code]?.[field] ?? ''));
        }
      }
    }
  });

  it('uses only placeholders the backend actually sends as evidence', () => {
    
    const EVIDENCE_KEYS: Record<string, string[]> = {
      insufficient_data: ['logged_cycles', 'needed'],
      no_recent_period_logged: [
        'days_since_last_start',
        'threshold_days',
        'last_start_date',
      ],
      prolonged_bleeding: ['bleeding_days', 'threshold_days', 'start_date'],
      repeated_heavy_flow: ['heavy_cycles', 'window', 'start_dates'],
      short_cycle_observed: [
        'shortest_cycle_days',
        'threshold_days',
        'occurrences',
      ],
      long_cycle_observed: ['longest_cycle_days', 'threshold_days', 'occurrences'],
      variable_cycle_lengths: [
        'shortest_cycle_days',
        'longest_cycle_days',
        'largest_swing_days',
        'cycles_compared',
      ],
      period_later_than_usual: [
        'current_cycle_day',
        'average_cycle_days',
        'days_past_average',
      ],
      symptom_increase: [
        'latest_symptom_count',
        'previous_average',
        'cycles_compared',
        'symptoms',
      ],
      sustained_high_stress: ['average_stress', 'entries', 'scale_max'],
      short_sleep_trend: ['average_sleep_hours', 'entries'],
      severe_pain_pattern: ['pain_cycles', 'window', 'start_dates', 'symptoms_seen'],
      repeated_heavy_flow_concern: ['heavy_cycles', 'window', 'start_dates'],
      frequent_bleeding_pattern: [
        'consecutive_short_cycles',
        'threshold_days',
        'recent_gaps',
      ],
    };

    const english = (en as { observations: Catalogue }).observations;

    for (const code of BACKEND_OBSERVATION_CODES) {
      const allowed = EVIDENCE_KEYS[code];
      for (const field of ['title', 'body'] as const) {
        const used = [
          ...(english[code]?.[field] ?? '').matchAll(/\{\{(\w+)\}\}/g),
        ].map((match) => match[1]);

        for (const placeholder of used) {
          expect(
            allowed,
            `en.${code}.${field} uses {{${placeholder}}}, which is not in that rule's evidence`,
          ).toContain(placeholder);
        }
      }
    }
  });
});
