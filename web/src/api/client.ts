
import axios, { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

import {
  DEFAULT_TIMEOUT_MS,
  backoffDelay,
  isOffline,
  parseRetryAfter,
  shouldRetry,
  sleep,
  timeoutFor,
  type RetryableConfig,
} from './retry';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS;

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, 
  headers: { 'X-Client-Platform': 'web' }, 
  timeout: TIMEOUT_MS,
});

const REQUEST_ID_HEADER = 'x-request-id';
let lastRequestId: string | null = null;

export function getLastRequestId(): string | null {
  return lastRequestId;
}

function recordRequestId(headers: unknown) {
  if (!headers || typeof headers !== 'object') return;
  const value = (headers as Record<string, unknown>)[REQUEST_ID_HEADER];
  if (typeof value === 'string' && value) lastRequestId = value;
}

const PUBLIC_ENDPOINTS = new Set([
  '/auth/login',
  '/auth/register',
  '/auth/firebase-login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/password-requirements',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/assistant/languages',
  '/health',
]);

function isPublicEndpoint(path: string): boolean {
  for (const publicPath of PUBLIC_ENDPOINTS) {
    if (path === publicPath || path.endsWith(publicPath)) return true;
  }
  return false;
}

let refreshPromise: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      
      await axios.post(`${BASE_URL}/auth/refresh`, {}, { withCredentials: true });
      
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

apiClient.interceptors.request.use(
  (config) => {
    
    config.timeout = timeoutFor(config.url, TIMEOUT_MS);
    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response) => {
    recordRequestId(response.headers);
    return response;
  },
  async (error: AxiosError) => {
    recordRequestId(error.response?.headers);

    const status = error.response?.status;
    const config = error.config as RetryableConfig | undefined;
    const url = config?.url ?? '';

    if (status !== 401) {
      if (config && shouldRetry(error, config.retryCount ?? 0)) {
        
        if (isOffline()) {
          return Promise.reject(error);
        }

        const attempt = config.retryCount ?? 0;
        const retryAfter = parseRetryAfter(
          error.response?.headers?.['retry-after'] as string | undefined,
        );

        await sleep(backoffDelay(attempt, retryAfter));

        config.retryCount = attempt + 1;
        return apiClient.request(config);
      }

      return Promise.reject(error);
    }

    if (isPublicEndpoint(url)) {
      onUnauthorized?.();
      return Promise.reject(error);
    }

    if (config?.headers?.['X-Retry-After-Refresh'] === '1') {
      onUnauthorized?.();
      return Promise.reject(error);
    }

    const refreshed = await performRefresh();

    if (!refreshed) {
      
      onUnauthorized?.();
      return Promise.reject(error);
    }

    const headers = AxiosHeaders.from(config?.headers);
    headers.set('X-Retry-After-Refresh', '1');

    const retryConfig = {
      ...config,
      headers,
    } as InternalAxiosRequestConfig;

    return apiClient.request(retryConfig);
  },
);

export function friendlyAuthError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      code?: string;
      response?: { status?: number; data?: { detail?: string } };
    };
    if (!axiosErr.response) {
      
      if (axiosErr.code === 'ECONNABORTED' || axiosErr.code === 'ETIMEDOUT') {
        return 'The server took too long to respond. Please try again.';
      }
      if (isOffline()) {
        return "You appear to be offline. Check your connection and try again.";
      }
      return "Couldn't reach the server. Check your connection, that the backend is running, and that this origin is allowed by its CORS settings.";
    }
    const status = axiosErr.response.status;
    if (status === 401) return 'Invalid username or password.';
    if (status === 429) {
      return (
        axiosErr.response.data?.detail ||
        'Too many attempts. Please wait a few minutes and try again.'
      );
    }
    if (axiosErr.response.data?.detail) return axiosErr.response.data.detail;
  }
  return fallback;
}

export function friendlyApiError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      code?: string;
      response?: { status?: number; data?: { detail?: string } };
    };

    if (!axiosErr.response) {
      if (axiosErr.code === 'ECONNABORTED' || axiosErr.code === 'ETIMEDOUT') {
        return 'The server took too long to respond. Please try again.';
      }
      if (isOffline()) {
        return "You appear to be offline. Check your connection and try again.";
      }
      return "Couldn't reach the server. Please check your connection and try again.";
    }

    const status = axiosErr.response.status;
    if (status === 401) return 'Your session has expired. Please sign in again.';
    if (status === 503 || status === 502 || status === 504) {
      return 'The service is temporarily unavailable. Please try again in a moment.';
    }
    
    const detail = axiosErr.response.data?.detail;
    if (typeof detail === 'string' && detail) return detail;
  }
  return fallback;
}
