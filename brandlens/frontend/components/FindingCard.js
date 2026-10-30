"use client";
// frontend/components/FindingCard.js
// Shows one flag: category badge, issue, reason, rule, selectable rewrites, Accept/Reject buttons.
// - onAccept(chosenWording): called with the rewrite the creator picked.
// - onReject(): reject the finding.
// - onMore(): async, asks the backend for more rewrites (the "Suggest more rewrites" button).
// Buttons are hidden when onAccept / onReject are not given (read-only view).

import { useState } from "react";

export const CATEGORY_COLORS = {
  tone: { bg: "#ede9fe", color: "#5b21b6" },
  terminology: { bg: "#dbeafe", color: "#1d4ed8" },
  fact: { bg: "#fef3c7", color: "#92400e" },
  claim: { bg: "#fee2e2", color: "#991b1b" },
  channel: { bg: "#d1fae5", color: "#065f46" },
};

const MAX_OPTIONS = 6; // same limit as the backend

export default function FindingCard({ finding, onAccept, onReject, onMore }) {
  const c = CATEGORY_COLORS[finding.category] || CATEGORY_COLORS.tone;
  const decided = finding.status !== "pending";

  // All wordings the creator can pick from (no empty ones, no duplicates).
  const options = [];
  [finding.suggestion, ...(finding.alternatives || [])].forEach((o) => {
    if (o && !options.includes(o)) options.push(o);
  });

  const [selected, setSelected] = useState(finding.replacement || finding.suggestion || "");
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState("");

  const chosen = options.includes(selected) ? selected : options[0] || "";

  async function handleMore() {
    setLoadingMore(true);
    setMoreError("");
    try {
      await onMore();
    } catch (error) {
      setMoreError(error.message || "Could not get more rewrites.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="card" style={{ opacity: finding.status === "rejected" ? 0.6 : 1 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
        <span className="badge" style={{ background: c.bg, color: c.color }}>
          {finding.category}
        </span>
        <strong>{finding.issue}</strong>
        {decided && (
          <span style={{ marginLeft: "auto", fontSize: 13 }}>
            {finding.status === "accepted" ? "Accepted" : "Rejected"}
          </span>
        )}
      </div>

      <div style={{ fontSize: 14, marginBottom: 4 }}>
        <strong>Found:</strong> <span style={{ background: c.bg }}>"{finding.text}"</span>
      </div>
      <div style={{ fontSize: 14, marginBottom: 4 }}><strong>Why:</strong> {finding.reason}</div>
      <div style={{ fontSize: 14, marginBottom: 8 }}><strong>Rule:</strong> {finding.rule}</div>

      {options.length === 0 && (
        <div style={{ fontSize: 14, marginBottom: 10 }}>
          <strong>Suggested fix:</strong> No automatic rewrite - fix this one by hand.
        </div>
      )}

      {options.length === 1 && (
        <div style={{ fontSize: 14, marginBottom: 10 }}>
          <strong>Suggested fix:</strong> "{options[0]}"
        </div>
      )}

      {options.length > 1 && (
        <fieldset style={{ border: "none", padding: 0, margin: "0 0 10px" }}>
          <legend style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Choose a rewrite:</legend>
          {options.map((option) => (
            <label key={option} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 14, marginBottom: 4, cursor: decided ? "default" : "pointer" }}>
              <input
                type="radio"
                name={`rewrite-${finding.id}`}
                checked={chosen === option}
                disabled={decided}
                onChange={() => setSelected(option)}
              />
              <span>"{option}"</span>
            </label>
          ))}
        </fieldset>
      )}

      {finding.status === "accepted" && finding.replacement && (
        <div style={{ fontSize: 13, marginBottom: 8 }}>Chosen wording: "{finding.replacement}"</div>
      )}

      {moreError && (
        <div style={{ fontSize: 13, color: "#991b1b", marginBottom: 8 }}>{moreError}</div>
      )}

      {onAccept && onReject && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            className="btn"
            onClick={() => onAccept(chosen || undefined)}
            disabled={finding.status === "accepted"}
          >
            Accept
          </button>
          <button className="btn secondary" onClick={onReject} disabled={finding.status === "rejected"}>
            Reject
          </button>
          {onMore && !decided && finding.suggestion && options.length < MAX_OPTIONS && (
            <button className="btn secondary" onClick={handleMore} disabled={loadingMore}>
              {loadingMore ? "Thinking..." : "Suggest more rewrites"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}