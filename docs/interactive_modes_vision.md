# Interactive Modes — Future Addition (Design Notes)

## Vision
Three interactive chat modes powered by `gemini-3-flash-live` (unlimited tier, high throughput) + optional `gemini-3.1-flash-tts` for audio. SSE streaming for token-by-token response. All modes use the same chat infrastructure but differ in system prompt and context injection.

## Models Considered

| Model | Purpose |
|-------|---------|
| `gemini-3-flash-live` | Chat text generation — unlimited requests, 65K RPM. SSE streaming via `generate_content_stream`. |
| `gemini-3.1-flash-tts` | Text-to-speech for "Read aloud" feature on AI responses (future). |

## Architecture Approach
- Backend SSE streaming (FastAPI `StreamingResponse`)
- Frontend `fetch()` with `ReadableStream` for incremental rendering
- Chat history stored in `ChatSession` + `ChatMessage` tables
- Full conversation memory sent each turn (last N messages)
- No rate limit pacing needed (unlimited tier)

## Modes

### 1. Coach Mode (💬)
- Open-ended chat with an AI UPSC coach
- Student profile auto-injected (ELO, weak areas, subject accuracy, trap stats)
- **Open questions:**
  - Proactive (coach greets with suggestions based on weak areas) or reactive (wait for student)?
  - Personality: friendly explainer or strict tutor?
  - Should coach challenge student ("What do you already know?") before explaining?
  - Should it reference personal data explicitly (ELO changes, diagnostic results)?

### 2. Learning Mode (📚)
- Structured topic-based interactive learning
- **Two possible flows discussed:**

| | Tutor-led (proactive) | Student-led (reactive) |
|---|---|---|
| Start | AI picks topic, asks first question | Student picks topic, asks anything |
| Flow | Q → Student answers → AI explains + follow-up → repeat | Student asks doubts, AI explains |
| End | After N questions or student leaves | Student leaves |

- **Open questions:**
  - Which flow (or mix of both)?
  - Should difficulty adapt to ELO?
  - Show mid-session progress ("3/5 correct")?
  - How does session end? Fixed questions, timer, or student decides?

### 3. CA Discussion Mode (📰)
- Interactive discussion about a specific current affairs article
- Student selects an article from the list → AI has full context (title, summary, key_facts, historical_context)
- **Three approaches discussed:**
  - A: AI briefs first ("This relates to GS2..."), then opens floor
  - B: AI quizzes student ("What's your understanding?") to gauge knowledge
  - C: Pure Q&A like Coach mode
- Should AI explicitly map the article to GS syllabus papers?

## Cross-Cutting Design Questions

- **Memory**: Should the coach remember you across days ("Last time we discussed Polity...") or is each session fresh?
- **Session model**: Like ChatGPT (single continuous thread) or separate titled sessions browsable later?
- **Learning mode — first move**: Should AI proactively ask the first question when a topic is selected, or wait for the student?

## Implementation Notes (Technical)

When ready:
- New models: `ChatSession`, `ChatMessage` in `models.py`
- New file: `chat_engine.py` — context builder + streaming logic
- New API layer: `"chat"` model in `model_config.py`, no pacing in `api_guardrail.py`
- 4 endpoints: `POST /chat/session`, `GET /chat/sessions`, `GET /chat/{id}/messages`, `POST /chat/{id}/message` (SSE)
- Frontend: `InteractiveChat.jsx` with 3 tabs, SSE reader, session panel
- Sidebar link + route in `App.jsx`
- "Discuss this article" button on `CADetail.jsx`

## Files to Create/Modify (When Implemented)

| File | Action |
|------|--------|
| `backend/model_config.py` | Add `chat` layer |
| `backend/api_guardrail.py` | Add `execute_direct_call()` (no pacing) |
| `backend/models.py` | Add `ChatSession`, `ChatMessage` tables |
| `backend/chat_engine.py` | New — streaming logic |
| `backend/main.py` | 4 chat endpoints |
| `frontend/.../InteractiveChat.jsx` | New — full chat UI |
| `frontend/.../CADetail.jsx` | Add "Discuss" button |
| `frontend/.../App.jsx` | Add route |
| `frontend/.../Sidebar.jsx` | Add nav item |
