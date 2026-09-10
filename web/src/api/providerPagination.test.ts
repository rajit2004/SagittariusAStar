import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  setUnauthorizedHandler: vi.fn(),
  friendlyAuthError: vi.fn(),
}));

import { apiClient } from './client';
import {
  fetchConsentPage,
  fetchConsents,
  fetchProviderPatientPage,
  fetchProviderPatients,
  type Consent,
  type PageInfo,
  type ProviderPatientSummary,
} from './endpoints';

const mockClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

function page(overrides: Partial<PageInfo> = {}): PageInfo {
  return {
    limit: 20,
    offset: 0,
    count: 0,
    hasMore: false,
    nextOffset: null,
    ...overrides,
  };
}

function consent(id: string): Consent {
  return {
    id,
    provider_id: `prov-${id}`,
    provider_email: `${id}@clinic.test`,
    status: 'active',
  } as Consent;
}

function patient(id: string): ProviderPatientSummary {
  return {
    patient_id: id,
    name: `Patient ${id}`,
    loggedCycleCount: 0,
    hasEnoughDataForInsights: false,
  } as ProviderPatientSummary;
}

describe('fetchProviderPatientPage', () => {
  it('sends limit and offset as query parameters', async () => {
    mockClient.get.mockResolvedValue({
      data: { patients: [], page: page() },
    });

    await fetchProviderPatientPage(7, 14);

    expect(mockClient.get).toHaveBeenCalledWith('/provider/patients', {
      params: { limit: 7, offset: 14 },
    });
  });

  it('defaults to the server page size rather than leaving it unset', async () => {
    
    mockClient.get.mockResolvedValue({
      data: { patients: [], page: page() },
    });

    await fetchProviderPatientPage();

    expect(mockClient.get).toHaveBeenCalledWith('/provider/patients', {
      params: { limit: 20, offset: 0 },
    });
  });

  it('returns the envelope so a caller can page', async () => {
    mockClient.get.mockResolvedValue({
      data: {
        patients: [patient('a')],
        page: page({ count: 1, hasMore: true, nextOffset: 20 }),
      },
    });

    const result = await fetchProviderPatientPage();

    expect(result.patients).toHaveLength(1);
    expect(result.page.hasMore).toBe(true);
    expect(result.page.nextOffset).toBe(20);
  });
});

describe('fetchProviderPatients', () => {
  it('returns the first page only, and does not walk to the end', async () => {
    
    mockClient.get.mockResolvedValue({
      data: {
        patients: [patient('a')],
        page: page({ count: 1, hasMore: true, nextOffset: 20 }),
      },
    });

    const result = await fetchProviderPatients();

    expect(result).toHaveLength(1);
    expect(mockClient.get).toHaveBeenCalledTimes(1);
  });
});

describe('fetchConsentPage', () => {
  it('sends limit and offset as query parameters', async () => {
    mockClient.get.mockResolvedValue({
      data: { consents: [], page: page() },
    });

    await fetchConsentPage(5, 10);

    expect(mockClient.get).toHaveBeenCalledWith('/provider/consents', {
      params: { limit: 5, offset: 10 },
    });
  });
});

describe('fetchConsents', () => {
  it('follows every page', async () => {
    
    mockClient.get
      .mockResolvedValueOnce({
        data: {
          consents: [consent('a'), consent('b')],
          page: page({ limit: 100, count: 2, hasMore: true, nextOffset: 100 }),
        },
      })
      .mockResolvedValueOnce({
        data: {
          consents: [consent('c')],
          page: page({ limit: 100, offset: 100, count: 1 }),
        },
      });

    const result = await fetchConsents();

    expect(result.map((row) => row.id)).toEqual(['a', 'b', 'c']);
    expect(mockClient.get).toHaveBeenCalledTimes(2);
  });

  it('uses the offset the server reports, not one it computed', async () => {
    mockClient.get
      .mockResolvedValueOnce({
        data: {
          consents: [consent('a')],
          page: page({ limit: 100, count: 1, hasMore: true, nextOffset: 37 }),
        },
      })
      .mockResolvedValueOnce({
        data: { consents: [], page: page({ limit: 100, offset: 37 }) },
      });

    await fetchConsents();

    expect(mockClient.get).toHaveBeenNthCalledWith(2, '/provider/consents', {
      params: { limit: 100, offset: 37 },
    });
  });

  it('stops when hasMore is true but nextOffset is null', async () => {
    
    mockClient.get.mockResolvedValue({
      data: {
        consents: [consent('a')],
        page: page({ limit: 100, count: 1, hasMore: true, nextOffset: null }),
      },
    });

    const result = await fetchConsents();

    expect(result).toHaveLength(1);
    expect(mockClient.get).toHaveBeenCalledTimes(1);
  });

  it('stops at the page cap if the server always reports more', async () => {
    
    mockClient.get.mockResolvedValue({
      data: {
        consents: [consent('x')],
        page: page({ limit: 100, count: 1, hasMore: true, nextOffset: 100 }),
      },
    });

    const result = await fetchConsents();

    expect(mockClient.get).toHaveBeenCalledTimes(50);
    expect(result).toHaveLength(50);
  });

  it('survives a response with no page envelope at all', async () => {
    
    mockClient.get.mockResolvedValue({
      data: { consents: [consent('a')] },
    });

    const result = await fetchConsents();

    expect(result).toHaveLength(1);
    expect(mockClient.get).toHaveBeenCalledTimes(1);
  });
});
