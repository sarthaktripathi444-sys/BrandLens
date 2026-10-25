# main.py
# Starts the FastAPI server, allows the frontend to call it (CORS) and connects all the routers.

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import FRONTEND_URL
from app.database import close_database
from app.routes.auth import router as auth_router
from app.routes.content import router as content_router
from app.routes.review import router as review_router
from app.routes.rulebook import router as rulebook_router
from app.services.review_service import WorkflowError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_database()  # tidy up the database connection when the server stops


app = FastAPI(title="BrandLens API", lifespan=lifespan)

# Which websites may call this API. FRONTEND_URL can hold several addresses separated by commas.
# localhost and 127.0.0.1 are different origins for the browser, so both are allowed for local work.
if FRONTEND_URL.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = sorted(
        {url.strip().rstrip("/") for url in FRONTEND_URL.split(",") if url.strip()}
        | {"http://localhost:3000", "http://127.0.0.1:3000"}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(rulebook_router)
app.include_router(content_router)
app.include_router(review_router)


# Turn a workflow-rule problem (e.g. "decide all issues first") into a clean JSON error for the frontend.
@app.exception_handler(WorkflowError)
async def workflow_error_handler(request: Request, error: WorkflowError):
    return JSONResponse(status_code=error.status, content={"detail": error.message})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin") or "*"
    return JSONResponse(
        status_code=500,
        content={"detail": f"Server Error: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": origin},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
