<h1 align="center">Rhythma</h1>

<p align="center">
  <strong>Her Rhythm. Her Health. Her Power. An AI-powered menstrual and women's health companion built for Indian women.</strong>
</p>

<p align="center">
  <a href="#-features"><img src="https://img.shields.io/badge/Features-6DB33F?style=flat-square" alt="Features" /></a>
  <a href="#-how-it-works"><img src="https://img.shields.io/badge/How_It_Works-FF6F61?style=flat-square" alt="How It Works" /></a>
  <a href="#-tech-stack"><img src="https://img.shields.io/badge/Tech_Stack-4FC3F7?style=flat-square" alt="Tech Stack" /></a>
  <a href="#-project-structure"><img src="https://img.shields.io/badge/Structure-FFB74D?style=flat-square" alt="Structure" /></a>
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-81C784?style=flat-square" alt="Quick Start" /></a>
  <a href="#-configuration"><img src="https://img.shields.io/badge/Config-AB47BC?style=flat-square" alt="Configuration" /></a>
  <a href="#-contributing"><img src="https://img.shields.io/badge/Contributing-F06292?style=flat-square" alt="Contributing" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/made_with-Flutter-blue?logo=flutter&style=flat-square" alt="Flutter" />
  <img src="https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&style=flat-square" alt="FastAPI" />
  <img src="https://img.shields.io/badge/AI-Gemini-4285F4?logo=google&style=flat-square" alt="Gemini" />
</p>

---

## What is Rhythma?

**Rhythma** is an offline-first, multilingual menstrual health companion designed for Indian women. It handles irregular cycles, provides AI-powered health insights, and works in 17 regional languages, all without assuming you have a stable internet connection.

Most period trackers assume a 28-day cycle and English fluency. Rhythma does not. It is built from the ground up for women in tier-2, tier-3, and semi-urban India, where internet access is spotty and health conversations are often taboo.

---

## Features

* **Smart Cycle Tracking**
  Handles irregular cycles with no fixed 28-day assumption. Log flow, mood, symptoms, sleep, water intake, and medications.

* **Gemini-Powered AI Assistant**
  Real-time health conversations powered by Google Gemini (`gemini-2.5-flash`), with rate limiting and safety gating.

* **Cycle Variability Index (CVI)**
  A trained XGBoost model that scores cycle regularity, with a heuristic fallback if the model file is unavailable.

* **Menstrual Health Score (MHS)**
  A weighted composite of CVI, sleep, stress, symptoms, and lifestyle data to give a single health number.

* **Hormonal Risk Indicator**
  Three-tier alerting (Low, Medium, High) derived from CVI to flag potential hormonal concerns early.

* **Offline-First Architecture**
  Hive local storage with Firestore sync. Core features work with zero internet and sync when you are back online.

* **17 Indian Regional Languages**
  Hindi, Marathi, Tamil, Telugu, Bengali, Kannada, and more. Translation files exist for all 17 languages.

* **SMS Health Summaries**
  Twilio integration for sending health summaries via SMS, so users without smartphones can still get insights.

* **Privacy-First Design**
  Auth, password policy, rate limiting, and data export are all implemented server-side. ML models run on-device.

* **AI Health Assistant**
  A conversational assistant that answers health questions using Gemini, with context from your logged data.

* **Ayurvedic Wellness Layer**
  Educational content connecting lifestyle and cycle data to Ayurvedic wellness concepts.

* **WhatsApp and Telegram Bot**
  Full chat-linking with command engine (status, link, unlink, help) for users who prefer messaging apps.

* **Provider Portal**
  Healthcare professionals can view consenting patients' longitudinal health data through a dedicated portal.

* **PDF Health Reports**
  Export your health data as a formatted PDF, generated client-side.

---

## How It Works

```text
User registers with phone or email
        |
        v
Firebase Auth issues JWT token
        |
        v
Onboarding introduces the app (first launch only)
        |
        v
User logs cycle data, symptoms, mood, sleep
        |
        v
Data is stored locally (Hive) and synced to Firestore
        |
        v
Backend computes CVI and MHS scores
        |
        v
Gemini generates personalized health insights
        |
        v
User interacts with AI Assistant for health questions
        |
        v
SMS summaries are sent via Twilio (optional)
```

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| **Mobile** | Flutter, Material Design 3 |
| **Backend** | Python 3.10, FastAPI, Uvicorn |
| **Database** | Firebase Firestore (cloud), Hive (local) |
| **AI** | Google Gemini (`gemini-2.5-flash`) |
| **ML Models** | XGBoost (CVI), weighted composite (MHS) |
| **Auth** | Firebase Auth (phone + email), JWT |
| **SMS** | Twilio |
| **Bot** | WhatsApp via Twilio/Meta Cloud API, Telegram |
| **i18n** | 17 ARB translation files |
| **CI/CD** | GitHub Actions (Flutter analyze + test, backend pytest) |

---

## Project Structure

```text
Rhythma/
├── backend/                          # FastAPI backend
│   ├── api/                          # Route handlers (assistant, bot, cycle, dashboard, etc.)
│   ├── core/                         # Auth, middleware, security, validation
│   ├── models/                       # ML models (CVI, MHS)
│   ├── services/                     # Business logic (chatbot, scoring, SMS, etc.)
│   ├── tests/                        # 42 test modules
│   └── main.py                       # App entry point
│
├── rhythma_flutter/                  # Flutter mobile app
│   ├── lib/
│   │   ├── components/               # Shared widgets
│   │   ├── config/                   # App configuration, theme, constants
│   │   ├── l10n/                     # 17 language translations
│   │   ├── models/                   # Data models
│   │   ├── providers/                # State management
│   │   ├── screens/                  # All UI screens
│   │   └── services/                 # Storage, API, auth, notifications
│   └── test/                         # 25 test files
│
├── web/                              # React + TypeScript + Vite web app
│   └── src/
│       ├── api/                      # API client and endpoints
│       ├── auth/                     # Auth context and routes
│       ├── pages/                    # All page components
│       └── test/                     # 34 test files
│
├── landing-page/                     # Next.js marketing site
├── docs/                             # Architecture, medical sources, disclaimers
└── .github/workflows/                # CI for backend, Flutter, web, landing page
```

---

## Quick Start

### Prerequisites

* Flutter 3.x
* Python 3.10+
* Node.js 18+ (only for web and landing page)
* A Firebase project
* A Gemini API key ([get one here](https://ai.google.dev))

---

### 1. Clone the Repository

```bash
git clone https://github.com/rajit2004/SagittariusAStar.git
cd SagittariusAStar
```

---

### 2. Run the Backend

```bash
cd backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r ../requirements.txt

cp .env.example .env
# Fill in JWT_SECRET, Firebase credentials, and optionally GEMINI_API_KEY / Twilio credentials

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

To run backend tests:

```bash
cd backend
pytest
```

---

### 3. Run the Flutter App

```bash
cd rhythma_flutter

flutter create .
flutter pub get

cp env.example .env
# Add GEMINI_API_KEY to .env for real AI responses

# Add your Firebase config:
# android/app/google-services.json

flutter run
```

For a physical device, pass your machine's local IP:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.100:8000/api/v1
```

---

### 4. Run the Web App (Optional)

```bash
cd web
cp .env.example .env.local

npm install
npm run dev
```

---

### 5. Run the Landing Page (Optional)

```bash
cd landing-page
npm install
npm run dev
```

---

## Configuration

### Backend (`backend/.env`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `JWT_SECRET` | Yes | Signs and verifies auth tokens |
| `FIREBASE_SERVICE_ACCOUNT_JSON` or `FIREBASE_SERVICE_ACCOUNT_PATH` | Yes | Firebase Admin SDK credentials for Firestore |
| `GEMINI_API_KEY` | Optional | Enables the AI assistant endpoint |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Optional | Enables SMS health summaries |

### Flutter (`rhythma_flutter/.env`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | Optional | Enables real AI responses in the Assistant tab |

### Web (`web/.env.local`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | No | Defaults to `http://localhost:8000/api/v1` |

---

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.

```bash
git checkout -b feature/amazing-idea
```

3. Commit changes.

```bash
git commit -m "Add amazing feature"
```

4. Push branch.

```bash
git push origin feature/amazing-idea
```

5. Open a Pull Request.

Please review the project's Code of Conduct and Contributing Guidelines before contributing.

---

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

* **Google Gemini** for AI-powered health conversations
* **FastAPI** for a fast, modern Python backend
* **Flutter** for cross-platform mobile development
* **Firebase** for authentication and cloud sync
* **Twilio** for SMS delivery

---

## Disclaimer

Rhythma is intended for educational and preventive health awareness purposes only. It is not a certified medical device and does not provide medical diagnoses, prescriptions, or treatment recommendations. Always consult a qualified healthcare professional for medical advice.

---

# Author

**Ranesh Rajit**
B.Tech Computer Science Student, India

[![GitHub](https://img.shields.io/badge/GitHub-rajit2004-black?style=flat&logo=github)](https://github.com/rajit2004)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-ranesh--kun-blue?style=flat&logo=linkedin)](https://linkedin.com/in/ranesh-kun)
