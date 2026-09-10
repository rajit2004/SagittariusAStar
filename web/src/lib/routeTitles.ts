
const ROUTE_TITLE_KEYS: { pattern: RegExp; key: string }[] = [
  { pattern: /^\/$/, key: 'meta.home.title' },
  { pattern: /^\/cycle/, key: 'meta.cycle.title' },
  { pattern: /^\/assistant/, key: 'meta.assistant.title' },
  { pattern: /^\/insights/, key: 'meta.insights.title' },
  { pattern: /^\/profile/, key: 'meta.profile.title' },
  { pattern: /^\/settings/, key: 'meta.settings.title' },
  { pattern: /^\/sharing/, key: 'meta.sharing.title' },
  { pattern: /^\/sms/, key: 'meta.sms.title' },
  { pattern: /^\/login/, key: 'meta.login.title' },
  { pattern: /^\/register/, key: 'meta.register.title' },
  { pattern: /^\/provider\/patients\//, key: 'meta.providerPatient.title' },
  { pattern: /^\/provider\/login/, key: 'meta.providerLogin.title' },
  { pattern: /^\/provider\/register/, key: 'meta.providerRegister.title' },
  { pattern: /^\/provider/, key: 'meta.providerDashboard.title' },
];

export function routeTitleKey(pathname: string): string {
  const match = ROUTE_TITLE_KEYS.find((route) => route.pattern.test(pathname));
  return match ? match.key : 'meta.appName';
}
