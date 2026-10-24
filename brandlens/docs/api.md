# API Endpoints

Backend: FastAPI on http://localhost:8000. Interactive docs (try every endpoint in the browser): http://localhost:8000/docs

Every endpoint except `/health` and `/auth/login` needs the header `Authorization: Bearer <token>`.
`lib/api.js` adds it automatically. All errors come back as `{ "detail": "readable message" }`.

| Who | Method and path | What it does |
|---|---|---|
| Anyone | POST /auth/login | Body `{role, name}` (role = creator, manager or reviewer). Returns `{token, role, name}`. Demo login: no password. |
| Manager | POST /rulebook | Save a rule book (JSON) and make it the active one |
| Anyone logged in | GET /rulebook/active | Read the active rule book (404 if none yet) |
| Creator | POST /content | Body `{title, type, text}`. Saves content as a `draft` |
| Creator | POST /content/extract | Upload a .txt / .pdf / .docx (multipart field `file`); returns `{filename, text}`, saves nothing |
| Anyone logged in | GET /content | All content, newest first |
| Anyone logged in | GET /content/{id} | One content item |
| Creator | POST /review/{id}/run | Run the four checks. Body (optional) `{apply_accepted: true}` first applies accepted fixes, then checks again |
| Anyone logged in | GET /review/{id} | The review: content, findings, score, status, revised text |
| Creator | PATCH /review/{id}/findings/{finding_id} | Body `{status}` = accepted, rejected or pending |
| Creator | POST /review/{id}/send | Send to the reviewer (every finding must be accepted or rejected) |
| Reviewer | POST /review/{id}/decision | Body `{decision, comment}`; decision = approved or changes_requested (comment required for changes) |
| Anyone | GET /health | `{"status": "ok"}` |

`{id}` is always the CONTENT id (the `id` returned by POST /content).

## Shapes

Content: `id, title, type, text, status, score, owner, created_at, updated_at`
(`type` = Blog, Email, Social Post, Landing Page or Press Release; `score` is null until reviewed)

Finding: `id, category (terminology | tone | fact | claim), text, start, end, issue, reason, rule, suggestion, status (pending | accepted | rejected), source (rule | ai)`
`start`/`end` are character positions of `text` inside the content. An empty `suggestion` means "no automatic rewrite".

Review: `content_id, title, type, text, revised_text, score, status, findings, comment, reviewed_by`
`revised_text` is `text` with every ACCEPTED suggestion applied.

Rule book: `company, tone[], approved_terms[], restricted_terms[{term, use, reason}], facts[{label, aliases[], value}], claims_policy`
(plus `updated` when read back). See `sample_data/rulebook_sample.json`.

## Score

Starts at 100. Each finding subtracts points: fact 10, claim 10, tone 6, terminology 4 (minimum 0).
