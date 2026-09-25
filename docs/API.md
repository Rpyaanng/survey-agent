# REST API reference

Base path: `/api/v1`. Every request and response is JSON unless noted.

## Authentication

| Method | How | Use for |
|---|---|---|
| Session cookie | `POST /auth/login` sets an httpOnly `sa_session` cookie. Mutating requests must also send `X-Requested-With: fetch` (CSRF guard). | The web app |
| Bearer JWT | `Authorization: Bearer <token>` (the `token` field returned by login/register) | Scripts, mobile clients |
| API key | `Authorization: Bearer sa_live_…` (create under **Developers**, Team plan) | Server-to-server integrations. Editor-level access to one workspace. |

**Workspace selection:** user sessions send `X-Org-Id: <org id>`. Without it, the user's default workspace is used. API keys are bound to one workspace.

**Roles:** `viewer` < `editor` < `admin` < `owner`. Each endpoint below lists its minimum role.

## Errors

```json
{ "error": { "code": "plan_limit", "message": "…", "details": { "feature": "export", "required_plan": "pro" } } }
```

| Status | Codes |
|---|---|
| 400 | `bad_request`, `no_questions`, `invalid_form_url`, `invalid_pdf`, `mode_disabled`, … |
| 401 | `unauthorized`, `session_expired`, `invalid_credentials`, `invalid_signature` |
| 402 | `plan_limit`: quota exhausted, or a feature isn't on the current plan |
| 403 | `forbidden`, `csrf_failed` |
| 404 | `not_found` (also returned for other workspaces' resources) |
| 409 | `conflict`, `email_taken`, `response_closed` |
| 410 | `survey_closed` |
| 422 | `validation_error`, with `details` listing the fields |
| 429 | Rate limited |

List endpoints accept `?page=&per_page=` (max 100) and return `{items, page, per_page, total}`.

## Auth & account

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | `{email, password, name?, organization_name?}`: creates the user, a workspace, and a free subscription |
| POST | `/auth/login` | `{email, password}` |
| POST | `/auth/logout` | Clears the cookie |
| GET / PATCH | `/auth/me` | Profile plus workspaces. PATCH `{name?, current_password?, new_password?}` |

## Workspaces & team

| Method | Path | Role |
|---|---|---|
| POST | `/orgs` | any user: create another workspace |
| GET / PATCH | `/org` | viewer / admin: `{name?, branding: {logo_url?, primary_color?}}` |
| GET | `/org/members` | viewer: members, plus pending invitations for admins |
| PATCH / DELETE | `/org/members/:id` | admin: `{role}` (the last owner is protected) |
| POST | `/org/leave` | viewer |
| POST | `/org/invitations` | admin: `{email, role}`. Seat-limited; returns `accept_link` |
| DELETE | `/org/invitations/:id` | admin |
| GET | `/invitations/:token` | public: invitation preview |
| POST | `/invitations/:token/accept` | signed-in user whose email matches |

## Surveys

| Method | Path | Role / plan |
|---|---|---|
| GET | `/surveys?status=&q=` | viewer |
| POST | `/surveys` | editor: `{title, description?, questions?, settings?}` |
| POST | `/surveys/generate` | editor: `{prompt, question_count}`. AI builder, counts toward `ai_generations` |
| POST | `/surveys/import/google-form` | editor, Pro: `{url}`. One-way import; responses are collected in Survey Agent |
| POST | `/surveys/import/pdf` | editor, Pro: multipart `file`. AI converts the form |
| GET / PATCH / DELETE | `/surveys/:id` | viewer / editor / editor |
| PUT | `/surveys/:id/questions` | editor: full ordered list. Removing a question that has answers archives it |
| POST | `/surveys/:id/publish` · `/close` · `/duplicate` | editor. Publishing is limited by live-survey slots |
| GET | `/surveys/:id/analytics` | viewer: funnel, channels, 30-day timeline, per-question stats (NPS, distributions) |
| POST | `/surveys/:id/insights` | editor, Pro: AI executive summary |
| GET | `/surveys/:id/responses?status=&channel=` | viewer |
| GET | `/surveys/:id/export?format=csv\|json&status=completed\|all` | viewer, Pro |
| GET / POST | `/surveys/:id/outreach` | viewer / editor, Team: `{contacts: [{name?, phone: "+E164"}]}` places voice calls |
| GET / DELETE | `/responses/:id` | viewer / editor: answers, transcript, metadata |

### Question object

```json
{ "type": "single_choice", "title": "How did you hear about us?", "description": "", "required": true,
  "options": { "choices": ["Search", "Friend", "Social"], "allow_other": false } }
```

Types: `short_text`, `long_text`, `single_choice`, `multiple_choice`, `dropdown`, `rating` (`options.min/max`, 0–10), `nps`, `yes_no`, `number`, `email`, `phone`, `date` (YYYY-MM-DD), `time` (HH:MM).

Stored answer values are normalized by type: choices become canonical option strings, `multiple_choice` becomes a string array, scales become integers, `yes_no` becomes a boolean.

### Survey settings

`modes` (`form` | `chat` | `voice`), `welcome_message`, `closing_message`, `agent {name, tone, instructions}`, `collect {name, email}`, `response_limit`, `notify_emails[]`, `show_branding`, `language`.

## Respondent (public) endpoints

No login. A response is authorized by the `response_token` returned when it starts, sent back as `X-Response-Token`.

| Method | Path | Notes |
|---|---|---|
| GET | `/public/plans` | Plan catalog |
| GET | `/public/surveys/:token` | Public survey view |
| POST | `/public/surveys/:token/responses` | `{channel: form\|chat\|voice, respondent?}`. Voice returns an ElevenLabs `signed_url` plus `dynamic_variables` |
| POST | `/public/responses/:id/answers` | Form mode: `{answers: {question_id: value}, complete}` |
| POST | `/public/responses/:id/chat` | Chat mode: `{message}` (omit it to get the opening message). Returns `{reply, completed, progress, transcript}` |
| GET | `/public/responses/:id` | Status polling |

## Billing

| Method | Path | Role |
|---|---|---|
| GET | `/billing` | viewer: subscription, plan, usage, catalog |
| POST | `/billing/checkout` | admin: `{plan: pro\|team}` returns a Stripe Checkout `url`. In dev mode the plan switches instantly |
| POST | `/billing/portal` | admin: Stripe Customer Portal `url` |

## Developers (Team plan)

| Method | Path |
|---|---|
| GET / POST / DELETE | `/api-keys`, `/api-keys/:id`. The plaintext key is returned once |
| GET / POST / PATCH / DELETE | `/webhooks`, `/webhooks/:id` |
| GET | `/webhooks/:id/secret` |
| POST | `/webhooks/:id/test` |

### Outbound webhook events

`response.completed`, `survey.published`, `survey.closed`. Payload:

```json
{ "id": "evt_…", "type": "response.completed", "created_at": "…Z", "data": { "id": "rsp_…", "answers": [ … ] } }
```

Verify `X-SurveyAgent-Signature: t=<unix>,v1=<hex>`, where `v1 = HMAC_SHA256(secret, "<t>.<raw body>")`. Reject stale timestamps. Endpoints are auto-disabled after 20 consecutive failures.

## Inbound integrations

| Path | Verified with |
|---|---|
| `POST /integrations/stripe/webhook` | `Stripe-Signature` |
| `POST /integrations/elevenlabs/post-call` | `elevenlabs-signature` HMAC |
| `POST /integrations/elevenlabs/inbound-call` | `elevenlabs-signature` HMAC |
