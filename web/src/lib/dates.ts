
export function toISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function parseISODate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

export function endOfMonth(date: Date): Date {
  
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

export function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function monthWindow(month: Date, marginDays = 7): { start: string; end: string } {
  return {
    start: toISODate(addDays(startOfMonth(month), -marginDays)),
    end: toISODate(addDays(endOfMonth(month), marginDays)),
  };
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function daysBetween(a: Date, b: Date): number {
  const ms = new Date(b.getFullYear(), b.getMonth(), b.getDate()).getTime() -
    new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  return Math.round(ms / 86400000);
}

export function cycleDayFor(date: Date, lastPeriodIso?: string | null): number {
  if (lastPeriodIso) {
    const day = daysBetween(parseISODate(lastPeriodIso), date) + 1;
    if (day >= 1) return day;
  }
  
  return date.getDate();
}

export type CyclePhase = 'period' | 'follicular' | 'ovulation' | 'luteal' | 'late';

export const DEFAULT_CYCLE_LENGTH = 28;

const DEFAULT_PERIOD_DAYS = 5;
const DEFAULT_LUTEAL_DAYS = 14;
const MIN_LUTEAL_DAYS = 10;
const SHORT_CYCLE_LUTEAL_THRESHOLD = 25;

export function lutealLengthFor(cycleLength: number): number {
  if (cycleLength >= SHORT_CYCLE_LUTEAL_THRESHOLD) return DEFAULT_LUTEAL_DAYS;
  return Math.max(MIN_LUTEAL_DAYS, cycleLength - 11);
}

export function phaseFor(
  date: Date,
  lastPeriodIso?: string | null,
  cycleLength: number = DEFAULT_CYCLE_LENGTH,
  periodDays: number = DEFAULT_PERIOD_DAYS,
): CyclePhase {
  const day = cycleDayFor(date, lastPeriodIso);
  const length = cycleLength > 0 ? cycleLength : DEFAULT_CYCLE_LENGTH;
  const ovulationDay = length - lutealLengthFor(length);

  if (day <= periodDays) return 'period';
  if (day < ovulationDay - 1) return 'follicular';
  if (day <= ovulationDay + 1) return 'ovulation';
  if (day <= length) return 'luteal';
  return 'late';
}

export const PHASE_COLORS: Record<CyclePhase, string> = {
  period: '#E07AAD',
  follicular: '#AA3BFF',
  ovulation: '#52B3B0',
  luteal: '#E8946A',
  
  late: '#8E8E93',
};

export function formatMonthYear(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

export function formatDayMonth(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
