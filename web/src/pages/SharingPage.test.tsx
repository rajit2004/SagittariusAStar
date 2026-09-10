import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';

vi.mock('../api/endpoints', () => ({
  fetchConsents: vi.fn(),
  fetchAccessLog: vi.fn(),
  grantConsent: vi.fn(),
  revokeConsent: vi.fn(),
}));

import { fetchAccessLog, fetchConsents } from '../api/endpoints';
import { SharingPage } from './SharingPage';
import { renderWithProviders } from '../test/utils';

const mockConsents = fetchConsents as unknown as ReturnType<typeof vi.fn>;
const mockAccessLog = fetchAccessLog as unknown as ReturnType<typeof vi.fn>;

function consentFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 'consent-1',
    patient_id: 'patient-1',
    provider_id: 'provider-1',
    provider_email: 'dr.rao@clinic.in',
    provider_name: 'Dr. Priya Rao',
    status: 'active' as const,
    created_at: '2026-03-12T09:00:00Z',
    viewCount: 0,
    lastAccessedAt: null,
    ...overrides,
  };
}

function accessEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'access-1',
    providerId: 'provider-1',
    providerName: 'Dr. Priya Rao',
    view: 'patient_detail' as const,
    consentId: 'consent-1',
    accessedAt: '2026-08-02T11:30:00Z',
    ...overrides,
  };
}

function emptyPage() {
  return {
    entries: [],
    page: { limit: 20, offset: 0, count: 0, hasMore: false, nextOffset: null },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockConsents.mockResolvedValue([]);
  mockAccessLog.mockResolvedValue(emptyPage());
});

describe('access history', () => {
  it('lists who opened the record and when', async () => {
    mockAccessLog.mockResolvedValue({
      ...emptyPage(),
      entries: [accessEntry()],
    });

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Opened your full record/i)).toBeInTheDocument();
  });

  it('distinguishes a summary card from the full record', async () => {
    mockAccessLog.mockResolvedValue({
      ...emptyPage(),
      entries: [accessEntry({ view: 'patient_list' })],
    });

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Saw your summary card/i)).toBeInTheDocument();
  });

  it('says so plainly when nobody has looked', async () => {
    renderWithProviders(<SharingPage />);

    expect(
      await screen.findByText(/No provider has viewed your data yet/i),
    ).toBeInTheDocument();
  });

  it('names a provider who has since closed their account', async () => {
    mockAccessLog.mockResolvedValue({
      ...emptyPage(),
      entries: [accessEntry({ providerName: null })],
    });

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/closed their account/i)).toBeInTheDocument();
  });
});

describe('consent rows carry usage', () => {
  it('shows a view count and a last-viewed date', async () => {
    mockConsents.mockResolvedValue([
      consentFixture({ viewCount: 4, lastAccessedAt: '2026-08-02T11:30:00Z' }),
    ]);

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Viewed 4 times/i)).toBeInTheDocument();
  });

  it('distinguishes "granted but never used" from silence', async () => {
    mockConsents.mockResolvedValue([consentFixture({ viewCount: 0 })]);

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Has not viewed your data yet/i)).toBeInTheDocument();
  });

  it('says nothing at all when the server omitted the field', async () => {
    
    const consent = consentFixture();
    delete (consent as Record<string, unknown>).viewCount;
    delete (consent as Record<string, unknown>).lastAccessedAt;
    mockConsents.mockResolvedValue([consent]);

    renderWithProviders(<SharingPage />);

    await screen.findByText('Dr. Priya Rao');
    expect(screen.queryByText(/Has not viewed your data yet/i)).toBeNull();
    
    expect(screen.queryByText(/Viewed \d+ times/i)).toBeNull();
  });

  it('keeps the history visible on a revoked consent', async () => {
    
    mockConsents.mockResolvedValue([
      consentFixture({ status: 'revoked', viewCount: 2 }),
    ]);

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Viewed 2 times/i)).toBeInTheDocument();
  });
});

describe('failure handling', () => {
  it('still shows consents when the access log cannot be loaded', async () => {
    
    mockConsents.mockResolvedValue([consentFixture()]);
    mockAccessLog.mockRejectedValue(new Error('500'));

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText('Dr. Priya Rao')).toBeInTheDocument();
  });

  it('reports an error when the consents themselves fail', async () => {
    mockConsents.mockRejectedValue(new Error('500'));

    const { container } = renderWithProviders(<SharingPage />);

    await waitFor(() => {
      expect(container.querySelector('.error-text')).not.toBeNull();
    });
  });
});
