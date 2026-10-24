// frontend/lib/auth.js
// Saves, reads and clears the login token, role and name in the browser (localStorage).

const KEY = "brandlens_auth";

export function saveAuth(token, role, name) {
  localStorage.setItem(KEY, JSON.stringify({ token, role, name }));
}

export function getAuth() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearAuth() {
  localStorage.removeItem(KEY);
}
