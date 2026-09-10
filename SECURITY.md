# Security Policy

Rhythma handles sensitive personal health data, including menstrual cycle logs, symptoms, mood, and other private information. We take security seriously and appreciate your help keeping the project and its users safe.

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.** Public issues are visible to everyone, including anyone who might exploit the report before a fix ships.

Instead, report privately by emailing:

**rhythma.official@gmail.com**

Please include:

- A clear description of the vulnerability and its impact
- Steps to reproduce, including affected endpoints, screens, or files
- The component involved (backend, Flutter app, web app, or landing page)
- Proof-of-concept code or request/response examples if applicable
- Whether you believe the issue is currently being exploited
- Your contact information for follow-up

### What to Expect

- **Acknowledgment:** Within 72 hours
- **Initial assessment:** Within 7 days
- **Fix timeline:** Depends on severity. Critical issues (auth bypass, data exposure) are prioritized immediately.
- **Disclosure:** We request coordinated disclosure. Please avoid publishing details until a fix is available.

---

## Supported Versions

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Any fork or older commit | No |

Only the latest code on `main` is supported. There is no backport policy.

---

## Scope

**In scope:**

- **Backend:** Authentication and authorization, Firestore data access, input validation, CORS configuration, secrets handling, rate limiting, AI assistant prompt injection
- **Flutter app:** Local data storage and encryption, auth token handling, data leakage via logs, API key handling
- **Web app:** Auth token storage, XSS/CSRF exposure, insecure endpoint calls
- **Landing page:** Dependency vulnerabilities or exposed secrets
- **Supply chain:** Vulnerable dependencies in requirements.txt, pubspec.yaml, or package.json with a demonstrated exploit path

**Out of scope:**

- Automated scanner findings without a demonstrated exploit
- Social engineering or phishing attacks
- Denial-of-service requiring unrealistic traffic
- Issues in third-party services (Firebase, Gemini, Twilio, Vercel). Report those to the vendor directly.

---

## For Contributors: Secure Development

- Never commit secrets, API keys, or credentials
- Validate and sanitize all user input on the backend
- Use parameterized Firestore queries
- Do not log sensitive data even at debug level
- Explicitly state in your PR whether new endpoints require authentication
- Prefer secure defaults (HTTPS, proper authorization, least-privilege access)

---

## Data Handling

Rhythma is built around a privacy-first principle: health data stays on-device by default, with cloud sync as an explicit opt-in choice. If you implement a feature that touches user health data, keep this in mind.

If you accidentally commit credentials or sensitive material, notify a maintainer immediately. Repository history may need to be rewritten.

---

Thank you for helping keep Rhythma and its users safe.
