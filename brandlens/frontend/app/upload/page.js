// frontend/app/upload/page.js
// Creator page: title, content type, paste text or upload a file, then start the AI review.

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "../../lib/auth";
import { createContent, extractFile, runReview } from "../../lib/api";

const TYPES = ["Blog", "Email", "Social Post", "Landing Page", "Press Release", "Ad"];
export default function UploadPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [type, setType] = useState("Blog");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [auth, setAuth] = useState(null);

  useEffect(() => {
    const a = getAuth();
    if (!a) router.replace("/login");
    else setAuth(a);
  }, [router]);

  // Reads the chosen file: .txt is read in the browser, .pdf and .docx are read by the backend.
  async function handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    const name = file.name.toLowerCase();
    setError("");

    if (name.endsWith(".txt")) {
      const reader = new FileReader();
      reader.onload = () => setText(reader.result);
      reader.readAsText(file);
    } else if (name.endsWith(".pdf") || name.endsWith(".docx")) {
      setBusy(true);
      try {
        const data = await extractFile(file);
        setText(data.text);
      } catch (err) {
        setError(err.message);
        setBusy(false);
        return;
      }
      setBusy(false);
    } else {
      setError("Please upload a .txt, .pdf or .docx file, or paste the text below.");
      return;
    }
    if (!title) setTitle(file.name.replace(/\.(txt|pdf|docx)$/i, ""));
  }

  // Saves the content, runs the AI review, then opens the review screen.
  async function handleReview() {
    if (!title.trim() || !text.trim()) {
      setError("Please add a title and some content first.");
      return;
    }
    setError("");
    setBusy(true);
    let created;
    try {
      created = await createContent(title.trim(), type, text);
    } catch (err) {
      setError(err.message);
      setBusy(false);
      return;
    }
    try {
      await runReview(created.id);
    } catch {
      // The content is saved; the review page shows the problem and lets the creator try again.
    }
    router.push(`/review/${created.id}`);
  }

  if (!auth) return <div>Loading...</div>;
  if (auth.role !== "creator") {
    return <div className="card">Only creators can add content. Log in as a Creator.</div>;
  }

  return (
    <div>
      <h2>New Content</h2>
      <div className="card">
        <label>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Spring Sale Email" />

        <label>Content type</label>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>

        <label>Upload a .txt, .pdf or .docx file (optional)</label>
        <input type="file" accept=".txt,.pdf,.docx" onChange={handleFile} />

        <label>Or paste your content</label>
        <textarea
          rows={12}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your blog, email, social post or press release here..."
        />
        <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>{text.length} characters</div>

        {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}

        <button className="btn" style={{ marginTop: 16 }} onClick={handleReview} disabled={busy}>
          {busy ? "Working..." : "Run Brand Review"}
        </button>
      </div>
    </div>
  );
}