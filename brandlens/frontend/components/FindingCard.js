// frontend/components/FindingCard.js
// Shows one flag: coloured category badge, issue, reason, rule violated, suggested fix,
// alternative rewrite selector, and Accept/Reject buttons.
// When an alternative is chosen, Accept applies that specific replacement.

"use client";
import { useState } from "react";
import { getAlternatives } from "../lib/api";

export const CATEGORY_COLORS = {
  tone: { bg: "#ede9fe", color: "#5b21b6" },
  terminology: { bg: "#dbeafe", color: "#1d4ed8" },
  fact: { bg: "#fef3c7", color: "#92400e" },
  claim: { bg: "#fee2e2", color: "#991b1b" },
  channel: { bg: "#fce7f3", color: "#9d174d" },
};

export default function FindingCard({ finding, contentId, onAccept, onReject }) {
  const c = CATEGORY_COLORS[finding.category] || CATEGORY_COLORS.tone;
  const decided = finding.status !== "pending";

  const initialReplacement = finding.replacement || finding.suggestion || "";
  const [selectedReplacement, setSelectedReplacement] = useState(initialReplacement);
  const [alts, setAlts] = useState(finding.alternatives || []);
  const [loadingAlts, setLoadingAlts] = useState(false);
  const [altError, setAltError] = useState("");

  // Combine primary suggestion + any alternatives without duplicates
  const allChoices = Array.from(
    new Set([finding.suggestion, ...alts].filter((s) => s && s.trim()))
  );

  async function handleFetchAlternatives() {
    if (!contentId) return;
    setLoadingAlts(true);
    setAltError("");
    try {
      const res = await getAlternatives(contentId, finding.id);
      if (res && res.alternatives && res.alternatives.length > 0) {
        setAlts(res.alternatives);
        if (!selectedReplacement) {
          setSelectedReplacement(res.alternatives[0]);
        }
      } else {
        setAltError("No additional compliant alternatives found.");
      }
    } catch (err) {
      setAltError(err.message || "Could not generate alternatives.");
    } finally {
      setLoadingAlts(false);
    }
  }

  return (
    <div className="card" style={{ opacity: finding.status === "rejected" ? 0.6 : 1, marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="badge" style={{ background: c.bg, color: c.color, textTransform: "capitalize", fontWeight: 600 }}>
          {finding.category}
        </span>
        <strong>{finding.issue}</strong>
        {decided && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 13,
              fontWeight: 600,
              color: finding.status === "accepted" ? "#065f46" : "#991b1b",
              background: finding.status === "accepted" ? "#d1fae5" : "#fee2e2",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            {finding.status === "accepted" ? "Accepted" : "Rejected"}
          </span>
        )}
      </div>

      <div style={{ fontSize: 14, marginBottom: 4 }}>
        <strong>Found:</strong> <span style={{ background: c.bg, padding: "1px 6px", borderRadius: 3 }}>"{finding.text}"</span>
      </div>
      <div style={{ fontSize: 14, marginBottom: 4 }}><strong>Why:</strong> {finding.reason}</div>
      <div style={{ fontSize: 14, marginBottom: 6 }}><strong>Rule:</strong> {finding.rule}</div>

      {/* Suggested Fix and Alternatives Selection */}
      <div style={{ fontSize: 14, marginTop: 10, marginBottom: 12 }}>
        <strong>Suggested fix:</strong>{" "}
        {!decided && allChoices.length > 0 ? (
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 6 }}>
            {allChoices.map((choice, idx) => (
              <label
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  padding: "4px 8px",
                  borderRadius: 4,
                  background: selectedReplacement === choice ? "#f0fdf4" : "#f9fafb",
                  border: selectedReplacement === choice ? "1px solid #86efac" : "1px solid #e5e7eb",
                }}
              >
                <input
                  type="radio"
                  name={`replacement_${finding.id}`}
                  value={choice}
                  checked={selectedReplacement === choice}
                  onChange={() => setSelectedReplacement(choice)}
                />
                <span style={{ fontWeight: selectedReplacement === choice ? 600 : 400 }}>
                  "{choice}"
                  {idx === 0 && finding.suggestion === choice && (
                    <span style={{ fontSize: 11, color: "#6b7280", marginLeft: 6 }}>(primary)</span>
                  )}
                </span>
              </label>
            ))}
          </div>
        ) : decided ? (
          <span>
            {finding.status === "accepted" && (finding.replacement || finding.suggestion)
              ? `"${finding.replacement || finding.suggestion}"`
              : finding.suggestion
              ? `"${finding.suggestion}"`
              : "No automatic rewrite."}
          </span>
        ) : (
          <span>No automatic rewrite - fix this one by hand.</span>
        )}
      </div>

      {/* Alternatives generator button */}
      {!decided && contentId && onAccept && (
        <div style={{ marginBottom: 10 }}>
          <button
            type="button"
            className="btn secondary"
            style={{ fontSize: 12, padding: "3px 8px" }}
            onClick={handleFetchAlternatives}
            disabled={loadingAlts}
          >
            {loadingAlts ? "Generating compliant rewrites..." : "Suggest alternatives"}
          </button>
          {altError && <span style={{ color: "#c0392b", fontSize: 12, marginLeft: 8 }}>{altError}</span>}
        </div>
      )}

      {/* Action buttons */}
      {onAccept && onReject && (
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            type="button"
            className="btn"
            onClick={() => onAccept(selectedReplacement)}
            disabled={finding.status === "accepted"}
          >
            {allChoices.length > 1 ? "Accept Selected" : "Accept"}
          </button>
          <button
            type="button"
            className="btn secondary"
            onClick={onReject}
            disabled={finding.status === "rejected"}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
