// frontend/app/review/[id]/page.js
// Creator's review screen: highlighted text, list of flags, accept/reject fixes, revised preview, 'Send to Reviewer'.
// The [id] in the address is the CONTENT id.

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAuth } from "../../../lib/auth";
import { getReview, runReview, sendToReviewer, setFindingStatus } from "../../../lib/api";
import FindingCard from "../../../components/FindingCard";
import HighlightedText from "../../../components/HighlightedText";
import StatusBadge from "../../../components/StatusBadge";

export default function ReviewPage() {
  const router = useRouter();
  const { id } = useParams();
  const [auth, setAuth] = useState(null);
  const [review, setReview] = useState(null);
  const [notReviewed, setNotReviewed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Check the login, then load the review from the backend.
  useEffect(() => {
    const a = getAuth();
    if (!a) {
      router.replace("/login");
      return;
    }
    setAuth(a);

    getReview(id)
      .then(setReview)
      .catch((e) => {
        if (e.status === 404) setNotReviewed(true);
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [id, router]);

  // Runs the checks (or runs them again; applyAccepted keeps the fixes already accepted).
  async function run(applyAccepted) {
    setError("");
    setBusy(true);
    try {
      setReview(await runReview(id, applyAccepted));
      setNotReviewed(false);
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  // Accept or reject one finding; accepts an optional alternative replacement.
  async function decide(findingId, status, replacement) {
    setError("");
    try {
      setReview(await setFindingStatus(id, findingId, status, replacement));
    } catch (e) {
      setError(e.message);
    }
  }

  async function send() {
    setError("");
    setBusy(true);
    try {
      await sendToReviewer(id);
      router.push("/dashboard");
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  if (!auth || loading) return <div>Loading...</div>;
  if (auth.role !== "creator") {
    return <div className="card">Only creators can open this page. Log in as a Creator.</div>;
  }

  if (notReviewed || !review) {
    return (
      <div>
        <h2>Brand review</h2>
        <div className="card">
          <p>{notReviewed ? "This content has not been reviewed yet." : "Could not load this review."}</p>
          {error && <div style={{ color: "#c0392b", marginBottom: 10 }}>{error}</div>}
          {notReviewed && (
            <button className="btn" onClick={() => run(false)} disabled={busy}>
              {busy ? "Reviewing..." : "Run Brand Review"}
            </button>
          )}
        </div>
      </div>
    );
  }

  const findings = review.findings;
  const pending = findings.filter((f) => f.status === "pending").length;
  const editable = review.status === "reviewed"; // only then may the creator change decisions
  const accepted = findings.filter((f) => f.status === "accepted").length;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>{review.title}</h2>
        <span
          className="badge"
          style={{
            background: "#e0e7ff",
            color: "#3730a3",
            fontSize: 13,
            padding: "4px 10px",
            fontWeight: 600,
          }}
        >
          {review.type}
        </span>
        <StatusBadge status={review.status} />
        <Link
          href={`/audit/${id}`}
          className="btn secondary"
          style={{ marginLeft: "auto", fontSize: 13, padding: "6px 12px", textDecoration: "none" }}
        >
          View Audit Trail
        </Link>
      </div>

      {review.status === "changes_requested" && (
        <div className="card" style={{ borderLeft: "4px solid #c0392b" }}>
          <strong>The reviewer requested changes{review.reviewed_by ? ` (${review.reviewed_by})` : ""}:</strong>
          <p style={{ marginBottom: 12 }}>{review.comment}</p>
          <button className="btn" onClick={() => run(true)} disabled={busy}>
            {busy ? "Reviewing..." : "Apply accepted fixes and review again"}
          </button>
        </div>
      )}
      {review.status === "pending_review" && (
        <div className="card">This content has been sent to the reviewer and is waiting for a decision.</div>
      )}
      {review.status === "approved" && (
        <div className="card" style={{ borderLeft: "4px solid #065f46", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <div>
            <strong>Approved{review.reviewed_by ? ` by ${review.reviewed_by}` : ""}.</strong>
            {review.comment && <span style={{ marginLeft: 6 }}>Comment: {review.comment}</span>}
          </div>
          <Link href={`/audit/${id}`} className="btn" style={{ fontSize: 13, textDecoration: "none" }}>
            View Certified Audit Trail
          </Link>
        </div>
      )}

      <div className="card" style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <div>
          <div style={{ fontSize: 36, fontWeight: 700 }}>{review.score}/100</div>
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
      <div className="card"><HighlightedText text={review.text} findings={findings} /></div>

      <h3>Issues</h3>
      {findings.length === 0 && <div className="card">No issues found. This content follows the brand rule book.</div>}
      {findings.map((f) => (
        <FindingCard
          key={f.id}
          finding={f}
          contentId={id}
          onAccept={editable ? (rep) => decide(f.id, "accepted", rep) : undefined}
          onReject={editable ? () => decide(f.id, "rejected") : undefined}
        />
      ))}

      <h3>Revised version ({accepted} accepted fix{accepted === 1 ? "" : "es"} applied)</h3>
      <div className="card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{review.revised_text}</div>

      {error && <div style={{ color: "#c0392b", marginBottom: 12 }}>{error}</div>}

      {editable && (
        <button className="btn" disabled={pending > 0 || busy} onClick={send}>
          {pending > 0 ? `Decide ${pending} more issue(s) to continue` : busy ? "Sending..." : "Send to Reviewer"}
        </button>
      )}
    </div>
  );
}
