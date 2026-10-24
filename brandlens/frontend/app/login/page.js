// frontend/app/login/page.js
// Login screen: choose a role (creator / manager / reviewer), call the login API, save token and role.

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveAuth } from "../../lib/auth";
import { login } from "../../lib/api";

const ROLES = [
  { value: "creator", label: "Creator", desc: "Upload content and fix flagged issues" },
  { value: "manager", label: "Brand Manager", desc: "Upload and manage the brand rule book" },
  { value: "reviewer", label: "Reviewer", desc: "Approve content or request changes" },
];

export default function LoginPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState("creator");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Asks the backend for a login token for the chosen role, saves it, then opens the dashboard.
  async function handleLogin() {
    setError("");
    setBusy(true);
    try {
      const data = await login(role, name.trim());
      saveAuth(data.token, data.role, data.name);
      router.push("/dashboard");
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 480, margin: "40px auto" }}>
      <h2 style={{ marginTop: 0 }}>Log in to BrandLens</h2>
      <p>Choose a role to continue (demo login, no password).</p>

      <label>Your name</label>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Manya" />

      <label>Role</label>
      {ROLES.map((r) => (
        <div
          key={r.value}
          onClick={() => setRole(r.value)}
          style={{
            border: role === r.value ? "2px solid #3b4a9c" : "1px solid #c8cce0",
            borderRadius: 8,
            padding: 12,
            marginBottom: 8,
            cursor: "pointer",
          }}
        >
          <strong>{r.label}</strong>
          <div style={{ fontSize: 13, color: "#555" }}>{r.desc}</div>
        </div>
      ))}

      {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}

      <button className="btn" style={{ marginTop: 12, width: "100%" }} onClick={handleLogin} disabled={busy}>
        {busy ? "Logging in..." : "Log in"}
      </button>
    </div>
  );
}
