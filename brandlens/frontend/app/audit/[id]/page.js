// frontend/app/audit/[id]/page.js
// Feature 3: Audit Trail & Certification Report View (Person A)
// Displays complete chronological compliance history, cryptographic verification status,
// and official PDF certification report download for approved content.

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAuth } from "../../../lib/auth";
import { getAudit, getContent, downloadReport } from "../../../lib/api";
import StatusBadge from "../../../components/StatusBadge";
import AuditTimeline from "../../../components/AuditTimeline";

export default function AuditTrailPage() {
  const router = useRouter();
  const { id } = useParams();

  const [auth, setAuth] = useState(null);
  const [content, setContent] = useState(null);
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [downloadError, setDownloadError] = useState("");

  useEffect(() => {
    const a = getAuth();
    if (!a) {
      router.replace("/login");
      return;
    }
    setAuth(a);

    async function loadData() {
      try {
        setError("");
        // Load both content details and audit trail in parallel
        const [contentData, auditData] = await Promise.all([
          getContent(id).catch(() => null),
          getAudit(id),
        ]);

        setContent(contentData);
        setAudit(auditData);
      } catch (e) {
        setError(e.message || "Failed to load audit trail.");
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      loadData();
    }
  }, [id, router]);

  async function handleDownloadReport() {
    setDownloading(true);
    setDownloadError("");
    try {
      await downloadReport(id);
    } catch (e) {
      setDownloadError(e.message || "Failed to generate certification report.");
    } finally {
      setDownloading(false);
    }
  }

  if (!auth || loading) {
    return (
      <div className="container">
        <div className="card" style={{ textAlign: "center", padding: 40, color: "#666" }}>
          Loading audit trail and cryptographic ledger...
        </div>
      </div>
    );
  }

  const isApproved = content?.status === "approved" || audit?.status === "approved";
  const events = audit?.events || [];
  const chainValid = !!audit?.chain_valid;

  return (
    <div className="container">
      {/* Breadcrumb Navigation */}
      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10, fontSize: 14 }}>
        <Link href="/dashboard" style={{ color: "#3b4a9c", textDecoration: "none" }}>
          ← Back to Dashboard
        </Link>
        {content && (
          <>
            <span style={{ color: "#aaa" }}>/</span>
            <Link
              href={auth.role === "reviewer" ? `/reviewer/${id}` : `/review/${id}`}
              style={{ color: "#3b4a9c", textDecoration: "none" }}
            >
              Review Workspace
            </Link>
          </>
        )}
      </div>

      {error ? (
        <div className="card" style={{ borderLeft: "4px solid #c0392b", color: "#991b1b" }}>
          <h3 style={{ marginTop: 0 }}>Unable to Load Audit Trail</h3>
          <p>{error}</p>
          <Link href="/dashboard">
            <button className="btn secondary">Return to Dashboard</button>
          </Link>
        </div>
      ) : (
        <>
          {/* Header Card */}
          <div className="card">
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 16,
              }}
            >
              <div style={{ flex: 1, minWidth: 260 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <h2 style={{ margin: 0 }}>
                    {content?.title || `Content ${id.slice(0, 8)}...`}
                  </h2>
                  <StatusBadge status={content?.status || audit?.status || "draft"} />
                </div>
                <div style={{ fontSize: 13, color: "#555" }}>
                  <span>Type: <strong>{content?.type || "Content"}</strong></span>
                  {content?.owner && <span> · Owner: <strong>{content.owner}</strong></span>}
                  {content?.created_at && (
                    <span> · Created: {new Date(content.created_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>

              {/* Certification Report Action Box */}
              <div>
                {isApproved ? (
                  <button
                    className="btn"
                    onClick={handleDownloadReport}
                    disabled={downloading}
                    style={{
                      background: "#15803d",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 14,
                      padding: "10px 20px",
                    }}
                  >
                    <span>{downloading ? "⏳" : "📄"}</span>
                    <span>
                      {downloading ? "Generating PDF..." : "Download Certification Report (PDF)"}
                    </span>
                  </button>
                ) : (
                  <div
                    style={{
                      fontSize: 12,
                      color: "#6b7280",
                      background: "#f3f4f6",
                      padding: "8px 14px",
                      borderRadius: 6,
                      border: "1px dashed #d1d5db",
                      maxWidth: 280,
                    }}
                  >
                    🔒 <strong>Certification Locked:</strong> Report download becomes available once content is approved by a human reviewer.
                  </div>
                )}
              </div>
            </div>

            {downloadError && (
              <div
                style={{
                  marginTop: 14,
                  padding: "8px 12px",
                  borderRadius: 6,
                  background: "#fee2e2",
                  color: "#991b1b",
                  fontSize: 13,
                }}
              >
                {downloadError}
              </div>
            )}

            {/* Quick Metrics */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: 12,
                marginTop: 20,
                paddingTop: 16,
                borderTop: "1px solid #e5e7eb",
              }}
            >
              <div>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#6b7280", fontWeight: 600 }}>
                  Recorded Events
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "#1f2a5a" }}>
                  {events.length}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#6b7280", fontWeight: 600 }}>
                  Ledger State
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, marginTop: 4, color: chainValid ? "#15803d" : "#b91c1c" }}>
                  {chainValid ? "✓ Tamper-Evident" : "⚠️ Needs Verification"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#6b7280", fontWeight: 600 }}>
                  Compliance Score
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "#1f2a5a" }}>
                  {content?.score !== null && content?.score !== undefined ? `${content.score}/100` : "—"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#6b7280", fontWeight: 600 }}>
                  Content ID
                </div>
                <div style={{ fontSize: 12, fontFamily: "monospace", color: "#4b5563", marginTop: 4 }}>
                  {id}
                </div>
              </div>
            </div>
          </div>

          {/* Audit Timeline Section */}
          <div style={{ marginTop: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>Compliance Event Log & Cryptographic Ledger</h3>
              <span style={{ fontSize: 13, color: "#6b7280" }}>
                Chronological Order (Oldest to Newest)
              </span>
            </div>

            <AuditTimeline events={events} chainValid={chainValid} />
          </div>
        </>
      )}
    </div>
  );
}
