// frontend/app/rulebook/page.js
// Manager-only page to upload or paste the rule book JSON, auto-extract from guidelines with AI, and inspect schema completeness.

"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "../../lib/auth";
import { extractRulebook, getActiveRulebook, saveRulebook } from "../../lib/api";

function validate(data) {
  if (!data || typeof data !== "object") return "The rule book must be a valid JSON object.";
  if (!data.company || !data.company.trim()) return "Missing required field: 'company' (name of your organization).";
  if (!Array.isArray(data.tone) || data.tone.length === 0) return "Missing required field: 'tone' (a list of tone keywords, e.g. ['professional', 'trustworthy']).";
  if (!Array.isArray(data.restricted_terms)) return "Missing required field: 'restricted_terms' (must be a list; can be [] if none yet).";
  if (!Array.isArray(data.facts)) return "Missing required field: 'facts' (must be a list; can be [] if none yet).";
  if (typeof data.claims_policy !== "string") return "Missing required field: 'claims_policy' (text explaining claims standards).";
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

  // Feature 1: Auto-extraction states
  const [extracting, setExtracting] = useState(false);
  const [guidelineFile, setGuidelineFile] = useState(null);
  const [guidelineUrl, setGuidelineUrl] = useState("");
  const [extractError, setExtractError] = useState("");
  const [warnings, setWarnings] = useState([]);
  const [extractSuccess, setExtractSuccess] = useState("");
  const [showSchemaGuide, setShowSchemaGuide] = useState(false);

  useEffect(() => {
    const a = getAuth();
    if (!a) {
      router.replace("/login");
      return;
    }
    setAuth(a);

    // Load active rulebook
    getActiveRulebook()
      .then(setActive)
      .catch((e) => {
        if (e.status !== 404) setError(e.message);
      });
  }, [router]);

  // Real-time schema inspection on draft
  const schemaReport = useMemo(() => {
    if (!draft.trim()) return null;
    let data;
    try {
      data = JSON.parse(draft);
    } catch {
      return { validJson: false };
    }
    if (!data || typeof data !== "object") return { validJson: false };

    const companyOk = Boolean(data.company && data.company.trim() && data.company.toLowerCase() !== "brand");
    const toneOk = Array.isArray(data.tone) && data.tone.length > 0;
    const termsOk = Array.isArray(data.restricted_terms) && data.restricted_terms.length > 0;
    const factsOk = Array.isArray(data.facts) && data.facts.length > 0;
    const claimsOk = Boolean(typeof data.claims_policy === "string" && data.claims_policy.trim().length > 0);
    const messagingCount = Array.isArray(data.approved_messaging) ? data.approved_messaging.length : 0;
    const channelsCount = data.channel_rules && typeof data.channel_rules === "object" ? Object.keys(data.channel_rules).length : 0;

    const missingSections = [];
    if (!companyOk) missingSections.push("Company Name (update from 'Brand' to actual name)");
    if (!toneOk) missingSections.push("Brand Tone (2-4 voice adjectives)");
    if (!termsOk) missingSections.push("Restricted Terms (words to discourage/replace)");
    if (!factsOk) missingSections.push("Core Facts (company statistics, founding year)");
    if (!claimsOk) missingSections.push("Claims Policy (superlatives & guarantees rules)");

    return {
      validJson: true,
      data,
      company: { ok: companyOk, val: data.company || "" },
      tone: { ok: toneOk, count: Array.isArray(data.tone) ? data.tone.length : 0 },
      restrictedTerms: { ok: termsOk, count: Array.isArray(data.restricted_terms) ? data.restricted_terms.length : 0 },
      facts: { ok: factsOk, count: Array.isArray(data.facts) ? data.facts.length : 0 },
      claimsPolicy: { ok: claimsOk, text: data.claims_policy || "" },
      messaging: { count: messagingCount },
      channels: { count: channelsCount },
      missingSections,
    };
  }, [draft]);

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

  // Helper to inject missing schema sections into current draft
  function injectTemplate(key) {
    let current = {};
    try {
      if (draft.trim()) current = JSON.parse(draft);
    } catch {
      current = {};
    }

    if (key === "facts") {
      current.facts = current.facts || [];
      current.facts.push({
        label: "active customers",
        aliases: ["customers", "clients"],
        value: 10000,
        source_quote: "Verified metric from internal records"
      });
    } else if (key === "restricted_terms") {
      current.restricted_terms = current.restricted_terms || [];
      current.restricted_terms.push({
        term: "cheap",
        use: "affordable",
        reason: "Sounds low quality",
        source_quote: ""
      });
    } else if (key === "claims_policy") {
      current.claims_policy = current.claims_policy || "No unsupported superlatives (best, #1, revolutionary) and no guaranteed outcomes unless backed by verifiable evidence.";
    } else if (key === "approved_messaging") {
      current.approved_messaging = current.approved_messaging || [];
      current.approved_messaging.push({
        text: "Built for trust and excellence",
        context: "Landing pages and email footers",
        source_quote: ""
      });
    }

    setDraft(JSON.stringify(current, null, 2));
  }

  // Feature 1: Call Gemini to auto-extract rulebook from PDF/DOCX/TXT file or URL
  async function handleAutoExtract() {
    setExtractError("");
    setExtractSuccess("");
    setWarnings([]);

    if (!guidelineFile && !guidelineUrl.trim()) {
      setExtractError("Please select a file or enter a web page URL.");
      return;
    }

    setExtracting(true);
    try {
      const result = await extractRulebook({
        file: guidelineFile || undefined,
        url: guidelineUrl.trim() || undefined,
      });

      if (result && result.draft) {
        setDraft(JSON.stringify(result.draft, null, 2));
        setWarnings(result.warnings || []);
        setExtractSuccess(`Draft rule book extracted from ${result.source || "guidelines"}! Check the Schema Guidance below to verify and fill any missing details.`);
      } else {
        setExtractError("No draft rule book could be generated.");
      }
    } catch (e) {
      setExtractError(e.message || "Failed to extract rule book.");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSave() {
    setSaved(false);
    let data;
    try {
      data = JSON.parse(draft);
    } catch {
      setError("This is not valid JSON. Check for missing commas, brackets, or quotes.");
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
      setWarnings([]);
      setExtractSuccess("");
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  // Categorize extraction warnings into factual warnings vs schema guidance
  const schemaGuidanceWarnings = warnings.filter((w) => w.startsWith("Schema Guidance:"));
  const factWarnings = warnings.filter((w) => w.startsWith("Fact '"));
  const otherWarnings = warnings.filter((w) => !w.startsWith("Schema Guidance:") && !w.startsWith("Fact '"));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Brand Rule Book</h2>
        <button
          className="btn secondary"
          style={{ fontSize: 13, padding: "6px 12px" }}
          onClick={() => setShowSchemaGuide(!showSchemaGuide)}
        >
          {showSchemaGuide ? "Hide Schema Guide" : "View Schema Guide & Best Practices"}
        </button>
      </div>

      {showSchemaGuide && (
        <div className="card" style={{ background: "#f8fafc", border: "1px solid #cbd5e1", fontSize: 14 }}>
          <h3 style={{ marginTop: 0, color: "#1e293b" }}>Essential Rule Book Schema Architecture</h3>
          <p style={{ color: "#475569" }}>
            A comprehensive brand rulebook configures the automated compliance checkers. Here is what each schema section does:
          </p>
          <ul style={{ paddingLeft: 20, color: "#334155", lineHeight: 1.6 }}>
            <li>
              <strong><code>company</code> (String, Required):</strong> The name of the organization. Used to identify the brand across reviews and compliance certificates.
            </li>
            <li>
              <strong><code>tone</code> (Array of Strings, Required):</strong> 2–4 adjectives (e.g. <code>[&quot;professional&quot;, &quot;trustworthy&quot;]</code>). The tone checker checks content against these and flags aggressive or hype language.
            </li>
            <li>
              <strong><code>restricted_terms</code> (Array of Objects, Required):</strong> Prohibited or discouraged words and their replacements. Each item has <code>term</code>, <code>use</code> (replacement, or &quot;&quot; if strictly prohibited), and <code>reason</code>.
            </li>
            <li>
              <strong><code>facts</code> (Array of Objects, Required):</strong> Verified brand metrics (e.g. active customer count, founding year). The fact checker verifies any numeric claim in content against these exact numbers.
            </li>
            <li>
              <strong><code>claims_policy</code> (String, Required):</strong> Policy on claims, superlatives (&quot;#1&quot;, &quot;best&quot;), or guarantees. The AI claim checker uses this policy to catch unsubstantiated promises.
            </li>
            <li>
              <strong><code>approved_messaging</code> (Array of Objects, Optional):</strong> Approved taglines, mission statements, or slogans that creators are encouraged to use.
            </li>
            <li>
              <strong><code>channel_rules</code> (Object, Optional):</strong> Custom rules per channel (e.g. max characters for Ads, subject line limits for Emails).
            </li>
          </ul>
        </div>
      )}

      {!active && (
        <div className="card">No rule book has been uploaded yet. Upload or extract one below.</div>
      )}

      {active && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            Active rule book: {active.company}
            {active.version ? ` (v${active.version})` : ""}
          </h3>

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

          {active.approved_messaging && active.approved_messaging.length > 0 && (
            <>
              <strong>Approved messaging</strong>
              <div style={{ margin: "6px 0 14px", fontSize: 14 }}>
                {active.approved_messaging.map((m, idx) => (
                  <div key={idx} style={{ marginBottom: 4 }}>
                    &ldquo;{m.text}&rdquo; {m.context && <><em>({m.context})</em></>}
                  </div>
                ))}
              </div>
            </>
          )}

          <strong>Restricted terms ({active.restricted_terms.length})</strong>
          <div style={{ margin: "6px 0 14px", fontSize: 14 }}>
            {active.restricted_terms.map((r) => (
              <div key={r.term} style={{ marginBottom: 4 }}>
                &ldquo;{r.term}&rdquo; &rarr; use &ldquo;{r.use}&rdquo; {r.reason && <>({r.reason})</>}
              </div>
            ))}
          </div>

          <strong>Facts ({active.facts.length})</strong>
          <div style={{ margin: "6px 0 14px", fontSize: 14 }}>
            {active.facts.map((f) => (
              <div key={f.label} style={{ marginBottom: 4 }}>
                {f.label}: <strong>{String(f.value)}</strong>
              </div>
            ))}
          </div>

          <strong>Claims policy</strong>
          <div style={{ marginTop: 6, fontSize: 14 }}>{active.claims_policy}</div>
        </div>
      )}

      {/* Feature 1: Auto-extract from guidelines card */}
      <div className="card" style={{ borderLeft: "4px solid #3b4a9c" }}>
        <h3 style={{ marginTop: 0 }}>Auto-extract from guidelines</h3>
        <p style={{ fontSize: 14, color: "#555", marginTop: 4 }}>
          Upload existing guidelines (PDF, DOCX, TXT) or paste a web address.
          Gemini extracts the brand rules into the required schema. If any core schema details are missing from the uploaded document, you will be guided below to complete them.
        </p>

        <label>Upload guidelines file (.pdf, .docx, .txt)</label>
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => setGuidelineFile(e.target.files[0] || null)}
          disabled={extracting}
        />

        <label>Or enter guidelines web page URL</label>
        <input
          type="url"
          placeholder="https://example.com/brand-guidelines"
          value={guidelineUrl}
          onChange={(e) => setGuidelineUrl(e.target.value)}
          disabled={extracting}
        />

        {extractError && (
          <div style={{ color: "#c0392b", marginTop: 10, fontSize: 14 }}>
            {extractError}
          </div>
        )}

        {extractSuccess && (
          <div style={{ color: "#065f46", marginTop: 10, fontSize: 14, fontWeight: 500 }}>
            {extractSuccess}
          </div>
        )}

        {/* Schema Gaps identified in source document */}
        {schemaGuidanceWarnings.length > 0 && (
          <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: 12, marginTop: 12 }}>
            <strong style={{ color: "#1e40af", fontSize: 14 }}>Schema Gaps Found in Document:</strong>
            <p style={{ margin: "4px 0 8px", fontSize: 13, color: "#1e3a8a" }}>
              The uploaded document did not define all baseline schema fields. Review and add them to the editor below:
            </p>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "#1d4ed8" }}>
              {schemaGuidanceWarnings.map((w, idx) => (
                <li key={idx} style={{ marginBottom: 4 }}>
                  {w.replace("Schema Guidance: ", "")}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Fact verification warnings */}
        {factWarnings.length > 0 && (
          <div style={{ background: "#fffbeb", border: "1px solid #fef3c7", borderRadius: 8, padding: 12, marginTop: 12 }}>
            <strong style={{ color: "#92400e", fontSize: 14 }}>Fact Verification Warnings:</strong>
            <ul style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 13, color: "#78350f" }}>
              {factWarnings.map((w, idx) => (
                <li key={idx} style={{ marginBottom: 4 }}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {otherWarnings.length > 0 && (
          <div style={{ fontSize: 13, color: "#64748b", marginTop: 8 }}>
            {otherWarnings.join(" ")}
          </div>
        )}

        <button
          className="btn"
          style={{ marginTop: 14 }}
          onClick={handleAutoExtract}
          disabled={extracting || (!guidelineFile && !guidelineUrl.trim())}
        >
          {extracting ? "Extracting rules with AI..." : "Extract draft rule book"}
        </button>
      </div>

      {/* Real-time Schema Completeness & Guidance Panel */}
      {schemaReport && schemaReport.validJson && (
        <div className="card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>Schema Completeness Checklist</h3>
            <span style={{ fontSize: 12, color: schemaReport.missingSections.length === 0 ? "#15803d" : "#b45309", fontWeight: 600 }}>
              {schemaReport.missingSections.length === 0
                ? "✓ All Essential Schemas Defined"
                : `${schemaReport.missingSections.length} Schema Area(s) Need Attention`}
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10, marginTop: 12, fontSize: 13 }}>
            <div style={{ padding: "8px 10px", background: "#fff", borderRadius: 6, border: "1px solid #e2e8f0" }}>
              <strong>Company:</strong> {schemaReport.company.ok ? <span style={{ color: "#16a34a" }}>✓ {schemaReport.company.val}</span> : <span style={{ color: "#dc2626" }}>⚠️ Missing</span>}
            </div>
            <div style={{ padding: "8px 10px", background: "#fff", borderRadius: 6, border: "1px solid #e2e8f0" }}>
              <strong>Tone:</strong> {schemaReport.tone.ok ? <span style={{ color: "#16a34a" }}>✓ {schemaReport.tone.count} defined</span> : <span style={{ color: "#dc2626" }}>⚠️ Empty</span>}
            </div>
            <div style={{ padding: "8px 10px", background: "#fff", borderRadius: 6, border: "1px solid #e2e8f0" }}>
              <strong>Restricted Terms:</strong> {schemaReport.restrictedTerms.ok ? <span style={{ color: "#16a34a" }}>✓ {schemaReport.restrictedTerms.count} defined</span> : <span style={{ color: "#d97706" }}>⚠️ None</span>}
            </div>
            <div style={{ padding: "8px 10px", background: "#fff", borderRadius: 6, border: "1px solid #e2e8f0" }}>
              <strong>Facts:</strong> {schemaReport.facts.ok ? <span style={{ color: "#16a34a" }}>✓ {schemaReport.facts.count} defined</span> : <span style={{ color: "#d97706" }}>⚠️ None</span>}
            </div>
            <div style={{ padding: "8px 10px", background: "#fff", borderRadius: 6, border: "1px solid #e2e8f0" }}>
              <strong>Claims Policy:</strong> {schemaReport.claimsPolicy.ok ? <span style={{ color: "#16a34a" }}>✓ Set</span> : <span style={{ color: "#dc2626" }}>⚠️ Empty</span>}
            </div>
          </div>

          {schemaReport.missingSections.length > 0 && (
            <div style={{ marginTop: 12, padding: "8px 12px", background: "#fffbeb", borderRadius: 6, fontSize: 13, border: "1px solid #fef3c7" }}>
              <strong style={{ color: "#92400e" }}>Quick Template Inserters for Missing Details:</strong>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
                {!schemaReport.facts.ok && (
                  <button className="btn secondary" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => injectTemplate("facts")}>
                    + Add Sample Fact
                  </button>
                )}
                {!schemaReport.restrictedTerms.ok && (
                  <button className="btn secondary" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => injectTemplate("restricted_terms")}>
                    + Add Sample Restricted Term
                  </button>
                )}
                {!schemaReport.claimsPolicy.ok && (
                  <button className="btn secondary" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => injectTemplate("claims_policy")}>
                    + Add Default Claims Policy
                  </button>
                )}
                {schemaReport.messaging.count === 0 && (
                  <button className="btn secondary" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => injectTemplate("approved_messaging")}>
                    + Add Approved Messaging Template
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Review &amp; save rule book</h3>

        <label>Or load an existing .json rule book file</label>
        <input type="file" accept=".json" onChange={handleFile} />

        <label>Rule book JSON (edit or paste)</label>
        <textarea
          rows={14}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder='{ "company": "NovaCart", "tone": [...], ... }'
          style={{ fontFamily: "monospace", fontSize: 13 }}
        />

        {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}
        {saved && <div style={{ color: "#065f46", marginTop: 10 }}>Rule book saved and set as active.</div>}

        <button className="btn" style={{ marginTop: 14 }} onClick={handleSave} disabled={busy || !draft.trim()}>
          {busy ? "Saving..." : "Save as active rule book"}
        </button>
      </div>
    </div>
  );
}
