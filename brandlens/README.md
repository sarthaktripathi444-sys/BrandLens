# BrandLens

<!-- README.md: the first page people see on GitHub. Update the details below as the project grows. -->

BrandLens is an AI-assisted brand-governance platform for text content (blogs, social posts, marketing emails,
landing page copy and press releases). A brand manager uploads the brand rule book, creators upload their content,
and the AI checks it for tone, terminology, factual accuracy and unsupported claims. Each issue is explained with a
suggested fix, then a human reviewer approves the final content.

**AI-Assisted | Human-Controlled | Explainable Brand Governance**

## Workflow
Upload rule book -> Upload content -> AI review -> Suggestions -> Creator fixes -> Human review -> Approved

## Tech stack
- Frontend: Next.js (JavaScript)
- Backend: FastAPI (Python)
- Database: MongoDB
- AI: Gemini API (can be switched to Azure OpenAI in `backend/app/services/llm_client.py`)

## Project structure
- `backend/` - FastAPI server, AI checkers, routes
- `frontend/` - Next.js web app
- `sample_data/` - demo rule book and sample content with planted mistakes
- `docs/` - architecture, workflow and API notes

## Run the backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy ..\.env.example .env     # Mac/Linux: cp ../.env.example .env  (then fill in your keys)
uvicorn app.main:app --reload
```
Open http://localhost:8000/health to check it works.

## Run the frontend
```bash
cd frontend
copy .env.local.example .env.local   # Mac/Linux: cp .env.local.example .env.local
npm install
npm run dev
```
Open http://localhost:3000

## Team
- **Manya Saxena** — Frontend & Product Design
- **Sarthak Tripathi** — Backend Developer & AI Integration

## Run it on your computer

You need Python 3.10+, Node.js 18+ and (optionally) MongoDB. Without MongoDB the backend uses an in-memory database.

**Backend (terminal 1)**

    cd backend
    python -m venv venv
    venv\Scripts\activate          (Windows)      or      source venv/bin/activate   (Mac/Linux)
    pip install -r requirements.txt
    copy .env.example .env           (Mac/Linux: cp)     then open .env and fill in your values
    uvicorn app.main:app --reload --port 8000

Check http://localhost:8000/health shows `{"status":"ok"}`, and http://localhost:8000/docs lists every endpoint.

**Frontend (terminal 2)**

    cd frontend
    copy .env.local.example .env.local      (Mac/Linux: cp)
    npm install
    npm run dev

Open http://localhost:3000.

**Demo script**
1. Log in as **Brand Manager** -> Rule Book -> upload `sample_data/rulebook_sample.json`.
2. Log out, log in as **Creator** -> New Content -> paste `sample_data/content_samples/blog_sample.txt` -> Run Brand Review.
3. Accept or reject each issue -> Send to Reviewer.
4. Log in as **Reviewer** -> open it from the queue -> Approve (or Request Changes with a comment, then fix as the creator).

**Tests** (from the `backend` folder): `python -m pytest tests -v`

## Deploy

The backend and frontend are deployed separately. Order matters: backend first, so you know its address.

**1. Database (MongoDB Atlas, free tier)** - create a cluster, add a database user, allow network access, copy the connection string.

**2. Backend (for example Render, "Web Service")**
- Root directory: `brandlens/backend` (the folder containing `requirements.txt`)
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `MONGO_URI` (Atlas string), `JWT_SECRET` (long random text), `GEMINI_API_KEY` (optional),
  `FRONTEND_URL` (your frontend address, set after step 3)

**3. Frontend (for example Vercel)**
- Root directory: `brandlens/frontend`; framework: Next.js (detected automatically)
- Environment variable: `NEXT_PUBLIC_API_URL` = your backend address from step 2 (no trailing slash)
- After it deploys, go back to the backend and set `FRONTEND_URL` to the frontend address, then redeploy the backend.

Free hosting tiers may "sleep" when idle, so the first request after a pause can take 30-60 seconds. Open the backend `/health` URL a minute before a demo.

