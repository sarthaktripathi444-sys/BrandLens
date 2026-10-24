// frontend/app/upload/page.js
// Creator page: title, content type, paste text or upload a file, then start the AI review.
// TODO: build the form, call the content API, then open /review/[id].

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "../../lib/auth";

const TYPES = ["Blog", "Email", "Social Post", "Landing Page", "Press Release"];

export default function UploadPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [type, setType] = useState("Blog");
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const a = getAuth();
    if (!a) router.replace("/login");
  }, [router]);

  function handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.name.endsWith(".txt")) {
      setError("For now, upload a .txt file or paste the text below. PDF and Word support comes with the backend.");
      return;
    }
    setError("");
    const reader = new FileReader();
    reader.onload = () => setText(reader.result);
    reader.readAsText(file);
    if (!title) setTitle(file.name.replace(".txt", ""));
  }

  function handleReview() {
    if (!title.trim() || !text.trim()) {
      setError("Please add a title and some content first.");
      return;
    }
    setError("");
    // Later: POST /content, then POST /review/{id}/run, then go to the real id.
    router.push("/review/c2");
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

        <label>Upload a .txt file (optional)</label>
        <input type="file" accept=".txt" onChange={handleFile} />

        <label>Or paste your content</label>
        <textarea
          rows={12}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your blog, email, social post or press release here..."
        />
        <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>{text.length} characters</div>

        {error && <div style={{ color: "#c0392b", marginTop: 10 }}>{error}</div>}

        <button className="btn" style={{ marginTop: 16 }} onClick={handleReview}>
          Run Brand Review
        </button>
      </div>
    </div>
  );
}