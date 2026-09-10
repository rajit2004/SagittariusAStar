import { describe, expect, it } from 'vitest';
import {
  PHASE_COLORS,
  addDays,
  addMonths,
  cycleDayFor,
  daysBetween,
  isSameDay,
  endOfMonth,
  lutealLengthFor,
  monthWindow,
  parseISODate,
  phaseFor,
  startOfMonth,
  toISODate,
} from './dates';

describe('toISODate', () => {
  it('pads month and day', () => {
    expect(toISODate(new Date(2026, 0, 5))).toBe('2026-01-05');
  });

  it('uses local components, not UTC', () => {
    
    const lateEvening = new Date(2026, 4, 1, 23, 30);
    expect(toISODate(lateEvening)).toBe('2026-05-01');
  });

  it('handles the last day of a year', () => {
    expect(toISODate(new Date(2026, 11, 31))).toBe('2026-12-31');
  });

  it('handles a leap day', () => {
    expect(toISODate(new Date(2024, 1, 29))).toBe('2024-02-29');
  });
});

describe('parseISODate', () => {
  it('round-trips with toISODate', () => {
    for (const iso of ['2026-01-01', '2024-02-29', '2026-12-31', '2026-07-04']) {
      expect(toISODate(parseISODate(iso))).toBe(iso);
    }
  });

  it('produces a local midnight, not a UTC one', () => {
    const parsed = parseISODate('2026-05-01');
    expect(parsed.getHours()).toBe(0);
    expect(parsed.getDate()).toBe(1);
  });
});

describe('startOfMonth', () => {
  it('returns the first of the month', () => {
    expect(toISODate(startOfMonth(new Date(2026, 4, 17)))).toBe('2026-05-01');
  });

  it('is idempotent', () => {
    const first = startOfMonth(new Date(2026, 4, 17));
    expect(toISODate(startOfMonth(first))).toBe('2026-05-01');
  });
});

describe('addMonths', () => {
  it('moves forward', () => {
    expect(toISODate(addMonths(new Date(2026, 4, 15), 1))).toBe('2026-06-01');
  });

  it('rolls over the year boundary going forward', () => {
    expect(toISODate(addMonths(new Date(2026, 11, 15), 1))).toBe('2027-01-01');
  });

  it('rolls over the year boundary going back', () => {
    expect(toISODate(addMonths(new Date(2026, 0, 15), -1))).toBe('2025-12-01');
  });

  it('does not overflow from a 31-day month into the wrong month', () => {
    
    expect(toISODate(addMonths(new Date(2026, 0, 31), 1))).toBe('2026-02-01');
  });
});

describe('isSameDay', () => {
  it('ignores the time of day', () => {
    expect(isSameDay(new Date(2026, 4, 1, 0, 1), new Date(2026, 4, 1, 23, 59))).toBe(true);
  });

  it('distinguishes the same day in different months', () => {
    expect(isSameDay(new Date(2026, 4, 1), new Date(2026, 5, 1))).toBe(false);
  });

  it('distinguishes the same date in different years', () => {
    expect(isSameDay(new Date(2025, 4, 1), new Date(2026, 4, 1))).toBe(false);
  });
});

describe('daysBetween', () => {
  it('counts forward', () => {
    expect(daysBetween(new Date(2026, 4, 1), new Date(2026, 4, 8))).toBe(7);
  });

  it('counts backward as a negative', () => {
    expect(daysBetween(new Date(2026, 4, 8), new Date(2026, 4, 1))).toBe(-7);
  });

  it('is zero for the same day at different times', () => {
    expect(daysBetween(new Date(2026, 4, 1, 1), new Date(2026, 4, 1, 23))).toBe(0);
  });

  it('crosses a month boundary', () => {
    expect(daysBetween(new Date(2026, 3, 28), new Date(2026, 4, 2))).toBe(4);
  });

  it('counts a leap day', () => {
    expect(daysBetween(new Date(2024, 1, 28), new Date(2024, 2, 1))).toBe(2);
  });

  it('survives a DST transition', () => {
    
    expect(daysBetween(new Date(2026, 2, 1), new Date(2026, 3, 1))).toBe(31);
  });
});

describe('cycleDayFor', () => {
  it('is day 1 on the period start date', () => {
    expect(cycleDayFor(new Date(2026, 4, 1), '2026-05-01')).toBe(1);
  });

  it('counts inclusively from the start', () => {
    expect(cycleDayFor(new Date(2026, 4, 15), '2026-05-01')).toBe(15);
  });

  it('falls back to the day of the month with no last period', () => {
    expect(cycleDayFor(new Date(2026, 4, 17), null)).toBe(17);
    expect(cycleDayFor(new Date(2026, 4, 17))).toBe(17);
  });

  it('falls back rather than returning a non-positive day for an earlier date', () => {
    expect(cycleDayFor(new Date(2026, 3, 20), '2026-05-01')).toBe(20);
  });
});

describe('phaseFor', () => {
  
  it.each([
    ['2026-05-01', 'period'],
    ['2026-05-05', 'period'],
    ['2026-05-06', 'follicular'],
    ['2026-05-12', 'follicular'],
    ['2026-05-13', 'ovulation'],
    ['2026-05-14', 'ovulation'],
    ['2026-05-15', 'ovulation'],
    ['2026-05-16', 'luteal'],
    ['2026-05-28', 'luteal'],
  ])('maps %s to %s on a 28-day cycle', (iso, expected) => {
    expect(phaseFor(parseISODate(iso), '2026-05-01')).toBe(expected);
  });

  it('has a colour for every phase', () => {
    for (const phase of ['period', 'follicular', 'ovulation', 'luteal', 'late'] as const) {
      expect(PHASE_COLORS[phase]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('says a cycle is running long instead of reporting luteal forever', () => {
    
    expect(phaseFor(parseISODate('2026-07-15'), '2026-05-01')).toBe('late');
  });

  it('moves ovulation later on a longer cycle', () => {
    
    expect(phaseFor(parseISODate('2026-05-21'), '2026-05-01', 35)).toBe('ovulation');
    expect(phaseFor(parseISODate('2026-05-14'), '2026-05-01', 35)).toBe('follicular');
  });

  it('shortens the luteal phase rather than ovulating on day 7', () => {
    
    expect(lutealLengthFor(21)).toBe(10);
    expect(phaseFor(parseISODate('2026-05-11'), '2026-05-01', 21)).toBe('ovulation');
  });

  it('respects a bleed longer than the default five days', () => {
    expect(phaseFor(parseISODate('2026-05-07'), '2026-05-01', 28, 7)).toBe('period');
  });

  it('falls back to a 28-day cycle when the length is unusable', () => {
    expect(phaseFor(parseISODate('2026-05-14'), '2026-05-01', 0)).toBe('ovulation');
  });
});

describe('month windows', () => {
  it('finds the last day of a 31-day month', () => {
    expect(toISODate(endOfMonth(parseISODate('2026-01-10')))).toBe('2026-01-31');
  });

  it('finds the last day of a 30-day month', () => {
    expect(toISODate(endOfMonth(parseISODate('2026-04-10')))).toBe('2026-04-30');
  });

  it('gets February right in a leap year', () => {
    
    expect(toISODate(endOfMonth(parseISODate('2028-02-10')))).toBe('2028-02-29');
    expect(toISODate(endOfMonth(parseISODate('2026-02-10')))).toBe('2026-02-28');
  });

  it('rolls addDays across a month boundary', () => {
    expect(toISODate(addDays(parseISODate('2026-01-31'), 1))).toBe('2026-02-01');
    expect(toISODate(addDays(parseISODate('2026-03-01'), -1))).toBe('2026-02-28');
  });

  it('rolls addDays across a year boundary', () => {
    expect(toISODate(addDays(parseISODate('2026-12-31'), 1))).toBe('2027-01-01');
  });

  it('brackets the month with margin on both sides', () => {
    const { start, end } = monthWindow(parseISODate('2026-05-14'), 7);

    expect(start).toBe('2026-04-24');
    expect(end).toBe('2026-06-07');
  });

  it('always contains the whole month it was asked for', () => {
    for (let month = 0; month < 12; month++) {
      const { start, end } = monthWindow(new Date(2026, month, 1));
      expect(start <= toISODate(new Date(2026, month, 1))).toBe(true);
      expect(end >= toISODate(endOfMonth(new Date(2026, month, 1)))).toBe(true);
    }
  });

  it('stays inside a single server page', () => {
    
    const { start, end } = monthWindow(parseISODate('2026-01-15'));
    expect(daysBetween(parseISODate(start), parseISODate(end))).toBeLessThan(100);
  });
});
