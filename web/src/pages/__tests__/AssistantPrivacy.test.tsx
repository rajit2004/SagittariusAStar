import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const sendChatMessage = vi.fn();

vi.mock('../../api/endpoints', () => ({
  sendChatMessage: (...args: unknown[]) => sendChatMessage(...args),
}));

let currentUser: { id: string; username: string } | null = null;

vi.mock('../../auth/useAuth', () => ({
  useAuth: () => ({
    user: currentUser,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('../../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { AssistantPage } from '../AssistantPage';
import { clearAllHistories, LEGACY_KEY, saveHistory } from '../../lib/chatHistory';
import { renderWithProviders } from '../../test/utils';

const ASHA = { id: 'user-asha', username: 'Asha' };
const BEGUM = { id: 'user-begum', username: 'Begum' };

const PRIVATE_QUESTION = 'is this much bleeding normal for me?';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  currentUser = ASHA;
  sendChatMessage.mockResolvedValue({
    response: 'Here is some general information.',
    language: 'en',
    disclaimer: 'Please consult a healthcare professional.',
  });
});

describe('a shared browser', () => {
  it('does not show the next person the last person’s conversation', async () => {
    saveHistory(ASHA.id, [{ role: 'user', content: PRIVATE_QUESTION }]);

    currentUser = BEGUM;
    renderWithProviders(<AssistantPage />);

    expect(screen.queryByText(PRIVATE_QUESTION)).not.toBeInTheDocument();
    expect(await screen.findByText(/Begum/)).toBeInTheDocument();
  });

  it('restores the conversation for the account that wrote it', async () => {
    saveHistory(ASHA.id, [{ role: 'user', content: PRIVATE_QUESTION }]);

    renderWithProviders(<AssistantPage />);

    expect(await screen.findByText(PRIVATE_QUESTION)).toBeInTheDocument();
  });

  it('ignores the shared key written before transcripts were namespaced', () => {
    localStorage.setItem(
      LEGACY_KEY,
      JSON.stringify([{ role: 'user', content: PRIVATE_QUESTION }]),
    );

    renderWithProviders(<AssistantPage />);

    expect(screen.queryByText(PRIVATE_QUESTION)).not.toBeInTheDocument();
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it('re-seeds when the signed-in account changes under a mounted screen', async () => {
    saveHistory(ASHA.id, [{ role: 'user', content: PRIVATE_QUESTION }]);
    const { rerender } = renderWithProviders(<AssistantPage />);
    expect(await screen.findByText(PRIVATE_QUESTION)).toBeInTheDocument();

    currentUser = BEGUM;
    rerender(<AssistantPage />);

    await waitFor(() =>
      expect(screen.queryByText(PRIVATE_QUESTION)).not.toBeInTheDocument(),
    );
  });

  it('does not send the previous account’s turns as context', async () => {
    
    saveHistory(ASHA.id, [{ role: 'user', content: PRIVATE_QUESTION }]);
    currentUser = BEGUM;
    renderWithProviders(<AssistantPage />);

    await userEvent.type(screen.getByRole('textbox'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => expect(sendChatMessage).toHaveBeenCalled());
    const history = sendChatMessage.mock.calls[0][2] as { content: string }[];
    expect(history.some((m) => m.content === PRIVATE_QUESTION)).toBe(false);
  });
});

describe('clearing from the screen', () => {
  it('offers no clear button before anything has been asked', () => {
    renderWithProviders(<AssistantPage />);

    expect(
      screen.queryByRole('button', { name: /clear conversation/i }),
    ).not.toBeInTheDocument();
  });

  it('clears the transcript from the screen and from storage', async () => {
    saveHistory(ASHA.id, [{ role: 'user', content: PRIVATE_QUESTION }]);
    renderWithProviders(<AssistantPage />);
    expect(await screen.findByText(PRIVATE_QUESTION)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /clear conversation/i }));

    expect(screen.queryByText(PRIVATE_QUESTION)).not.toBeInTheDocument();
    expect(localStorage.getItem(`${LEGACY_KEY}:${ASHA.id}`)).toBeNull();
  });

  it('says the transcript is kept on this device', () => {
    
    renderWithProviders(<AssistantPage />);

    expect(screen.getByText(/kept on this device/i)).toBeInTheDocument();
  });
});

describe('signing out', () => {
  it('leaves no transcript behind for the next person', () => {
    saveHistory(ASHA.id, [{ role: 'user', content: PRIVATE_QUESTION }]);
    saveHistory(BEGUM.id, [{ role: 'user', content: 'something else' }]);

    clearAllHistories();

    currentUser = BEGUM;
    renderWithProviders(<AssistantPage />);

    expect(screen.queryByText(PRIVATE_QUESTION)).not.toBeInTheDocument();
    expect(screen.queryByText('something else')).not.toBeInTheDocument();
  });
});
