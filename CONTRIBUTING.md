# Contributing to Rhythma

Thanks for your interest in contributing to Rhythma. Every contribution matters, whether it's code, documentation, translations, design, or bug reports.

Please read this guide before opening an issue or pull request.

---

## Project Setup

```bash
git clone https://github.com/rajit2004/SagittariusAStar.git
cd SagittariusAStar
```

**Flutter app:**

```bash
cd rhythma_flutter
flutter pub get
cp env.example .env
flutter run
```

**Backend:**

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r ../requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

**Web app:**

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

---

## Branch Naming

Branch off `main` using one of these prefixes:

| Prefix | Use for |
| --- | --- |
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code restructuring with no behavior change |
| `test/` | Adding or fixing tests |
| `chore/` | Tooling, dependencies, config |

Use lowercase, hyphen-separated, descriptive names. Not just issue numbers.

---

## Issue Workflow

1. Search open and closed issues first to avoid duplicates.
2. Open an issue before starting non-trivial work. Small typo fixes can skip straight to a PR.
3. Wait for a maintainer acknowledgment on larger issues before submitting a large PR.

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short summary>

<optional body>

<optional footer, e.g. "Closes #42">
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples:**

```
feat(cycle): persist cycle logs to Hive on save

fix(sms): reset rate limiter window correctly

docs(readme): correct cloud sync status

test(backend): add coverage for /cycle history endpoint
```

Keep the summary under 72 characters, written in imperative mood ("add", not "added").

---

## Coding Style

### General

- Keep code simple and maintainable
- Match the existing architecture unless a refactor has been discussed first
- Avoid unnecessary dependencies
- Remove debug code before submitting

### Flutter

- Use snake_case for file names
- Use PascalCase for classes and widgets
- Use localization for user-facing strings
- Keep business logic out of UI widgets

### Backend

- Use type hints for new code
- Use Pydantic models for request/response schemas
- Keep route handlers lightweight
- Move reusable logic into services

### Web

- TypeScript, not plain JS
- Follow the existing API client pattern for backend calls
- Use react-i18next for user-facing strings
- Run `npm run lint` before opening a PR

---

## How to Test

**Flutter:**

```bash
cd rhythma_flutter
flutter analyze
flutter test
```

**Backend:**

```bash
cd backend
pytest -v
```

**Web:**

```bash
cd web
npm run lint
npm run build
```

---

## Before Opening a PR

- Rebase or merge the latest `main` into your branch
- Run the relevant test suite
- Update documentation if you changed behavior
- Remove debug prints, commented-out dead code, and unused imports
- Keep the PR scoped to one logical change
- For UI changes, include before/after screenshots
- For API changes, update or add relevant API documentation

---

## PR Workflow

1. Open the PR against `main` with a descriptive title following the commit message format.
2. Fill out the PR description with what changed, why, how you tested it, and linked issues.
3. Request review if you are not sure who should review.
4. Respond to review comments in the PR thread.
5. Keep the PR up to date with `main` if review takes a while.
6. A maintainer will merge once approved and checks pass.

---

## Maximum Recommended PR Size

Split large features into multiple pull requests. Each PR should focus on one logical change. Use multiple meaningful commits instead of one large commit.

---

## Security Guidelines

- Never commit secrets or credentials
- Never commit .env files
- Use .env.example for configuration examples
- Remove sensitive logs before submission
- Report security issues privately to maintainers

If you discover a security vulnerability, do not open a public GitHub issue. Email **rhythma.official@gmail.com** instead.

---

## Code of Conduct

Be kind, constructive, and considerate in all interactions. Harassment, discrimination, abusive behavior, or personal attacks will not be tolerated.

---

## Questions?

If you are unsure about implementation details or project direction, open an issue and ask before starting work.

If you are unsure where to start, look for issues labeled `good first issue` or `help wanted`.

Thanks for helping improve Rhythma.
