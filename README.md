# BrandLens

**AI-Assisted | Human-Controlled | Explainable Brand Governance**

BrandLens is an AI-powered brand compliance and content governance platform for text content—including marketing emails, blogs, landing page copy, social media posts, and press releases. 

A Brand Manager uploads the company's brand rulebook, content creators submit their copy (or upload `.txt`, `.pdf`, or `.docx` files), and BrandLens automatically checks the content for tone of voice, restricted terminology, numerical facts, and unsupported claims. Every issue is highlighted in-context with an explainable rationale and suggested replacement. The creator decides which fixes to accept, and a human reviewer gives final approval through an interactive side-by-side comparison screen.

---

## Core Workflow

```
[Brand Manager] Uploads Rulebook (JSON)
       │
       ▼
[Content Creator] Submits Content (Paste or .txt / .pdf / .docx Upload)
       │
       ▼
[Compliance Engine] Multi-layer Analysis
  ├── 🏷️ Terminology Check  (enforces approved words; avoids restricted terms)
  ├── 📊 Fact Check         (verifies statistics, founding years, and customer counts)
  ├── ⚖️ Claims Check       (detects unsourced superlatives, #1 rankings, and outcome promises)
  └── 🎙️ Tone Check         (analyzes brand voice alignment via Gemini AI with offline fallback)
       │
       ▼
[Content Creator] Reviews In-Context Findings
  ├── Accepts or rejects suggested rewrites
  └── Views real-time revised document preview
       │
       ▼
[Reviewer] Final Review & Sign-Off
  ├── Inspects side-by-side diff (Original vs. Revised)
  ├── Audits creator-rejected findings
  └── Approves content or Requests Changes with actionable feedback
```

### Content Status Flow
`draft` ➔ `reviewed` ➔ `pending_review` ➔ `approved` (or `changes_requested`)

---

## Project Structure

```
brandlens/
├── README.md                          # Documentation and setup guide
├── .gitignore                         # Git hygiene for dependencies and environment files
├── .env.example                       # Environment variable templates
│
├── sample_data/
│   ├── rulebook_sample.json           # Demo brand rulebook (tone, terms, facts, claims policy)
│   └── content_samples/
│       ├── blog_sample.txt            # Demo blog with planted compliance issues
│       ├── email_sample.txt           # Demo email with planted compliance issues
│       ├── social_post_sample.txt     # Demo social post with planted compliance issues
│       └── press_release_sample.txt   # Demo press release with planted compliance issues
│
├── backend/                           # FastAPI server (Python)
│   ├── requirements.txt               # Backend dependencies
│   ├── app/
│   │   ├── main.py                    # Server entrypoint, CORS configuration, router bindings
│   │   ├── config.py                  # Environment settings and secrets loader
│   │   ├── database.py                # MongoDB connection with in-memory fallback
│   │   ├── routes/                    # API endpoints
│   │   │   ├── auth.py                # Role-based demo JWT authentication
│   │   │   ├── rulebook.py            # Rulebook upload and active rulebook retrieval
│   │   │   ├── content.py             # Content creation, document extraction, listing
│   │   │   └── review.py              # Review execution, finding updates, reviewer decisions
│   │   ├── services/                  # Business logic and checkers
│   │   │   ├── text_extractor.py      # Extraction from .txt, .pdf, and .docx
│   │   │   ├── llm_client.py          # Google Gemini API integration and response parser
│   │   │   ├── terminology_checker.py # Case-preserving restricted term enforcement
│   │   │   ├── fact_checker.py        # Numerical and factual verification
│   │   │   ├── tone_checker.py        # Brand tone compliance check
│   │   │   ├── claim_checker.py       # Superlatives and evidence validation
│   │   │   ├── suggestion_engine.py   # Overlap resolution and backwards text patching
│   │   │   └── review_service.py      # Orchestrator, scoring algorithm, workflow gatekeeper
│   │   ├── schemas/                   # Pydantic v2 schemas
│   │   │   ├── rulebook.py            # Rulebook models
│   │   │   ├── content.py             # Content creation and response models
│   │   │   └── review.py              # Finding, review, and decision models
│   │   └── prompts/                   # System instructions for AI
│   │       ├── tone_prompt.txt        # Brand tone analysis prompt
│   │       └── claims_prompt.txt      # Unsupported claim analysis prompt
│   └── tests/
│       ├── test_checkers.py           # Unit tests for checkers against planted samples
│       └── test_api.py                # End-to-end API workflow tests
│
├── frontend/                          # Next.js web application (React)
│   ├── package.json                   # Dependencies and scripts
│   ├── .env.local.example             # Backend URL setting
│   ├── app/
│   │   ├── layout.js                  # Global frame with navigation and styling
│   │   ├── page.js                    # Auth-aware root router
│   │   ├── login/page.js              # Persona selection and login
│   │   ├── dashboard/page.js          # Role-adaptive analytics & review queue
│   │   ├── rulebook/page.js           # Rulebook editor and file upload
│   │   ├── upload/page.js             # Document upload / text input & review trigger
│   │   ├── review/[id]/page.js        # Interactive highlighted findings & suggestion accept/reject
│   │   └── reviewer/[id]/page.js      # Side-by-side diff comparison & sign-off
│   ├── components/
│   │   ├── Navbar.js                  # Top navigation with role indicators
│   │   ├── FindingCard.js             # Issue explanation card with actions
│   │   ├── HighlightedText.js         # Color-coded text highlighter by issue category
│   │   └── StatusBadge.js             # Status badge component
│   └── lib/
│       ├── api.js                     # Centralized API client with dual-stack loopback fallback
│       └── auth.js                    # Session persistence helpers
│
└── docs/
    ├── architecture.md                # System topology and tech stack details
    ├── workflow.md                    # Content state machine documentation
    └── api.md                         # Complete REST API reference
```

---
# BrandLens
🌐 **Live Demo**: (https://brand-lens-nine.vercel.app)]

## How to Run Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- *(Optional)* MongoDB running locally or a MongoDB Atlas connection string (an in-memory database will automatically be used if MongoDB is not present).

---

### 1. Backend Setup

```bash
cd brandlens/backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy example)
# On Windows:
copy .env.example .env
# On macOS / Linux:
cp .env.example .env

# Optional: Add your GEMINI_API_KEY into .env for live AI tone & claim checks

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Health check**: `http://localhost:8000/health` (returns `{"status":"ok"}`)
- **Interactive API Documentation**: `http://localhost:8000/docs`

---

### 2. Frontend Setup

In a new terminal window:

```bash
cd brandlens/frontend

# Install packages
npm install

# Configure environment
# On Windows:
copy .env.local.example .env.local
# On macOS / Linux:
cp .env.local.example .env.local

# Run the development server
npm run dev
```

- Open **`http://localhost:3000`** in your browser.

---

### 3. Run Automated Tests

BrandLens includes unit tests verifying each checker against planted compliance issues, as well as an end-to-end API workflow test suite:

```bash
cd brandlens/backend
python -m pytest -o pythonpath=. tests -v
```

---

## Demo Walkthrough

1. **Brand Manager Persona**:
   - Navigate to `/login` and select **Brand Manager**.
   - Go to **Rule Book** and upload `sample_data/rulebook_sample.json`.
   - The brand tone, restricted terms, approved terminology, numerical facts, and claims policy are now active.

2. **Content Creator Persona**:
   - Log out and log in as **Creator**.
   - Click **New Content**, select content type (e.g. *Blog* or *Email*).
   - Paste the text from `sample_data/content_samples/blog_sample.txt` (or upload the file directly) and click **Run Brand Review**.
   - Review each flagged issue:
     - 🏷️ **Terminology**: See why *"users"* should be replaced with *"customers"*.
     - 📊 **Fact**: Notice the mismatch between *"50,000 users"* and the rulebook's true count of *14,000*.
     - ⚖️ **Claim**: Review flags on unsupported superlatives like *"best analytics platform"* and promises of *"guaranteed results"*.
     - 🎙️ **Tone**: Spot hype-filled and pushy language.
   - Accept or reject each suggested replacement.
   - Watch the live **Revised version** update in real time.
   - Click **Send to Reviewer** once all issues are decided.

3. **Reviewer Persona**:
   - Log out and log in as **Reviewer**.
   - Open the submitted item from the **Review Queue**.
   - Compare the **Original** and **Revised** text side-by-side.
   - Review any creator-rejected findings flagged with clear warnings.
   - Click **Approve** (or enter a comment and click **Request Changes**).

---

## Deployment

### Backend (Render / Railway / GCP Cloud Run)
- **Root Directory**: `brandlens/backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**:
  - `GEMINI_API_KEY`: Google AI Studio API key
  - `GEMINI_MODEL`: `gemini-2.5-flash`
  - `FRONTEND_URL`: `*` (or your frontend deployment URL)
  - `JWT_SECRET`: Random 32+ character secret string
  - `MONGO_URI`: MongoDB Atlas connection string *(optional: defaults to in-memory store if unset)*

### Frontend (Vercel)
- **Root Directory**: `brandlens/frontend`
- **Framework Preset**: `Next.js`
- **Build Command**: `npm run build`
- **Environment Variables**:
  - `NEXT_PUBLIC_API_URL`: Your deployed backend URL (e.g. `https://brandlens-api.onrender.com`, no trailing slash)

---

## Team

- **Manya Saxena** — Frontend & Product Design
- **Sarthak Tripathi** — Backend Developer & AI Integration
