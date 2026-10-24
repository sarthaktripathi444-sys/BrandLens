# config.py
# Reads all settings (database address, secret keys, frontend address) from environment variables.
# On your laptop they come from the backend/.env file; on a hosting service you set them in its dashboard.

import os
from pathlib import Path

from dotenv import load_dotenv

# The backend folder is where the local .env file lives.
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Load .env if it exists. Real environment variables always win over the file.
load_dotenv(BACKEND_DIR / ".env")


def _flag(name):
    """Turn an environment value like '1', 'true' or 'yes' into True."""
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


# ---- Database ----
# Local MongoDB by default. For MongoDB Atlas, paste its connection string into MONGO_URI.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "brandlens")
# Set USE_MEMORY_DB=1 to skip MongoDB and keep data in memory (resets on restart; fine for demos/tests).
USE_MEMORY_DB = _flag("USE_MEMORY_DB")

# ---- AI (Gemini) ----
# Never write the key in code. Without a key, tone and claims checks still work using built-in rules.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---- Login tokens ----
# CHANGE JWT_SECRET before deploying: anyone who knows it can create a valid login token.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-must-be-at-least-32-chars-long")
JWT_HOURS = int(os.getenv("JWT_HOURS", "12"))

# ---- CORS ----
# Address(es) of the website that may call this API. Several can be given, separated by commas.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Biggest file (in MB) accepted by the text-extraction endpoint.
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
