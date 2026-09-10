
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

export const DEFAULT_TIMEOUT_MS = 10_000;

export const LONG_TIMEOUT_MS = 45_000;
export const LONG_TIMEOUT_PATHS = ['/assistant/chat'];

export const MAX_RETRY_ATTEMPTS = 3;
export const BASE_BACKOFF_MS = 300;
export const MAX_BACKOFF_MS = 5_000;

const RETRYABLE_STATUSES = new Set([429, 502, 503, 504]);

const RETRYABLE_METHODS = new Set(['get', 'head', 'options']);

export interface RetryableConfig extends InternalAxiosRequestConfig {
  
  retryCount?: number;
}

export function isRetryableMethod(method: string | undefined): boolean {
  return RETRYABLE_METHODS.has((method ?? 'get').toLowerCase());
}

export function isNetworkError(error: AxiosError): boolean {
  if (error.response) return false;
  
  return error.code !== 'ERR_CANCELED';
}

export function shouldRetry(error: AxiosError, attempt: number): boolean {
  if (attempt >= MAX_RETRY_ATTEMPTS) return false;
  if (!isRetryableMethod(error.config?.method)) return false;

  const status = error.response?.status;
  if (status === undefined) return isNetworkError(error);
  return RETRYABLE_STATUSES.has(status);
}

export function parseRetryAfter(
  value: string | undefined | null,
  now: number = Date.now(),
): number | null {
  if (!value) return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  if (/^\d+$/.test(trimmed)) {
    return Number(trimmed) * 1000;
  }

  const timestamp = Date.parse(trimmed);
  if (Number.isNaN(timestamp)) return null;

  return Math.max(0, timestamp - now);
}

export function backoffDelay(
  attempt: number,
  retryAfterMs: number | null = null,
  random: () => number = Math.random,
): number {
  if (retryAfterMs !== null) {
    return Math.min(retryAfterMs, MAX_BACKOFF_MS * 4);
  }
  const ceiling = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
  return Math.round(random() * ceiling);
}

export function timeoutFor(url: string | undefined, defaultMs: number): number {
  if (!url) return defaultMs;
  return LONG_TIMEOUT_PATHS.some((path) => url.includes(path))
    ? LONG_TIMEOUT_MS
    : defaultMs;
}

export function isOffline(): boolean {
  
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
