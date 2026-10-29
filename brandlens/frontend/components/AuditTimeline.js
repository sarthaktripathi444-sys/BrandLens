// frontend/components/AuditTimeline.js
// Feature 3: Visual Audit Trail & Cryptographic Chain Timeline (Person A)
// Displays chronological events with sequence number, action type, actor,
// timestamp, structured metadata, and cryptographic SHA-256 block hashes.

"use client";
import { useState } from "react";

const ACTION_LABELS = {
  content_created: { label: "Content Created", color: "#1d4ed8", bg: "#dbeafe" },
  review_run: { label: "AI Review Run", color: "#6b21a8", bg: "#f3e8ff" },
  finding_decided: { label: "Finding Decided", color: "#b45309", bg: "#fef3c7" },
  sent_to_reviewer: { label: "Sent to Reviewer", color: "#4338ca", bg: "#e0e7ff" },
  decision_made: { label: "Reviewer Decision", color: "#065f46", bg: "#d1fae5" },
  rulebook_saved: { label: "Rulebook Saved", color: "#0f766e", bg: "#ccfbf1" },
};

export default function AuditTimeline({ events = [], chainValid = false }) {
  const [expandedHashes, setExpandedHashes] = useState({});

  const toggleHash = (idx) => {
    setExpandedHashes((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const formatTimestamp = (ts) => {
    if (!ts) return "—";
    try {
      return new Date(ts).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return ts;
    }
  };

  const truncateHash = (hash, len = 8) => {
    if (!hash) return "—";
    if (hash.length <= len * 2 + 3) return hash;
    return `${hash.slice(0, len)}...${hash.slice(-len)}`;
  };

  return (
    <div style={{ marginTop: 20 }}>
      {/* Cryptographic Chain Integrity Banner */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 18px",
          borderRadius: 8,
          marginBottom: 20,
          background: chainValid ? "#ecfdf5" : "#fef2f2",
          border: `1px solid ${chainValid ? "#a7f3d0" : "#fecaca"}`,
          color: chainValid ? "#065f46" : "#991b1b",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20 }}>{chainValid ? "🛡️" : "⚠️"}</span>
          <div>
            <strong>
              {chainValid
                ? "Cryptographic Hash Chain Verified"
                : "Cryptographic Chain Unverified or Tampered"}
            </strong>
            <div style={{ fontSize: 13, marginTop: 2, opacity: 0.9 }}>
              {chainValid
                ? "Every event is cryptographically linked via SHA-256. Tamper-evident ledger integrity confirmed."
                : "The sequence hashes could not be fully verified against the immutable block chain."}
            </div>
          </div>
        </div>
        <span
          className="badge"
          style={{
            background: chainValid ? "#10b981" : "#ef4444",
            color: "#fff",
            fontSize: 12,
            padding: "4px 12px",
          }}
        >
          {chainValid ? "CHAIN VALID" : "INVALID / UNCHECKED"}
        </span>
      </div>

      {/* Events List */}
      {(!events || events.length === 0) ? (
        <div className="card" style={{ textAlign: "center", padding: "30px 20px", color: "#666" }}>
          No audit events recorded yet for this content item.
        </div>
      ) : (
        <div style={{ position: "relative", paddingLeft: 24 }}>
          {/* Vertical timeline spine */}
          <div
            style={{
              position: "absolute",
              top: 10,
              bottom: 10,
              left: 10,
              width: 3,
              background: "#cbd5e1",
              borderRadius: 2,
            }}
          />

          {events.map((ev, idx) => {
            const actionMeta = ACTION_LABELS[ev.action] || {
              label: ev.action || "Event",
              color: "#374151",
              bg: "#f3f4f6",
            };
            const actorName = ev.actor?.name || (typeof ev.actor === "string" ? ev.actor : "System");
            const actorRole = ev.actor?.role || "";
            const isExpanded = !!expandedHashes[idx];

            return (
              <div
                key={idx}
                style={{
                  position: "relative",
                  marginBottom: 16,
                  paddingLeft: 20,
                }}
              >
                {/* Node icon / bullet */}
                <div
                  style={{
                    position: "absolute",
                    left: -20,
                    top: 14,
                    width: 14,
                    height: 14,
                    borderRadius: "50%",
                    background: actionMeta.color,
                    border: "3px solid #fff",
                    boxShadow: "0 0 0 2px #cbd5e1",
                  }}
                />

                <div className="card" style={{ marginBottom: 0, padding: 18 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: 8,
                      marginBottom: 10,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          color: "#6b7280",
                          background: "#f3f4f6",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}
                      >
                        #{ev.seq !== undefined ? ev.seq : idx + 1}
                      </span>
                      <span
                        className="badge"
                        style={{
                          background: actionMeta.bg,
                          color: actionMeta.color,
                          fontSize: 13,
                        }}
                      >
                        {actionMeta.label}
                      </span>
                      <span style={{ fontSize: 14, color: "#1f2430", fontWeight: 600 }}>
                        {actorName}
                        {actorRole && (
                          <span
                            style={{
                              marginLeft: 6,
                              fontSize: 11,
                              fontWeight: 500,
                              color: "#6b7280",
                              background: "#e5e7eb",
                              padding: "1px 6px",
                              borderRadius: 4,
                            }}
                          >
                            {actorRole}
                          </span>
                        )}
                      </span>
                    </div>

                    <span style={{ fontSize: 12, color: "#6b7280" }}>
                      {formatTimestamp(ev.timestamp)}
                    </span>
                  </div>

                  {/* Event Details Content */}
                  {ev.details && Object.keys(ev.details).length > 0 && (
                    <div
                      style={{
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: 6,
                        padding: "10px 14px",
                        fontSize: 13,
                        margin: "10px 0",
                      }}
                    >
                      {ev.action === "review_run" && (
                        <div>
                          <strong>Score:</strong> {ev.details.score}/100 &nbsp;|&nbsp;
                          <strong>Findings:</strong> {ev.details.findings_count ?? (ev.details.findings ? ev.details.findings.length : "—")} &nbsp;|&nbsp;
                          <strong>Rulebook Version:</strong> {ev.details.rulebook_version || "latest"}
                        </div>
                      )}

                      {ev.action === "finding_decided" && (
                        <div>
                          <div>
                            <strong>Decision:</strong>{" "}
                            <span
                              style={{
                                color: ev.details.status === "accepted" ? "#15803d" : "#b91c1c",
                                fontWeight: 600,
                              }}
                            >
                              {ev.details.status?.toUpperCase()}
                            </span>
                            {ev.details.finding_id && (
                              <span style={{ color: "#666", marginLeft: 8 }}>
                                (ID: {ev.details.finding_id})
                              </span>
                            )}
                          </div>
                          {ev.details.category && (
                            <div style={{ marginTop: 2 }}>
                              <strong>Category:</strong> {ev.details.category}
                            </div>
                          )}
                          {ev.details.original_text && (
                            <div style={{ marginTop: 2, color: "#4b5563" }}>
                              <strong>Original:</strong> &ldquo;{ev.details.original_text}&rdquo;
                            </div>
                          )}
                          {ev.details.replacement && (
                            <div style={{ marginTop: 2, color: "#15803d" }}>
                              <strong>Replacement:</strong> &ldquo;{ev.details.replacement}&rdquo;
                            </div>
                          )}
                        </div>
                      )}

                      {ev.action === "decision_made" && (
                        <div>
                          <div>
                            <strong>Final Decision:</strong>{" "}
                            <span
                              style={{
                                color: ev.details.decision === "approved" ? "#15803d" : "#b91c1c",
                                fontWeight: 700,
                              }}
                            >
                              {ev.details.decision?.toUpperCase()}
                            </span>
                          </div>
                          {ev.details.comment && (
                            <div style={{ marginTop: 4, fontStyle: "italic", color: "#374151" }}>
                              &ldquo;{ev.details.comment}&rdquo;
                            </div>
                          )}
                        </div>
                      )}

                      {ev.action === "sent_to_reviewer" && (
                        <div>
                          <strong>Ready for Review</strong> —
                          Accepted fixes: {ev.details.accepted_count ?? "—"},
                          Rejected fixes: {ev.details.rejected_count ?? "—"}
                        </div>
                      )}

                      {ev.action === "content_created" && (
                        <div>
                          <strong>Title:</strong> {ev.details.title || "—"} &nbsp;|&nbsp;
                          <strong>Type:</strong> {ev.details.type || "—"} &nbsp;|&nbsp;
                          <strong>Length:</strong> {ev.details.char_count ?? ev.details.text_length ?? "—"} chars
                        </div>
                      )}

                      {/* Fallback for other details */}
                      {!["review_run", "finding_decided", "decision_made", "sent_to_reviewer", "content_created"].includes(ev.action) && (
                        <pre style={{ margin: 0, fontSize: 12, overflowX: "auto" }}>
                          {JSON.stringify(ev.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}

                  {/* Cryptographic Hash Bar */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: 11,
                      fontFamily: "monospace",
                      color: "#64748b",
                      marginTop: 8,
                      paddingTop: 8,
                      borderTop: "1px dashed #e2e8f0",
                    }}
                  >
                    <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
                      <span>
                        <strong style={{ color: "#475569" }}>Hash:</strong>{" "}
                        <span style={{ color: "#0f172a", background: "#f1f5f9", padding: "2px 5px", borderRadius: 3 }}>
                          {isExpanded ? (ev.hash || "none") : truncateHash(ev.hash, 8)}
                        </span>
                      </span>
                      <span>
                        <strong style={{ color: "#475569" }}>Prev:</strong>{" "}
                        <span style={{ color: "#64748b", background: "#f8fafc", padding: "2px 5px", borderRadius: 3 }}>
                          {isExpanded ? (ev.prev_hash || "genesis") : truncateHash(ev.prev_hash, 8)}
                        </span>
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleHash(idx)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#3b4a9c",
                        cursor: "pointer",
                        fontSize: 11,
                        padding: 0,
                        textDecoration: "underline",
                      }}
                    >
                      {isExpanded ? "Collapse" : "Full Hash"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
