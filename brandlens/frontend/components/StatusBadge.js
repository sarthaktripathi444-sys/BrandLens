// frontend/components/StatusBadge.js
// Small coloured label for draft, pending review, approved and changes requested.
// TODO: map each status to a colour and label.

const STYLES = {
  draft: { label: "Draft", bg: "#e6e8f5", color: "#1f2a5a" },
  reviewed: { label: "AI Reviewed", bg: "#dbeafe", color: "#1d4ed8" },
  pending_review: { label: "Pending Review", bg: "#fef3c7", color: "#92400e" },
  approved: { label: "Approved", bg: "#d1fae5", color: "#065f46" },
  changes_requested: { label: "Changes Requested", bg: "#fee2e2", color: "#991b1b" },
};

export default function StatusBadge({ status }) {
  const s = STYLES[status] || STYLES.draft;
  return (
    <span className="badge" style={{ background: s.bg, color: s.color }}>
      {s.label}
    </span>
  );
}