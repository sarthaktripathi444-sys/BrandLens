// frontend/app/reviewer/[id]/page.js
// Reviewer screen: original vs revised text, flags and their status, comment box, Approve / Request Changes.
// The [id] in the address is the CONTENT id.

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAuth } from "../../../lib/auth";
import { getReview, submitDecision } from "../../../lib/api";
import HighlightedText from "../../../components/HighlightedText";
import StatusBadge from "../../../components/StatusBadge";

export default function ReviewerPage() {
  const router = useRouter();
  const { id } = useParams();
  const [auth, setAuth] = useState(null);
  const [sub, setSub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [decision, setDecision] = useState(null); // set after the reviewer decides on this page

  // Check the login, then load the submission.
  useEffect(() => {
    const a = getAuth();
    if (!a) {
      router.replace("/login");
      return;
    }
    setAuth(a);

    getReview(id)
      .then(setSub)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, router]);

  if (!auth || loading) return <div>Loading...</div>;
  if (auth.role !== "reviewer") {
    return <div className="card">Only reviewers can open this page. Log in as a Reviewer.</div>;
  }
  if (!sub) {
    return <div className="card" style={{ color: "#c0392b" }}>{error || "Could not load this submission."}</div>;
  }

  const accepted = sub.findings.filter((f) => f.status === "accepted");
  const rejected = sub.findings.filter((f) => f.status === "rejected");
  const waiting = sub.status === "pending_review" && !decision; // can the reviewer still decide?

  // Sends the decision to the backend. "approved" or "changes_requested" (needs a comment).
  async function decide(choice) {
    if (choice === "changes_requested" && !comment.trim()) {
      setError("Please write what needs to change.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const updated = await submitDecision(id, choice, comment.trim());
      setSub(updated);
      setDecision(updated.status);
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
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
          <StatusBadge status={sub.status} />
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
              <div>Suggested was: "{f.suggestion || "no automatic rewrite"}"</div>
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
          <div className="card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{sub.revised_text}</div>
        </div>
      </div>

      {waiting ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Your decision</h3>
          <label>Comment (needed if you request changes)</label>
          <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} />
          {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button className="btn" onClick={() => decide("approved")} disabled={busy}>Approve</button>
            <button className="btn danger" onClick={() => decide("changes_requested")} disabled={busy}>
              Request Changes
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            {sub.status === "approved" && "Content approved"}
            {sub.status === "changes_requested" && "Changes requested"}
            {sub.status !== "approved" && sub.status !== "changes_requested" && "Not waiting for review"}
          </h3>
          {sub.comment && <p>Comment: {sub.comment}</p>}
          {sub.status !== "approved" && sub.status !== "changes_requested" && (
            <p>This content is currently "{sub.status}", so it is not in the review queue.</p>
          )}
          <Link href="/dashboard"><button className="btn secondary">Back to dashboard</button></Link>
        </div>
      )}
    </div>
  );
}
