// frontend/app/dashboard/page.js
// Home screen that changes by role: creator's submissions, manager's rule book status, reviewer's queue.

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAuth } from "../../lib/auth";
import { getActiveRulebook, listContent } from "../../lib/api";
import StatusBadge from "../../components/StatusBadge";

export default function DashboardPage() {
  const router = useRouter();
  const [auth, setAuth] = useState(null);
  const [content, setContent] = useState([]);
  const [rulebook, setRulebook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Check the login, then load the content list (and the rule book for managers).
  useEffect(() => {
    const a = getAuth();
    if (!a) {
      router.replace("/login");
      return;
    }
    setAuth(a);

    async function load() {
      try {
        setContent(await listContent());
        if (a.role === "manager") {
          try {
            setRulebook(await getActiveRulebook());
          } catch (e) {
            if (e.status !== 404) throw e; // 404 just means "no rule book yet"
          }
        }
      } catch (e) {
        setError(e.message);
      }
      setLoading(false);
    }
    load();
  }, [router]);

  if (!auth) return <div>Loading...</div>;

  const isReviewer = auth.role === "reviewer";
  const items = isReviewer ? content.filter((c) => c.status === "pending_review") : content;
  const count = (s) => content.filter((c) => c.status === s).length;

  return (
    <div>
      <h2>Welcome, {auth.name}</h2>

      {error && <div className="card" style={{ color: "#c0392b" }}>{error}</div>}

      {auth.role === "manager" && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Rule Book</h3>
          {rulebook ? (
            <p>
              Active rule book: <strong>{rulebook.company}</strong>
              {rulebook.updated && <> (updated {new Date(rulebook.updated).toLocaleDateString()})</>}
            </p>
          ) : (
            <p>No rule book yet. Upload one so creators can run brand reviews.</p>
          )}
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
          <div style={{ fontSize: 28, fontWeight: 700 }}>{content.length}</div>
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
      {loading && <div className="card">Loading...</div>}
      {!loading && items.length === 0 && <div className="card">Nothing here yet.</div>}
      {items.map((c) => (
        <div key={c.id} className="card" style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <strong>{c.title}</strong>
            <div style={{ fontSize: 13, color: "#555" }}>
              {c.type}
              {c.owner ? ` · by ${c.owner}` : ""}
            </div>
          </div>
          {c.score !== null && c.score !== undefined && <div>Score: <strong>{c.score}</strong></div>}
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
