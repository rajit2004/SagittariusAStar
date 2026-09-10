import { apiClient } from './client';

export interface DashboardCycle {
  day: number | null;
  total: number;
  nextPeriodDays: number | null;
}

export interface DashboardInsights {
  averageCycleLength: number | null;
  shortestCycleLength: number | null;
  longestCycleLength: number | null;
  averageBleedingDuration: number | null;
  sleepHours: string | null;
}

export interface CycleHistoryPoint {
  start_date: string;
  cycle_length: number;
}

export interface SymptomFrequency {
  cramps: number;
  headache: number;
  bloating: number;
  acne: number;
}

export type EstimateSource = 'logged_history' | 'declared_cycle_length' | 'population_default';

export type PredictionConfidence = 'high' | 'medium' | 'low';

export type CyclePhase =
  | 'period'
  | 'follicular'
  | 'ovulation'
  | 'luteal'
  | 'late'
  | 'unknown';

export interface PredictedRange {
  earliest: string | null;
  latest: string | null;
}

export interface FertileWindow {
  start: string | null;
  end: string | null;
  isEstimate: boolean;
  notForContraception: boolean;
}

export interface DashboardPrediction {
  nextPeriodDate: string | null;
  daysUntilNextPeriod: number | null;
  isOverdue: boolean;
  daysOverdue: number;
  phase: CyclePhase;
  confidence: PredictionConfidence;
  estimateSource: EstimateSource;
  predictedRange: PredictedRange;
  fertileWindow: FertileWindow;
}

export interface CycleLengthEstimate {
  days: number;
  source: EstimateSource;
  confidence: PredictionConfidence;
  sampleSize: number;
  spreadDays: number;
  excludedCycleLengths: number[];
}

export interface PredictionResponse {
  today: string;
  cycleLength: CycleLengthEstimate;
  lastPeriodStart: string | null;
  currentCycleDay: number | null;
  phase: CyclePhase;
  nextPeriodDate: string | null;
  daysUntilNextPeriod: number | null;
  isOverdue: boolean;
  daysOverdue: number;
  predictedRange: PredictedRange;
  ovulation: { date: string | null; isEstimate: boolean };
  fertileWindow: FertileWindow;
  upcomingPeriods: string[];
  confidence: PredictionConfidence;
  disclaimer: string;
}

export interface DashboardData {
  user: { name: string };
  cycle: DashboardCycle;
  insights: DashboardInsights;
  hasEnoughDataForInsights: boolean;
  loggedCycleCount: number;
  cycleHistory: CycleHistoryPoint[];
  symptomFrequency: SymptomFrequency | Record<string, never>;
  recentStressLevel: number | null;
  
  prediction?: DashboardPrediction | null;
}

export async function fetchDashboard(): Promise<DashboardData> {
  const response = await apiClient.get<DashboardData>('/dashboard');
  return response.data;
}

export async function fetchPredictions(horizon?: number): Promise<PredictionResponse> {
  const response = await apiClient.get<PredictionResponse>('/cycle/predictions', {
    params: horizon ? { horizon } : undefined,
  });
  return response.data;
}

export type ObservationSeverity = 'info' | 'attention' | 'seek_care';

export interface Observation {
  code: string;
  severity: ObservationSeverity;
  title: string;
  body: string;
  titleKey: string;
  bodyKey: string;
  evidence: Record<string, unknown>;
  isMedicalAdvice: boolean;
  disclaimerKey: string;
}

export type CycleConsistency = 'unknown' | 'consistent' | 'slightly_variable' | 'variable';

export interface ObservationsResponse {
  observations: Observation[];
  topObservation: Observation | null;
  cycleConsistency: CycleConsistency;
  averageCycleLength: number | null;
  analyzedCycleCount: number;
  disclaimer: string;
  disclaimerKey: string;
}

export async function fetchObservations(userId: string): Promise<ObservationsResponse> {
  const response = await apiClient.get<ObservationsResponse>(`/insights/${userId}/observations`);
  return response.data;
}

export interface CycleLogInput {
  start_date: string;
  end_date?: string | null;
  flow_intensity?: string | null;
  mood?: string | null;
  symptoms?: string[] | null;
  sleep_hours?: number | null;
  stress_level?: number | null;
  notes?: string | null;
}

export interface CycleLogEntry extends CycleLogInput {
  id: string;
}

export interface CycleHistoryPageInfo {
  limit: number;
  offset: number;
  count: number;
  hasMore: boolean;
  nextOffset: number | null;
}

export interface CycleHistory {
  message: string;
  entries: CycleLogEntry[];
  page: CycleHistoryPageInfo;
}

export const MAX_HISTORY_PAGE = 100;

const MAX_PAGES_FOLLOWED = 10;

export async function submitCycleLog(log: CycleLogInput) {
  const response = await apiClient.post<{ id: string; message: string; data: CycleLogInput }>(
    '/cycle/log',
    log,
  );
  return response.data;
}

export interface CycleHistoryQuery {
  limit?: number;
  offset?: number;
  
  startDate?: string;
  
  endDate?: string;
}

export async function fetchCycleHistoryPage(
  userId: string,
  query: CycleHistoryQuery = {},
): Promise<CycleHistory> {
  const params: Record<string, string | number> = {
    limit: Math.min(Math.max(query.limit ?? 20, 1), MAX_HISTORY_PAGE),
  };
  if (query.offset) params.offset = query.offset;
  if (query.startDate) params.start_date = query.startDate;
  if (query.endDate) params.end_date = query.endDate;

  const response = await apiClient.get<CycleHistory>(`/cycle/${userId}/history`, { params });
  return response.data;
}

export async function fetchCycleHistoryRange(
  userId: string,
  startDate: string,
  endDate: string,
): Promise<CycleLogEntry[]> {
  const entries: CycleLogEntry[] = [];
  let offset = 0;

  for (let page = 0; page < MAX_PAGES_FOLLOWED; page++) {
    const result = await fetchCycleHistoryPage(userId, {
      limit: MAX_HISTORY_PAGE,
      offset,
      startDate,
      endDate,
    });
    entries.push(...result.entries);

    const next = result.page?.nextOffset;
    if (!result.page?.hasMore || next == null || next <= offset) break;
    offset = next;
  }

  return entries;
}

export async function fetchCycleHistory(userId: string, limit = 90): Promise<CycleLogEntry[]> {
  const result = await fetchCycleHistoryPage(userId, { limit });
  return result.entries;
}

export async function deleteCycleLog(logId: string) {
  await apiClient.delete(`/cycle/${logId}`);
}

export interface ChatMessage {
  role: 'user' | 'model';
  content: string;
}

export interface ChatResult {
  response: string;
  language: string;
  disclaimer: string;
}

export interface SupportedLanguage {
  code: string;
  name: string;
}

export async function sendChatMessage(
  message: string,
  language: string,
  history: ChatMessage[],
): Promise<ChatResult> {
  const response = await apiClient.post<ChatResult>('/assistant/chat', {
    message,
    language,
    history,
  });
  return response.data;
}

export async function fetchSupportedLanguages(): Promise<SupportedLanguage[]> {
  const response = await apiClient.get<SupportedLanguage[]>('/assistant/languages');
  return response.data;
}

export interface SmsSettings {
  phoneNumber: string;
  enabled: boolean;
}

export async function fetchSmsSettings(): Promise<SmsSettings> {
  try {
    const response = await apiClient.get<SmsSettings>('/sms/settings');
    return response.data;
  } catch (error) {
    
    if (error && typeof error === 'object' && 'response' in error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status === 404) return { phoneNumber: '', enabled: false };
    }
    throw error;
  }
}

export async function saveSmsSettings(settings: SmsSettings): Promise<SmsSettings> {
  const response = await apiClient.post<SmsSettings>('/sms/settings', settings);
  return response.data;
}

export async function sendSmsSummary(phone_number: string, message: string) {
  const response = await apiClient.post<{ message: string; sid: string }>('/sms/send-summary', {
    phone_number,
    message,
  });
  return response.data;
}

export interface Profile {
  id?: string;
  phone?: string | null;
  username?: string | null;
  email?: string | null;
  full_name?: string | null;
  age?: number | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  avatar?: string | null;
  language?: string | null;
  last_period?: string | null;
  last_period_is_approximate?: boolean | null;
  cycle_length?: number | null;
  period_duration?: number | null;
  cycle_regular?: boolean | null;
  notifications_enabled?: boolean | null;
  city?: string | null;
  state?: string | null;
}

export type ProfileUpdate = Partial<Pick<
  Profile,
  | 'full_name'
  | 'age'
  | 'height_cm'
  | 'weight_kg'
  | 'avatar'
  | 'language'
  | 'last_period'
  | 'last_period_is_approximate'
  | 'cycle_length'
  | 'period_duration'
  | 'cycle_regular'
  | 'notifications_enabled'
  | 'phone'
  | 'city'
  | 'state'
>>;

export async function fetchProfile(): Promise<Profile> {
  const response = await apiClient.get<Profile>('/auth/profile');
  return response.data;
}

export async function patchProfile(updates: ProfileUpdate): Promise<Profile> {
  const response = await apiClient.patch<Profile>('/auth/profile', updates);
  return response.data;
}

export async function deleteAccount() {
  await apiClient.delete('/auth/me');
}

export interface DataCategory {
  key: string;
  label: string;
  recordCount: number;
  storedFields: string[];
  collection: string;
  earliestEntry?: string | null;
  latestEntry?: string | null;
  retentionNote: string;
}

export interface DataSummary {
  userId: string;
  generatedAt: string;
  categories: DataCategory[];
  totalRecords: number;
}

export interface DeletionPreview {
  confirmationToken: string;
  expiresInSeconds: number;
  impact: DataSummary;
  warning: string;
}

export interface DeletionResult {
  status: string;
  deletedCounts: Record<string, number>;
  totalDeleted: number;
  deletedAt: string;
  message: string;
}

export type ExportFormat = 'json' | 'csv';

export interface ExportFile {
  blob: Blob;
  filename: string;
}

export async function fetchDataSummary(): Promise<DataSummary> {
  const response = await apiClient.get<DataSummary>('/privacy/summary');
  return response.data;
}

export function exportFilename(disposition: unknown, format: ExportFormat): string {
  if (typeof disposition === 'string') {
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
    if (match?.[1]) return decodeURIComponent(match[1].trim());
  }
  return `rhythma-data-export.${format}`;
}

/**
 * The export as a blob, with the name to save it under.
 *
 * Returned rather than downloaded here so the calling component decides
 * when to touch the DOM — and so this is testable without stubbing
 * `URL.createObjectURL`.
 */
export async function fetchDataExport(format: ExportFormat = 'json'): Promise<ExportFile> {
  const response = await apiClient.get('/privacy/export', {
    params: { format },
    responseType: 'blob',
  });

  const headers = response.headers as unknown as Record<string, unknown>;
  return {
    blob: response.data as Blob,
    filename: exportFilename(headers?.['content-disposition'], format),
  };
}

/**
 * Ask what deleting would destroy. Does not delete anything.
 *
 * The server answers 202 with a short-lived single-use token; nothing is
 * removed until that token comes back through `confirmAccountDeletion`.
 */
export async function requestAccountDeletion(): Promise<DeletionPreview> {
  const response = await apiClient.post<DeletionPreview>('/privacy/delete-account', {});
  return response.data;
}

/** Irreversible. Only reachable with a token from the call above. */
export async function confirmAccountDeletion(
  confirmationToken: string,
): Promise<DeletionResult> {
  const response = await apiClient.post<DeletionResult>('/privacy/delete-account', {
    confirmationToken,
  });
  return response.data;
}

// ─── Provider Dashboard & Data Sharing (issue #267) ────────────────────────

export interface Consent {
  id: string;
  patient_id: string;
  provider_id: string;
  provider_email: string;
  provider_name: string;
  status: 'active' | 'revoked';
  created_at?: string | null;
  updated_at?: string | null;
  revoked_at?: string | null;
  /**
   * How many times this provider has opened the patient's data, and when
   * she last did (issue #350). Folded into the consent list by the
   * backend so the sharing screen needs no second request.
   *
   * Optional so the page keeps rendering against a backend that predates
   * the field, rather than showing "0 views" — which would be a claim,
   * not a gap.
   */
  viewCount?: number;
  lastAccessedAt?: string | null;
}

/** One recorded read of the patient's data by a provider (issue #350). */
export interface AccessLogEntry {
  id: string;
  providerId: string;
  providerName: string | null;
  /** `patient_list` (dashboard card) or `patient_detail` (full record). */
  view: 'patient_list' | 'patient_detail';
  consentId: string | null;
  accessedAt: string | null;
}

/**
 * Where a page of access history sits. Mirrors the `page` object the
 * cycle-history endpoint returns (#331); declared separately rather than
 * shared so the two can diverge without one silently changing the other.
 */
/**
 * The paging envelope every list endpoint returns.
 *
 * Named generically because four endpoints now share it — cycle history,
 * the access log, and (as of #406) the provider patient and consent lists.
 * `AccessLogPageInfo` remains as an alias so nothing that imports it has
 * to change.
 */
export interface PageInfo {
  limit: number;
  offset: number;
  count: number;
  hasMore: boolean;
  nextOffset: number | null;
}

export type AccessLogPageInfo = PageInfo;

export interface AccessLogPage {
  entries: AccessLogEntry[];
  page: PageInfo;
}

export interface ProviderPatientSummary {
  patient_id: string;
  name: string;
  age?: number | null;
  city?: string | null;
  state?: string | null;
  sharedSince?: string | null;
  loggedCycleCount: number;
  mhs?: number | null;
  cvi?: string | null;
  hasEnoughDataForInsights: boolean;
}

export interface ProviderPatientDetail {
  patient: {
    id: string;
    name: string;
    age?: number | null;
    city?: string | null;
    state?: string | null;
    cycle_length?: number | null;
    period_duration?: number | null;
    cycle_regular?: boolean | null;
    last_period?: string | null;
  };
  summary: {
    mhs?: number | null;
    cvi?: string | null;
    cvi_raw?: number | null;
    loggedCycleCount: number;
    hasEnoughDataForInsights: boolean;
    avgSleepHours?: number | null;
  };
  cycleLogs: Array<{
    id: string;
    start_date?: string | null;
    end_date?: string | null;
    flow_intensity?: string | null;
    mood?: string | null;
    symptoms?: string[] | null;
    sleep_hours?: number | null;
    stress_level?: number | null;
    notes?: string | null;
  }>;
  consent: { grantedAt?: string | null; status: string };
}

export interface ProviderProfile {
  id: string;
  email: string;
  username?: string | null;
  full_name?: string | null;
  specialty?: string | null;
  license_number?: string | null;
  role: string;
}

export async function grantConsent(providerEmail: string): Promise<Consent> {
  const response = await apiClient.post<Consent>('/provider/consents', {
    provider_email: providerEmail,
  });
  return response.data;
}

export interface ConsentPage {
  consents: Consent[];
  page: PageInfo;
}

/**
 * One page of the patient's consents, newest first.
 *
 * The server bounds `limit` at 100 and defaults to 20 (#406). Asking for a
 * page explicitly rather than relying on that default is what stops #349
 * happening again — there, the client assumed a limit the server did not
 * agree with, and the calendar silently rendered empty.
 */
export async function fetchConsentPage(limit = 20, offset = 0): Promise<ConsentPage> {
  const response = await apiClient.get<ConsentPage>('/provider/consents', {
    params: { limit, offset },
  });
  return response.data;
}

/**
 * Every consent, by following the pages.
 *
 * The Sharing screen shows a patient the complete list of who can see her
 * data — a truncated answer to that question is a wrong answer, so this
 * walks to the end rather than showing the first page. The walk is bounded
 * so a server that always reports `hasMore` cannot spin here forever.
 */
export async function fetchConsents(): Promise<Consent[]> {
  const PAGE_SIZE = 100;
  const MAX_PAGES = 50;

  const all: Consent[] = [];
  let offset = 0;

  for (let pages = 0; pages < MAX_PAGES; pages += 1) {
    const page = await fetchConsentPage(PAGE_SIZE, offset);
    all.push(...page.consents);
    if (!page.page?.hasMore || page.page.nextOffset === null) break;
    offset = page.page.nextOffset;
  }

  return all;
}

export async function revokeConsent(consentId: string): Promise<Consent> {
  const response = await apiClient.delete<Consent>(`/provider/consents/${consentId}`);
  return response.data;
}

export async function fetchProviderProfile(): Promise<ProviderProfile> {
  const response = await apiClient.get<ProviderProfile>('/provider/me');
  return response.data;
}

export interface ProviderPatientPage {
  patients: ProviderPatientSummary[];
  page: PageInfo;
}

/**
 * One page of the provider's consented patients, newest share first.
 *
 * Paged on the server since #406, and paged here rather than walked to the
 * end on purpose: unlike the consent list, each row costs the backend a
 * profile read, a scoring pass and an access-log write, so fetching every
 * page would put the cost this endpoint was bounded to avoid straight back.
 * The dashboard shows a page and offers "load more".
 */
export async function fetchProviderPatientPage(
  limit = 20,
  offset = 0,
): Promise<ProviderPatientPage> {
  const response = await apiClient.get<ProviderPatientPage>('/provider/patients', {
    params: { limit, offset },
  });
  return response.data;
}

export async function fetchProviderPatients(): Promise<ProviderPatientSummary[]> {
  const page = await fetchProviderPatientPage();
  return page.patients;
}

/**
 * The patient's own record of who has viewed her data, newest first.
 *
 * Patient-only on the server: a provider cannot read this, because her
 * side of the relationship is the thing being recorded.
 */
export async function fetchAccessLog(limit = 20, offset = 0): Promise<AccessLogPage> {
  const response = await apiClient.get<AccessLogPage>('/provider/access-log', {
    params: { limit, offset },
  });
  return response.data;
}

export async function fetchProviderPatientDetail(
  patientId: string,
): Promise<ProviderPatientDetail> {
  const response = await apiClient.get<ProviderPatientDetail>(
    `/provider/patients/${patientId}`,
  );
  return response.data;
}
