// frontend/app/dashboard/page.js
// Home screen that changes by role: creator's submissions, manager's rule book status, reviewer's queue.
// TODO: fetch content for the logged-in role and show StatusBadge on each item.

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAuth } from "../../lib/auth";
import { mockContent, mockRulebook } from "../../lib/mock";
import StatusBadge from "../../components/StatusBadge";

export default function DashboardPage() {
  const router = useRouter();
  const [auth, setAuth] = useState(null);

  useEffect(() => {
    const a = getAuth();
    if (!a) router.replace("/login");
    else setAuth(a);
  }, [router]);

  if (!auth) return <div>Loading...</div>;

  const isReviewer = auth.role === "reviewer";
  const items = isReviewer
    ? mockContent.filter((c) => c.status === "pending_review")
    : mockContent;

  const count = (s) => mockContent.filter((c) => c.status === s).length;

  return (
    <div>
      <h2>Welcome, {auth.name}</h2>

      {auth.role === "manager" && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Rule Book</h3>
          <p>
            Active rule book: <strong>{mockRulebook.company}</strong> (updated {mockRulebook.updated})
          </p>
          <Link href="/rulebook"><button className="btn">Manage Rule Book</button></Link>
        </div>
      )}

      {auth.role === "creator" && (
        <div style={{ marginBottom: 16 }}>
          <Link href="/upload"><button className="btn">+ New Content</button></Link>
        </div>
      )}

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <div className="card" style={{ flex: 1, marginBottom: 0 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{mockContent.length}</div>
          <div>Total content</div>
        </div>
        <div className="card" style={{ flex: 1, marginBottom: 0 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{count("pending_review")}</div>
          <div>Pending review</div>
        </div>
        <div className="card" style={{ flex: 1, marginBottom: 0 }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{count("approved")}</div>
          <div>Approved</div>
        </div>
      </div>

      <h3>{isReviewer ? "Review queue" : "Content"}</h3>
      {items.length === 0 && <div className="card">Nothing here yet.</div>}
      {items.map((c) => (
        <div key={c.id} className="card" style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <strong>{c.title}</strong>
            <div style={{ fontSize: 13, color: "#555" }}>{c.type}</div>
          </div>
          {c.score !== null && <div>Score: <strong>{c.score}</strong></div>}
          <StatusBadge status={c.status} />
          {auth.role !== "manager" && (
            <Link href={isReviewer ? `/reviewer/${c.id}` : `/review/${c.id}`}>
              <button className="btn secondary">Open</button>
            </Link>
          )}
        </div>
      ))}
    </div>
  );
}
