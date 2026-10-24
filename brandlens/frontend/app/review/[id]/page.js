// frontend/app/review/[id]/page.js
// Creator's review screen: highlighted text, list of flags, accept/reject fixes, revised preview, 'Send to Reviewer'.
// TODO: use HighlightedText + FindingCard and call the review API.

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "../../../lib/auth";
import { mockReview } from "../../../lib/mock";
import FindingCard from "../../../components/FindingCard";
import HighlightedText from "../../../components/HighlightedText";

function buildRevised(text, findings) {
  let result = text;
  [...findings]
    .filter((f) => f.status === "accepted")
    .sort((a, b) => b.start - a.start)
    .forEach((f) => {
      result = result.slice(0, f.start) + f.suggestion + result.slice(f.end);
    });
  return result;
}

export default function ReviewPage() {
  const router = useRouter();
  const [findings, setFindings] = useState(mockReview.findings);

  useEffect(() => {
    if (!getAuth()) router.replace("/login");
  }, [router]);

  function setStatus(id, status) {
    setFindings((fs) => fs.map((f) => (f.id === id ? { ...f, status } : f)));
  }

  const pending = findings.filter((f) => f.status === "pending").length;
  const revised = buildRevised(mockReview.text, findings);

  return (
    <div>
      <h2>{mockReview.title}</h2>
      <div style={{ color: "#555", marginBottom: 16 }}>{mockReview.type}</div>

      <div className="card" style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <div>
          <div style={{ fontSize: 36, fontWeight: 700 }}>{mockReview.score}/100</div>
          <div>Brand score</div>
        </div>
        <div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{findings.length}</div>
          <div>Issues found</div>
        </div>
        <div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{pending}</div>
          <div>Still to decide</div>
        </div>
      </div>

      <h3>Your content</h3>
      <div className="card"><HighlightedText text={mockReview.text} findings={findings} /></div>

      <h3>Issues</h3>
      {findings.map((f) => (
        <FindingCard
          key={f.id}
          finding={f}
          onAccept={() => setStatus(f.id, "accepted")}
          onReject={() => setStatus(f.id, "rejected")}
        />
      ))}

      <h3>Revised version (accepted fixes applied)</h3>
      <div className="card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{revised}</div>

      <button
        className="btn"
        disabled={pending > 0}
        onClick={() => router.push("/dashboard")}
      >
        {pending > 0 ? `Decide ${pending} more issue(s) to continue` : "Send to Reviewer"}
      </button>
    </div>
  );
}
