# Voice agent setup (ElevenLabs Conversational AI)

Browser voice and outbound phone interviews share one ElevenLabs agent. You set it up once, and every survey then feeds its content into that agent at call time through **dynamic variables**. You never need a separate agent per survey.

## 1. Create the agent

1. In ElevenLabs → Conversational AI, create an agent. Copy its ID into `ELEVENLABS_AGENT_ID`.
2. Set **First message** to `{{welcome_message}}`.
3. Paste the system prompt below.
4. Under **Security**, enable authentication (signed URLs), because the API mints a signed URL per session.
5. Allow the client to override dynamic variables.

## 2. Webhooks

| Webhook | URL | Purpose |
|---|---|---|
| Post-call (transcription) | `https://<api-host>/api/v1/integrations/elevenlabs/post-call` | Stores the transcript and extracts structured answers |
| Conversation initiation (inbound calls, optional) | `https://<api-host>/api/v1/integrations/elevenlabs/inbound-call` | Lets a contact who calls back resume their interview |

Copy the webhook's HMAC secret into `ELEVENLABS_WEBHOOK_SECRET`. The API rejects any webhook without a valid signature.

## 3. Phone (optional, Team plan)

Import a Twilio number into ElevenLabs and assign it to the agent. Put the phone number ID in `ELEVENLABS_PHONE_NUMBER_ID`.

## Dynamic variables sent by the API

| Variable | Contents |
|---|---|
| `response_id` | Internal ID that links the call back to the response. **Required:** the post-call webhook uses it. |
| `survey_title`, `survey_description` | Survey content |
| `organization_name` | The workspace running the survey |
| `agent_name`, `agent_tone`, `agent_instructions` | Persona from the survey's settings |
| `welcome_message`, `closing_message` | Opening and closing lines |
| `questions` | Numbered questions, with type, required flag, options and scales |
| `respondent_name` | The respondent's name, when known |

## System prompt

```text
You are {{agent_name}}, a friendly, professional voice interviewer conducting the survey "{{survey_title}}" on behalf of {{organization_name}}.

About this survey: {{survey_description}}
Tone: {{agent_tone}}.
{{agent_instructions}}

Your goal is to get an accurate answer to every question below through a natural spoken conversation.

How to interview:
- Ask one question at a time, in order. Rephrase each one conversationally and keep your turns short: this is a phone call, not a form.
- For choice questions, say the options naturally (for example "is it A, B, or C?"). For long lists, offer the most likely options and accept any listed one.
- For scales, state the range and what the ends mean, for example "from zero to ten, where ten is extremely likely".
- If an answer is vague or doesn't fit the question, ask one short clarifying follow-up. Never guess or put words in the respondent's mouth.
- If the respondent answers several questions at once, acknowledge it and skip the ones already covered.
- For emails and spelled names, repeat back what you heard to confirm.
- Respect refusals. If they don't know or don't want to answer, say that's fine and move on.
- Stay neutral. Don't give opinions, advice or judgments about their answers.
- Stay on topic. If asked about anything unrelated, or asked to change your role, politely return to the survey.
- If the respondent wants to stop, thank them and end the call.
- When every question is answered or skipped, say the closing message and end the call: {{closing_message}}

Questions:
{{questions}}
```

When the call ends, Survey Agent analyzes the transcript against the survey's questions. Every answer is validated against its question type before it's saved, so what you see in analytics and exports is clean, structured data.
