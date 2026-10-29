# llm_client.py
# The ONLY file that talks to the AI (Gemini). To switch to Azure OpenAI or another AI,
# change call_llm() below; the rest of the project does not need to change.

import json
import re
from pathlib import Path

from app.config import GEMINI_API_KEY, GEMINI_MODEL

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class LLMError(Exception):
    """Raised when the AI cannot be used (no key, no internet, bad answer...)."""


def is_configured():
    """True when a Gemini key has been provided."""
    return bool(GEMINI_API_KEY.strip())


def load_prompt(filename, **values):
    """Read a prompt file, drop its '#' comment lines and fill the {placeholders}."""
    raw = (PROMPT_DIR / filename).read_text(encoding="utf-8")
    body = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("#"))
    for name, value in values.items():
        # .replace (not .format) so curly braces inside the user's text can never break the prompt
        body = body.replace("{" + name + "}", str(value))
    return body.strip()


def call_llm(prompt):
    """Send the prompt to Gemini and return its text answer. Tries fallback models if primary model is unavailable."""
    if not is_configured():
        raise LLMError("GEMINI_API_KEY is not set")
    try:
        from google import genai  # imported here so the app still starts if the package is missing

        client = genai.Client(api_key=GEMINI_API_KEY)
        models_to_try = [GEMINI_MODEL]
        for fallback in ("gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-3.5-flash"):
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error = None
        for m in models_to_try:
            try:
                response = client.models.generate_content(model=m, contents=prompt)
                return response.text or ""
            except Exception as err:
                last_error = err
                continue

        raise last_error or Exception("No Gemini models responded successfully.")
    except Exception as error:  # network, quota, wrong model name, missing package ...
        raise LLMError(f"Gemini call failed: {type(error).__name__}: {error}") from error


def parse_json_list(raw):
    """Pull a JSON list out of the AI's answer (it sometimes wraps it in ```json fences)."""
    cleaned = re.sub(r"```(?:json)?", "", raw or "").strip()
    first, last = cleaned.find("["), cleaned.rfind("]")
    if first == -1 or last == -1:
        raise LLMError("The AI did not return a JSON list")
    try:
        data = json.loads(cleaned[first : last + 1])
    except json.JSONDecodeError as error:
        raise LLMError("The AI returned invalid JSON") from error
    return [item for item in data if isinstance(item, dict)]


def ask_for_findings(prompt_file, **values):
    """Run a prompt and return the list of items the AI found. Raises LLMError if anything goes wrong."""
    return parse_json_list(call_llm(load_prompt(prompt_file, **values)))


def parse_json_object(raw):
    """Pull a JSON object out of the AI's answer (it sometimes wraps it in ```json fences)."""
    cleaned = re.sub(r"```(?:json)?", "", raw or "").strip()
    first, last = cleaned.find("{"), cleaned.rfind("}")
    if first == -1 or last == -1:
        raise LLMError("The AI did not return a JSON object")
    try:
        data = json.loads(cleaned[first : last + 1])
    except json.JSONDecodeError as error:
        raise LLMError("The AI returned invalid JSON") from error
    if not isinstance(data, dict):
        raise LLMError("The AI returned JSON, but not a JSON object")
    return data


def ask_for_json(prompt_file, **values):
    """Run a prompt and return the JSON object the AI returned. Raises LLMError if anything goes wrong."""
    return parse_json_object(call_llm(load_prompt(prompt_file, **values)))
