// frontend/app/rulebook/page.js
// Manager-only page to upload or paste the rule book JSON and see the active one.

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "../../lib/auth";
import { getActiveRulebook, saveRulebook } from "../../lib/api";

function validate(data) {
  if (!data || typeof data !== "object") return "The rule book must be a JSON object.";
  if (!data.company) return "Missing field: company";
  if (!Array.isArray(data.tone)) return "Missing field: tone (a list)";
  if (!Array.isArray(data.restricted_terms)) return "Missing field: restricted_terms (a list)";
  if (!Array.isArray(data.facts)) return "Missing field: facts (a list)";
  if (typeof data.claims_policy !== "string") return "Missing field: claims_policy (text)";
  return null;
}

export default function RulebookPage() {
  const router = useRouter();
  const [auth, setAuth] = useState(null);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const a = getAuth();
    if (!a) {
      router.replace("/login");
      return;
    }
    setAuth(a);

    // Load the rule book that is active right now (404 simply means none has been uploaded yet).
    getActiveRulebook()
      .then(setActive)
      .catch((e) => {
        if (e.status !== 404) setError(e.message);
      });
  }, [router]);

  if (!auth) return <div>Loading...</div>;
  if (auth.role !== "manager") {
    return <div className="card">Only brand managers can open this page. Log in as a Brand Manager.</div>;
  }

  function handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setDraft(reader.result);
    reader.readAsText(file);
  }

  // Checks the JSON, then sends it to the backend, which makes it the active rule book.
  async function handleSave() {
    setSaved(false);
    let data;
    try {
      data = JSON.parse(draft);
    } catch {
      setError("This is not valid JSON. Check for missing commas or quotes.");
      return;
    }
    const problem = validate(data);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setBusy(true);
    try {
      setActive(await saveRulebook(data));
      setSaved(true);
      setDraft("");
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  return (
    <div>
      <h2>Rule Book</h2>

      {!active && (
        <div className="card">No rule book has been uploaded yet. Upload one below.</div>
      )}

      {active && (
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Active rule book: {active.company}</h3>

        <strong>Tone</strong>
        <div style={{ margin: "6px 0 14px" }}>
          {active.tone.map((t) => (
            <span key={t} className="badge" style={{ background: "#ede9fe", color: "#5b21b6", marginRight: 6 }}>
              {t}
            </span>
          ))}
        </div>

        {active.approved_terms && active.approved_terms.length > 0 && (
          <>
            <strong>Approved terms</strong>
            <div style={{ margin: "6px 0 14px" }}>
              {active.approved_terms.map((t) => (
                <span key={t} className="badge" style={{ background: "#d1fae5", color: "#065f46", marginRight: 6 }}>
                  {t}
                </span>
              ))}
            </div>
          </>
        )}

        <strong>Restricted terms</strong>
        <div style={{ margin: "6px 0 14px", fontSize: 14 }}>
          {active.restricted_terms.map((r) => (
            <div key={r.term} style={{ marginBottom: 4 }}>
              "{r.term}" use "{r.use}" {r.reason && <>({r.reason})</>}
            </div>
          ))}
        </div>

        <strong>Facts</strong>
        <div style={{ margin: "6px 0 14px", fontSize: 14 }}>
          {active.facts.map((f) => (
            <div key={f.label} style={{ marginBottom: 4 }}>
              {f.label}: <strong>{f.value}</strong>
            </div>
          ))}
        </div>

        <strong>Claims policy</strong>
        <div style={{ marginTop: 6, fontSize: 14 }}>{active.claims_policy}</div>
      </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Upload a new rule book</h3>

        <label>Upload a .json file</label>
        <input type="file" accept=".json" onChange={handleFile} />

        <label>Or paste the JSON</label>
        <textarea
          rows={12}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder='{ "company": "NovaCart", "tone": [...], ... }'
          style={{ fontFamily: "monospace" }}
        />

        {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}
        {saved && <div style={{ color: "#065f46", marginTop: 10 }}>Rule book saved and set as active.</div>}

        <button className="btn" style={{ marginTop: 14 }} onClick={handleSave} disabled={busy}>
          {busy ? "Saving..." : "Save as active rule book"}
        </button>
      </div>
    </div>
  );
}
