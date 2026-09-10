
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchProfile = vi.fn();
const fetchDashboard = vi.fn();
const patchProfile = vi.fn();

vi.mock('../api/endpoints', () => ({
  fetchProfile: (...args: unknown[]) => fetchProfile(...args),
  fetchDashboard: (...args: unknown[]) => fetchDashboard(...args),
  patchProfile: (...args: unknown[]) => patchProfile(...args),
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'asha', email: 'asha@example.com' },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { ProfilePage } from './ProfilePage';
import { dashboardFixture, renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
  fetchProfile.mockResolvedValue({ id: 'u1', full_name: 'Asha', age: 27 });
});

async function openEdit() {
  const user = userEvent.setup();
  fetchDashboard.mockResolvedValue(dashboardFixture());

  renderWithProviders(<ProfilePage />);

  const opener = await screen.findByRole('button', { name: /Edit/i });
  await user.click(opener);

  return { user, opener };
}

describe('ProfilePage — the edit dialog (issue #502)', () => {
  it('opens as a modal dialog with an accessible name', async () => {
    await openEdit();

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleName(/Edit/i);
  });

  it('moves focus into the dialog rather than leaving it on the menu row', async () => {
    await openEdit();

    expect(screen.getByRole('dialog')).toHaveFocus();
  });

  it('is still the form, so its Save button submits it', async () => {
    await openEdit();

    expect(screen.getByRole('dialog').tagName).toBe('FORM');
  });

  it('closes on Escape, which it could not do before', async () => {
    
    const { user } = await openEdit();

    await user.keyboard('{Escape}');

    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    );
  });

  it('returns focus to the row that opened it', async () => {
    const { user, opener } = await openEdit();

    await user.keyboard('{Escape}');

    await waitFor(() => expect(opener).toHaveFocus());
  });

  it('keeps Tab inside the dialog', async () => {
    const { user } = await openEdit();
    const dialog = screen.getByRole('dialog');

    for (let step = 0; step < 12; step += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });
});
