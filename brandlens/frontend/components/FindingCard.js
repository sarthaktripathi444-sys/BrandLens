// frontend/components/FindingCard.js
// Shows one flag: coloured category badge, issue, reason, rule violated, suggested fix, Accept/Reject buttons.
// The buttons are hidden when no onAccept / onReject is given (read-only view).

export const CATEGORY_COLORS = {
  tone: { bg: "#ede9fe", color: "#5b21b6" },
  terminology: { bg: "#dbeafe", color: "#1d4ed8" },
  fact: { bg: "#fef3c7", color: "#92400e" },
  claim: { bg: "#fee2e2", color: "#991b1b" },
};

export default function FindingCard({ finding, onAccept, onReject }) {
  const c = CATEGORY_COLORS[finding.category] || CATEGORY_COLORS.tone;
  const decided = finding.status !== "pending";

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
      <div style={{ fontSize: 14, marginBottom: 4 }}><strong>Rule:</strong> {finding.rule}</div>
      <div style={{ fontSize: 14, marginBottom: 10 }}>
        <strong>Suggested fix:</strong>{" "}
        {finding.suggestion ? `"${finding.suggestion}"` : "No automatic rewrite - fix this one by hand."}
      </div>

      {onAccept && onReject && (
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={onAccept} disabled={finding.status === "accepted"}>
            Accept
          </button>
          <button className="btn secondary" onClick={onReject} disabled={finding.status === "rejected"}>
            Reject
          </button>
        </div>
      )}
    </div>
  );
}