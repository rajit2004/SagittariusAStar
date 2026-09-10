
export interface CycleSpread {
  
  meanDays: number;
  
  spreadDays: number;
  
  sampleSize: number;
}

export function meanOf(values: readonly number[]): number | null {
  const usable = usableLengths(values);
  if (usable.length === 0) return null;
  return usable.reduce((total, value) => total + value, 0) / usable.length;
}

function usableLengths(values: readonly number[]): number[] {
  return values.filter(
    (value) => typeof value === 'number' && Number.isFinite(value) && value > 0,
  );
}

function roundTo1(value: number): number {
  return Math.round(value * 10) / 10;
}

export function cycleSpread(lengths: readonly number[]): CycleSpread | null {
  const usable = usableLengths(lengths);
  if (usable.length < 2) return null;

  const mean = usable.reduce((total, value) => total + value, 0) / usable.length;
  const meanAbsoluteDeviation =
    usable.reduce((total, value) => total + Math.abs(value - mean), 0) / usable.length;

  return {
    meanDays: roundTo1(mean),
    spreadDays: roundTo1(meanAbsoluteDeviation),
    sampleSize: usable.length,
  };
}

export function formatSpread(spread: CycleSpread | null): string | null {
  if (spread === null) return null;
  return `±${spread.spreadDays}`;
}
