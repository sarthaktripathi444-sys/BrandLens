// frontend/lib/api.js
// All calls to the backend in one file (login, rulebook, content, review, decision).
// Pages never write fetch() themselves; they call the functions below.
// The backend address comes from NEXT_PUBLIC_API_URL (see .env.local.example).

import { getAuth, clearAuth } from "./auth";

let BASE = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

// The backend explains problems in "detail". This turns it into one readable sentence.
function readableError(detail, status) {
  if (typeof detail === "string") return detail;
  // A 422 (invalid data) sends a list like [{ loc: [...], msg: "..." }].
  if (Array.isArray(detail)) {
    return detail
      .map((d) => `${(d.loc || []).filter((p) => p !== "body").join(".")}: ${d.msg}`)
      .join("; ");
  }
  return `Request failed (status ${status})`;
}

// Sends one request, adds the login token, and returns the JSON answer.
// Throws an Error with a friendly message when something goes wrong.
async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  // Files are sent as FormData, which sets its own content type; everything else is JSON.
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const auth = getAuth();
  if (auth && auth.token) headers.Authorization = `Bearer ${auth.token}`;

  let response;
  try {
    response = await fetch(BASE + path, { ...options, headers });
  } catch {
    // If connecting to 127.0.0.1 or localhost fails, try the alternative loopback address
    let alternate = null;
    if (BASE.includes("localhost")) alternate = BASE.replace("localhost", "127.0.0.1");
    else if (BASE.includes("127.0.0.1")) alternate = BASE.replace("127.0.0.1", "localhost");

    if (alternate) {
      try {
        response = await fetch(alternate + path, { ...options, headers });
        BASE = alternate; // stick with the working address
      } catch {
        throw new Error(`Cannot reach the backend at ${BASE}. Make sure the FastAPI server is running on port 8000.`);
      }
    } else {
      throw new Error(`Cannot reach the backend at ${BASE}. Is it running?`);
    }
  }

  // Expired or missing login: forget it and go to the login page.
  if (response.status === 401 && !path.startsWith("/auth/")) {
    clearAuth();
    if (typeof window !== "undefined") window.location.href = "/login";
  }

  if (!response.ok) {
    let detail = null;
    try {
      detail = (await response.json()).detail;
    } catch {
      // The error had no JSON body; the status code message below is enough.
    }
    const error = new Error(readableError(detail, response.status));
    error.status = response.status;
    throw error;
  }
  return response.json();
}

const send = (method, body) => ({ method, body: JSON.stringify(body) });

// ---- Login ----
export const login = (role, name) => request("/auth/login", send("POST", { role, name }));

// ---- Rule book ----
export const getActiveRulebook = () => request("/rulebook/active");
export const saveRulebook = (rulebook) => request("/rulebook", send("POST", rulebook));

// ---- Content ----
export const listContent = () => request("/content");
export const createContent = (title, type, text) => request("/content", send("POST", { title, type, text }));
// Reads the text out of a .txt / .pdf / .docx file.
export const extractFile = (file) => {
  const form = new FormData();
  form.append("file", file);
  return request("/content/extract", { method: "POST", body: form });
};

// ---- Review (every call uses the CONTENT id) ----
export const runReview = (id, applyAccepted = false) =>
  request(`/review/${id}/run`, send("POST", { apply_accepted: applyAccepted }));
export const getReview = (id) => request(`/review/${id}`);
export const setFindingStatus = (id, findingId, status) =>
  request(`/review/${id}/findings/${findingId}`, send("PATCH", { status }));
export const sendToReviewer = (id) => request(`/review/${id}/send`, { method: "POST" });
export const submitDecision = (id, decision, comment) =>
  request(`/review/${id}/decision`, send("POST", { decision, comment: comment || "" }));
