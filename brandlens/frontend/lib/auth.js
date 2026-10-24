// frontend/lib/auth.js
// Saves, reads and clears the login token and role in the browser (localStorage).
// TODO: write saveAuth(), getAuth() and clearAuth().
const KEY = "brandlens_auth";

export function saveAuth(token, role, name) {
  localStorage.setItem(KEY, JSON.stringify({ token, role, name }));
}

export function getAuth() {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth() {
  localStorage.removeItem(KEY);
}