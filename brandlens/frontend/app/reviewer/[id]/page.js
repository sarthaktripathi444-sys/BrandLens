// frontend/app/reviewer/[id]/page.js
// Reviewer screen: original vs revised text, flags and their status, comment box, Approve / Request Changes.
// TODO: call the decision endpoint on each button.

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAuth } from "../../../lib/auth";
import { mockSubmission } from "../../../lib/mock";
import HighlightedText from "../../../components/HighlightedText";
import StatusBadge from "../../../components/StatusBadge";

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

export default function ReviewerPage() {
  const router = useRouter();
  const [auth, setAuth] = useState(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [decision, setDecision] = useState(null);

  useEffect(() => {
    const a = getAuth();
    if (!a) router.replace("/login");
    else setAuth(a);
  }, [router]);

  if (!auth) return <div>Loading...</div>;
  if (auth.role !== "reviewer") {
    return <div className="card">Only reviewers can open this page. Log in as a Reviewer.</div>;
  }

  const sub = mockSubmission;
  const accepted = sub.findings.filter((f) => f.status === "accepted");
  const rejected = sub.findings.filter((f) => f.status === "rejected");
  const revised = buildRevised(sub.text, sub.findings);

  function approve() {
    setError("");
    // Later: POST /review/{id}/decision with status "approved".
    setDecision("approved");
  }

  function requestChanges() {
    if (!comment.trim()) {
      setError("Please write what needs to change.");
      return;
    }
    setError("");
    // Later: POST /review/{id}/decision with status "changes_requested" and the comment.
    setDecision("changes_requested");
  }

  return (
    <div>
      <h2>{sub.title}</h2>
      <div style={{ color: "#555", marginBottom: 16 }}>{sub.type}</div>

      <div className="card" style={{ display: "flex", gap: 24, alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{sub.score}/100</div>
          <div>AI brand score</div>
        </div>
        <div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{accepted.length}</div>
          <div>Fixes accepted</div>
        </div>
        <div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{rejected.length}</div>
          <div>Fixes rejected</div>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <StatusBadge status={decision || "pending_review"} />
        </div>
      </div>

      {rejected.length > 0 && (
        <div className="card" style={{ borderLeft: "4px solid #c0392b" }}>
          <strong>Check these: the creator rejected the AI fix</strong>
          {rejected.map((f) => (
            <div key={f.id} style={{ marginTop: 10, fontSize: 14 }}>
              <div>Issue: {f.issue} ({f.category})</div>
              <div>Original: "{f.text}"</div>
              <div>Rule: {f.rule}</div>
              <div>Suggested was: "{f.suggestion}"</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <h3>Original</h3>
          <div className="card"><HighlightedText text={sub.text} findings={sub.findings} /></div>
        </div>
        <div style={{ flex: 1 }}>
          <h3>Revised</h3>
          <div className="card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{revised}</div>
        </div>
      </div>

      {!decision ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Your decision</h3>
          <label>Comment (needed if you request changes)</label>
          <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} />
          {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button className="btn" onClick={approve}>Approve</button>
            <button className="btn danger" onClick={requestChanges}>Request Changes</button>
          </div>
        </div>
      ) : (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            {decision === "approved" ? "Content approved" : "Changes requested"}
          </h3>
          {comment && <p>Comment: {comment}</p>}
          <Link href="/dashboard"><button className="btn secondary">Back to dashboard</button></Link>
        </div>
      )}
    </div>
  );
}
