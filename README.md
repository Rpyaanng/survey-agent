# Survey Agent

A multi-tenant SaaS for running surveys as **conversations**. Respondents can fill out a classic form, chat with an AI interviewer, talk to a voice agent in the browser, or take a phone call. Every answer is validated into clean, structured data, whatever the channel.

Survey Agent is a generalization of the **med-doc-flask** backend and **med-doc-ai** frontend. Those apps ran medical intake conversations. This one turns the same core (AI conversational data collection, voice agents, form import) into a general survey platform with accounts, workspaces, roles, and subscription billing.

| | |
|---|---|
| **Backend** | Flask 3 · SQLAlchemy 2 · Alembic · Postgres (SQLite locally) · Pydantic · Anthropic Claude · Stripe · ElevenLabs · Resend |
| **Frontend** | Next.js 16 (App Router) · React 19 · Tailwind CSS 4 · SWR · Radix UI |
| **Tests** | 95 backend tests (pytest). Frontend typecheck and production build in CI |

## Features

- **Four response channels from one survey.** Web form, AI chat interviewer, browser voice (ElevenLabs), and outbound phone campaigns (ElevenLabs + Twilio).
- **AI survey builder.** Describe your goal and get a draft with neutral wording and the right question types.
- **Imports.** One-way **Google Forms** import (deterministic, no AI needed). **PDF** import turns paper or fillable forms into surveys with AI. Imported surveys are fully native: all responses are collected and stored in Survey Agent.
- **Typed questions and normalized answers.** 13 question types. Answers from any channel pass through one normalizer, so analytics and exports stay consistent.
- **Analytics.** Completion funnel, channel mix, 30-day timeline, NPS breakdown, distributions, and open-text samples. **AI insights** produce an executive summary with themes and recommendations.
- **Workspaces and teams.** Multiple workspaces per user, owner/admin/editor/viewer roles, and email invitations.
- **Subscriptions.** Free / Pro / Team / Enterprise plans with feature gates and metered quotas (responses, AI generations, voice minutes, seats, live surveys). Stripe Checkout, Customer Portal, and webhooks keep plan state in sync.
- **Developer platform.** Workspace API keys and HMAC-signed outbound webhooks (`response.completed`, `survey.published`, `survey.closed`).
- **Branding.** Per-workspace logo and color on survey pages. Removable "Powered by" badge on paid plans. Embeddable via iframe, plus QR codes.

## Plans

Defined in [`backend/survey_agent/billing/plans.py`](backend/survey_agent/billing/plans.py), the single source of truth for both the API and the pricing page.

| | Free | Pro ($39/mo) | Team ($149/mo) | Enterprise |
|---|---|---|---|---|
| Live surveys | 3 | Unlimited | Unlimited | Unlimited |
| Responses / month | 100 | 2,000 | 10,000 | Unlimited |
| Seats | 1 | 3 | 15 | Unlimited |
| AI generations / month | 10 | 200 | 1,000 | Unlimited |
| Voice minutes / month | – | 300 | 2,000 | Unlimited |
| Form + AI chat, AI builder | ✓ | ✓ | ✓ | ✓ |
| Imports, voice, export, AI insights, remove branding | | ✓ | ✓ | ✓ |
| Phone campaigns, REST API, webhooks | | | ✓ | ✓ |

## Architecture

```
Browser ──► Next.js (web) ──/api/* rewrite──► Flask API ──► Postgres
               │  same-origin, so the httpOnly                ├─► Anthropic Claude (interviewer, builder, extraction, insights)
               │  session cookie is first-party               ├─► ElevenLabs (voice + phone) ◄── signed post-call webhook
               └─ /s/:token respondent pages                  ├─► Stripe ◄── signed subscription webhooks
                                                              ├─► Resend (notifications, invitations)
                                                              └─► Customer webhooks (HMAC-signed)
```

Key decisions:

- **Stateless API, all state in the database.** The original backend kept sessions in process memory, which broke with more than one gunicorn worker. The API now scales horizontally behind a load balancer.
- **Stateless AI interviewer.** Each chat turn renders the current state (questions, answers so far, skips, validation feedback) into the prompt and gets back JSON through Claude structured outputs. Answers are normalized server-side, and rejected answers are fed back so the agent re-asks.
- **Offline AI provider.** Without `ANTHROPIC_API_KEY`, a deterministic rule-based engine powers chat, generation, imports and insights. The whole product runs locally, and in CI, with zero API keys.
- **Tenant isolation by construction.** Every query is scoped by `org_id` through shared helpers; other workspaces' resources return 404. Tests cover it.
- **Pluggable background work.** Slow side effects (webhooks, emails, transcript analysis, calls) go through `tasks.enqueue()`. Tasks take IDs, so swapping the thread pool for RQ or Celery is a one-module change.

```
backend/
  survey_agent/
    api/            Blueprints: auth, orgs, surveys, responses, public, billing, developer, integrations
    ai/             Provider abstraction, interviewer, builder, extraction, insights, prompts/*.md
    billing/        Plan catalog, entitlements and quotas, Stripe
    services/       Answers normalizer, responses, surveys, analytics, voice, webhooks, email, importers
    models/         SQLAlchemy models (accounts, billing, surveys)
  migrations/       Alembic
  tests/
frontend/
  app/(marketing)   Landing and pricing
  app/(auth)        Login, signup, invitations
  app/dashboard     Workspace app: surveys (build, settings, share, responses, analytics), team, billing, developers
  app/s/[token]     Respondent experience: form, chat, voice
docs/               API reference, voice agent setup
```

## Quick start (local, no Docker)

Prerequisites: Python 3.12+ and Node 20+.

```bash
# API: http://localhost:5000
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # works as-is with SQLite and the offline AI
flask --app wsgi db upgrade
flask --app wsgi seed-demo                              # demo@surveyagent.dev / demo-password (Team plan)
python wsgi.py

# Web: http://localhost:3000
cd frontend
npm install
npm run dev
```

Sign in with the demo account, or sign up. Without Stripe keys, **development billing** lets you switch plans instantly from Billing (it's disabled in production).

## Docker

```bash
cp .env.example .env        # set SECRET_KEY
docker compose up --build   # Postgres, Redis, API (runs migrations on boot), web
docker compose exec backend flask --app wsgi seed-demo
```

## Deployment

- **Render:** [`render.yaml`](render.yaml) provisions Postgres, Redis, the API and the web service. Set the `sync: false` secrets in the dashboard. `BACKEND_URL` for the web service must be the API's public URL (it's read at build time for the `/api` rewrite).
- **Anywhere else:** both services ship production Dockerfiles. The API runs `flask db upgrade` then gunicorn (gthread workers, since the AI and webhook calls are IO-bound). The web app is a standalone Next.js server.
- Production checklist: set a strong `SECRET_KEY` (the app refuses to boot without one in production), serve over HTTPS (cookies are `Secure` in production), point `RATELIMIT_STORAGE_URI` at Redis, and configure Stripe and ElevenLabs webhooks with their secrets.

### Integrations

| Integration | Setup |
|---|---|
| **Claude** | Set `ANTHROPIC_API_KEY`. The default model is `claude-opus-5` (override with `AI_MODEL`). Server-side refusal fallback is on by default (`AI_REFUSAL_FALLBACK`). |
| **Stripe** | Create Pro and Team monthly prices and set `STRIPE_PRICE_PRO` / `STRIPE_PRICE_TEAM`. Add a webhook to `/api/v1/integrations/stripe/webhook` for `checkout.session.completed` and `customer.subscription.*`, and set `STRIPE_WEBHOOK_SECRET`. Enable the Customer Portal. |
| **ElevenLabs** | See [docs/voice-agent-prompt.md](docs/voice-agent-prompt.md). |
| **Resend** | Set `RESEND_API_KEY` and `EMAIL_FROM` for invitation and new-response emails. Without them, emails are logged instead of sent. |

## Testing

```bash
cd backend && pytest                            # 95 tests, fully offline (fake AI, mocked HTTP)
cd frontend && npm run typecheck && npm run build
```

## API

Full reference: [docs/API.md](docs/API.md). Quick example with an API key:

```bash
curl -H "Authorization: Bearer sa_live_…" https://api.example.com/api/v1/surveys
```

## What changed from med-doc

| med-doc-flask / med-doc-ai | Survey Agent |
|---|---|
| In-memory sessions, single process | Postgres-backed, horizontally scalable |
| No accounts | Users, workspaces, roles, invitations, API keys |
| Medical intake prompts | General-purpose interviewer with configurable persona and tone |
| Google Form / PDF answers written back to the source | One-way import; all data collected in-app |
| Chat via an ElevenLabs text agent | Native Claude interviewer with live answer capture and validation |
| ElevenLabs webhooks unverified | HMAC-verified, idempotent webhooks |
| OpenAI, Gemini and Claude mixed | One provider abstraction on Claude structured outputs, plus an offline engine |
| No billing | Plans, quotas, feature gates, Stripe |

Not carried over, because they're specific to the clinical product: the audio scribe (Deepgram transcription into chart templates), filled-PDF export, and the license-plate test page.

## Roadmap ideas

- Durable job queue (RQ/Celery) for high-volume phone campaigns
- Skip logic and branching questions
- SSO/SAML and audit logs for Enterprise
- Multi-language interviews (the `language` setting is already stored per survey)
- Annual billing and per-seat pricing
