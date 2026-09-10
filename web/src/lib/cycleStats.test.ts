import { describe, expect, it } from 'vitest';
import { cycleSpread, formatSpread, meanOf, type CycleSpread } from './cycleStats';

describe('meanOf', () => {
  it('averages the values', () => {
    expect(meanOf([26, 30])).toBe(28);
  });

  it('does not round', () => {
    
    expect(meanOf([28, 29])).toBe(28.5);
  });

  it('returns null for an empty list', () => {
    expect(meanOf([])).toBeNull();
  });

  it('ignores unusable entries', () => {
    expect(meanOf([28, Number.NaN, 30])).toBe(29);
  });
});

describe('cycleSpread', () => {
  it('reports the spread in days, not days squared', () => {
    
    expect(cycleSpread([26, 30])).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 2,
      sampleSize: 2,
    });
  });

  it('does not grow quadratically as the real spread widens', () => {
    
    expect(cycleSpread([23, 33])?.spreadDays).toBe(5);
  });

  it('measures against this user\'s own mean, not a population default', () => {
    
    const spread = cycleSpread([34, 35, 36]);
    expect(spread?.meanDays).toBe(35);
    expect(spread?.spreadDays).toBeCloseTo(0.7, 5);
  });

  it('reports zero spread for perfectly regular cycles', () => {
    
    expect(cycleSpread([28, 28, 28])).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 0,
      sampleSize: 3,
    });
  });

  it('rounds both figures to one decimal place', () => {
    const spread = cycleSpread([27, 28, 30]);
    expect(spread?.meanDays).toBe(28.3);
    expect(spread?.spreadDays).toBe(1.1);
  });

  it('returns null for a single cycle', () => {
    
    expect(cycleSpread([35])).toBeNull();
  });

  it('returns null for no cycles', () => {
    expect(cycleSpread([])).toBeNull();
  });

  it('survives a null or NaN in the array', () => {
    
    const withHoles = [26, Number.NaN, 30, null as unknown as number, undefined as unknown as number];
    expect(cycleSpread(withHoles)).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 2,
      sampleSize: 2,
    });
  });

  it('returns null when the holes leave fewer than two usable cycles', () => {
    expect(cycleSpread([Number.NaN, 28])).toBeNull();
  });

  it('ignores non-positive lengths', () => {
    
    expect(cycleSpread([0, 28, 30, -5])?.sampleSize).toBe(2);
  });

  it('does not mutate its input', () => {
    const lengths = [30, 26, 28];
    cycleSpread(lengths);
    expect(lengths).toEqual([30, 26, 28]);
  });

  it('is order-independent', () => {
    expect(cycleSpread([26, 30, 28])).toEqual(cycleSpread([30, 28, 26]));
  });

  it('handles a long history without drift', () => {
    const lengths = Array.from({ length: 24 }, (_, i) => (i % 2 === 0 ? 27 : 29));
    expect(cycleSpread(lengths)).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 1,
      sampleSize: 24,
    });
  });
});

describe('formatSpread', () => {
  it('prefixes the figure with a plus-minus sign', () => {
    expect(formatSpread(cycleSpread([26, 30]))).toBe('±2');
  });

  it('keeps a fractional day', () => {
    expect(formatSpread(cycleSpread([27, 28, 30]))).toBe('±1.1');
  });

  it('formats a zero spread rather than treating it as absent', () => {
    expect(formatSpread(cycleSpread([28, 28]))).toBe('±0');
  });

  it('returns null when there is nothing to report', () => {
    expect(formatSpread(null)).toBeNull();
  });

  it('leaves the unit to the caller', () => {
    
    expect(formatSpread(cycleSpread([26, 30]))).not.toContain('day');
  });
});
