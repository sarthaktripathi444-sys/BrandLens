// frontend/components/HighlightedText.js
// Shows the content text with every flagged part highlighted in its category colour.

import { CATEGORY_COLORS } from "./FindingCard";

export default function HighlightedText({ text, findings }) {
  // Only findings that know where they are in the text can be highlighted.
  const sorted = findings
    .filter((f) => Number.isInteger(f.start) && Number.isInteger(f.end) && f.end > f.start)
    .sort((a, b) => a.start - b.start);
  const parts = [];
  let pos = 0;

  sorted.forEach((f) => {
    if (f.start < pos) return;
    if (f.start > pos) parts.push({ text: text.slice(pos, f.start) });
    parts.push({ text: text.slice(f.start, f.end), finding: f });
    pos = f.end;
  });
  if (pos < text.length) parts.push({ text: text.slice(pos) });

  return (
    <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
      {parts.map((p, i) => {
        if (!p.finding) return <span key={i}>{p.text}</span>;
        const c = CATEGORY_COLORS[p.finding.category] || CATEGORY_COLORS.tone;
        const resolved = p.finding.status !== "pending";
        return (
          <mark
            key={i}
            title={p.finding.issue}
            style={{
              background: resolved ? "#e5e7eb" : c.bg,
              color: c.color,
              padding: "1px 3px",
              borderRadius: 4,
              textDecoration: p.finding.status === "accepted" ? "line-through" : "none",
            }}
          >
            {p.text}
          </mark>
        );
      })}
    </div>
  );
}