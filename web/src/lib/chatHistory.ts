
export interface StoredMessage {
  role: 'user' | 'model';
  content: string;
  isError?: boolean;
}

const KEY_PREFIX = 'rhythma_chat_history';

export const LEGACY_KEY = KEY_PREFIX;

export const MAX_STORED_MESSAGES = 20;

function keyFor(userId: string): string {
  return `${KEY_PREFIX}:${userId}`;
}

function storage(): Storage | null {
  
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

export function clearLegacyHistory(): void {
  try {
    storage()?.removeItem(LEGACY_KEY);
  } catch {
    
  }
}

export function loadHistory(userId: string | undefined | null): StoredMessage[] {
  clearLegacyHistory();

  if (!userId) return [];

  const store = storage();
  if (!store) return [];

  try {
    const raw = store.getItem(keyFor(userId));
    if (!raw) return [];

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed
      .filter((entry): entry is StoredMessage => {
        if (!entry || typeof entry !== 'object') return false;
        const message = entry as Partial<StoredMessage>;
        return (
          typeof message.content === 'string' &&
          message.content.length > 0 &&
          (message.role === 'user' || message.role === 'model')
        );
      })
      .slice(-MAX_STORED_MESSAGES);
  } catch {
    
    return [];
  }
}

export function saveHistory(
  userId: string | undefined | null,
  messages: StoredMessage[],
): void {
  if (!userId) return;

  try {
    storage()?.setItem(
      keyFor(userId),
      JSON.stringify(messages.slice(-MAX_STORED_MESSAGES)),
    );
  } catch {
    
  }
}

export function clearHistory(userId: string | undefined | null): void {
  try {
    if (userId) storage()?.removeItem(keyFor(userId));
  } catch {
    
  }
}

export function clearAllHistories(): void {
  const store = storage();
  if (!store) return;

  try {
    const doomed: string[] = [];
    for (let index = 0; index < store.length; index++) {
      const key = store.key(index);
      if (key && key.startsWith(KEY_PREFIX)) doomed.push(key);
    }
    
    for (const key of doomed) store.removeItem(key);
  } catch {
    
  }
}
