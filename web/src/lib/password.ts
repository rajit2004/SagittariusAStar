
export const MIN_PASSWORD_LENGTH = 8;

export const MAX_PASSWORD_BYTES = 72;

const MIN_IDENTIFIER_FRAGMENT = 4;

const MAX_SEQUENCE_RUN = 5;

const SEQUENCES = [
  'abcdefghijklmnopqrstuvwxyz',
  '0123456789',
  'qwertyuiop',
  'asdfghjkl',
  'zxcvbnm',
];

const COMMON_PASSWORDS = new Set([
  '123456', '123456789', '12345678', '1234567', '1234567890', '12345',
  'password', 'password1', 'password123', 'passw0rd', 'p@ssw0rd',
  'qwerty', 'qwerty123', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm',
  '111111', '000000', '123123', '654321', '666666', '888888',
  'abc123', 'abcd1234', 'a1b2c3d4', 'letmein', 'welcome', 'welcome1',
  'iloveyou', 'monkey', 'dragon', 'sunshine', 'princess', 'football',
  'baseball', 'superman', 'trustno1', 'master', 'shadow', 'michael',
  'jennifer', 'computer', 'internet', 'samsung', 'google', 'facebook',
  'whatsapp', 'india123', 'indian123', 'bharat123', 'krishna',
  'ganesh', 'chennai', 'mumbai123', 'delhi123', 'admin', 'admin123',
  'root', 'test123', 'changeme', 'secret', 'login', 'pass1234',
  'rhythma', 'rhythma123', 'period123', 'health123',
]);

export type PasswordRuleCode =
  | 'too_short'
  | 'too_long'
  | 'too_common'
  | 'contains_identifier'
  | 'not_varied_enough'
  | 'sequential';

export interface PasswordRuleState {
  code: PasswordRuleCode;
  
  met: boolean;
}

export interface PasswordContext {
  email?: string;
  username?: string;
}

export function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

function identifierFragments({ email, username }: PasswordContext): string[] {
  const fragments: string[] = [];

  if (username) fragments.push(username);

  if (email && email.includes('@')) {
    const [local, domain] = email.split('@');
    fragments.push(local, ...local.split(/[._\-+]/));
    const firstLabel = domain?.split('.')[0];
    if (firstLabel) fragments.push(firstLabel);
  } else if (email) {
    fragments.push(email);
  }

  return fragments
    .map((fragment) => fragment.toLowerCase())
    .filter((fragment) => fragment.length >= MIN_IDENTIFIER_FRAGMENT);
}

function hasLongSequence(password: string): boolean {
  const lowered = password.toLowerCase();

  return SEQUENCES.some((source) => {
    const reversed = [...source].reverse().join('');
    for (let start = 0; start <= source.length - MAX_SEQUENCE_RUN; start += 1) {
      if (lowered.includes(source.slice(start, start + MAX_SEQUENCE_RUN))) return true;
      if (lowered.includes(reversed.slice(start, start + MAX_SEQUENCE_RUN))) return true;
    }
    return false;
  });
}

export function evaluatePassword(
  password: string,
  context: PasswordContext = {},
): PasswordRuleState[] {
  const lowered = password.toLowerCase();
  const fragments = identifierFragments(context);
  const distinctCharacters = new Set(password).size;

  return [
    {
      code: 'too_short',
      met: password.length >= MIN_PASSWORD_LENGTH,
    },
    {
      code: 'too_long',
      met: byteLength(password) <= MAX_PASSWORD_BYTES,
    },
    {
      code: 'too_common',
      met: !COMMON_PASSWORDS.has(lowered),
    },
    {
      code: 'contains_identifier',
      met: !fragments.some((fragment) => lowered.includes(fragment)),
    },
    {
      
      code: 'not_varied_enough',
      met: password.length < 4 || distinctCharacters >= 4,
    },
    {
      code: 'sequential',
      met: !hasLongSequence(password),
    },
  ];
}

export function isPasswordAcceptable(
  password: string,
  context: PasswordContext = {},
): boolean {
  return password.length > 0 && evaluatePassword(password, context).every((rule) => rule.met);
}

export function serverPasswordFailures(error: unknown): string[] {
  if (!error || typeof error !== 'object') return [];

  const response = (error as { response?: { data?: unknown } }).response;
  const data = response?.data as
    | { error?: { code?: string; details?: unknown } }
    | undefined;

  if (data?.error?.code !== 'weak_password') return [];
  if (!Array.isArray(data.error.details)) return [];

  return data.error.details
    .map((item) => (item && typeof item === 'object' ? (item as { message?: unknown }).message : null))
    .filter((message): message is string => typeof message === 'string' && message.length > 0);
}
