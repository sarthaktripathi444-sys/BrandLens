# Architecture

```
Browser (Next.js, port 3000)
   |   fetch() with  Authorization: Bearer <token>        all calls live in frontend/lib/api.js
   v
FastAPI backend (port 8000)
   routes/   auth.py  rulebook.py  content.py  review.py     <- thin: check the role, read/write the database
   services/ review_service.py                               <- runs the 4 checks, score, workflow rules
             terminology_checker.py  fact_checker.py         <- plain Python, no AI
             claim_checker.py  tone_checker.py               <- built-in rules + AI
             llm_client.py                                   <- the ONLY file that talks to Gemini
             suggestion_engine.py  text_extractor.py         <- helpers
   |                         |
   v                         v
MongoDB (or in-memory)    Gemini API (optional)
rulebooks, contents,      prompts/tone_prompt.txt
reviews                   prompts/claims_prompt.txt
```

## Tech stack
- Frontend: Next.js 14 (JavaScript), plain CSS in `app/globals.css`
- Backend: FastAPI (Python), Pydantic schemas, PyJWT for the demo login
- Database: MongoDB (pymongo). Falls back to mongomock (in-memory) if MongoDB is unreachable
- AI: Gemini through the `google-genai` package. To switch to Azure OpenAI, change only `call_llm()` in `llm_client.py`

## Design decisions
- Everything the AI can do also has a built-in fallback, so the demo works with no key and no internet.
- AI answers are never trusted blindly: a finding is only kept if its quoted text really exists in the content.
- One review per content item; the URL id is always the content id.
- Login is a demo (pick a role, no password). It is enough to show the three roles, not for real security.

## Collections
- `rulebooks`: the uploaded rule book JSON + `active`, `updated`, `uploaded_by`
- `contents`: `id, title, type, text, status, score, owner, created_at, updated_at, final_text (after approval)`
- `reviews`: `content_id, findings[], comment, reviewed_by, created_at`
