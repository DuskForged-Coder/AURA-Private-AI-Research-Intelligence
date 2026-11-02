"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type User = { id: string; email: string };
type Doc = { id: string; filename: string; size_bytes: number; status: string; created_at: string };
type Citation = {
  source_id: string;
  filename: string;
  chunk_id: string;
  excerpt: string;
  page_number: number | null;
  score: number;
};
type Answer = { conversation_id: string; answer: string; abstained: boolean; citations: Citation[] };

async function request(path: string, token: string, options: RequestInit = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function formatBytes(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Home() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshDocuments = useCallback(async (activeToken: string) => {
    const docs = await request("/documents", activeToken);
    setDocuments(docs);
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("aura-token");
    if (!saved) return;
    setToken(saved);
    request("/auth/me", saved)
      .then(async (profile) => {
        setUser(profile);
        await refreshDocuments(saved);
      })
      .catch(() => {
        window.localStorage.removeItem("aura-token");
        setToken("");
        setDocuments([]);
      });
  }, [refreshDocuments]);

  async function authenticate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await request("/auth/register", "", { method: "POST", body: JSON.stringify({ email, password }) });
      }
      const body = new URLSearchParams({ username: email, password });
      const session = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const payload = await session.json();
      if (!session.ok) throw new Error(payload.detail || "Unable to sign in");
      window.localStorage.setItem("aura-token", payload.access_token);
      setToken(payload.access_token);
      const profile = await request("/auth/me", payload.access_token);
      setUser(profile);
      await refreshDocuments(payload.access_token);
      setNotice("Your private workspace is ready.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const file = (form.elements.namedItem("document") as HTMLInputElement).files?.[0];
    if (!file) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      await request("/documents", token, { method: "POST", body });
      await refreshDocuments(token);
      form.reset();
      setNotice(`${file.name} is indexed and ready to search.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function deleteDocument(document: Doc) {
    if (!window.confirm(`Delete “${document.filename}” and its indexed content?`)) return;
    try {
      await request(`/documents/${document.id}`, token, { method: "DELETE" });
      await refreshDocuments(token);
      setNotice("Document and indexed passages deleted.");
      if (answer?.citations.some((citation) => citation.source_id === document.id)) setAnswer(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete the document");
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setAnswer(null);
    try {
      const result = await request("/ask", token, {
        method: "POST",
        body: JSON.stringify({ query: question }),
      });
      setAnswer(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not answer that question");
    } finally {
      setLoading(false);
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await request("/search", token, {
        method: "POST",
        body: JSON.stringify({ query: searchText }),
      });
      setSearchResults(result.results);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function signOut() {
    window.localStorage.removeItem("aura-token");
    setToken("");
    setUser(null);
    setDocuments([]);
    setAnswer(null);
    setSearchResults([]);
    setQuestion("");
    setSearchText("");
    setError("");
    setNotice("");
  }

  if (!user) {
    return (
      <main className="auth-page">
        <div className="auth-art">
          <div className="brand"><span className="brand-mark">A</span><span>AURA</span></div>
          <div className="auth-copy">
            <p className="eyebrow">YOUR KNOWLEDGE. YOUR CONTROL.</p>
            <h1>Research that stays<br /><span>yours.</span></h1>
            <p className="subtle">A quiet, private space to ask better questions of the documents you trust.</p>
            <div className="privacy-chip"><span className="pulse" /> Local-first · Evidence-backed · Private</div>
          </div>
          <div className="auth-orbit orbit-one" /><div className="auth-orbit orbit-two" />
        </div>
        <section className="auth-panel">
          <div className="auth-form-wrap">
            <p className="eyebrow">PRIVATE RESEARCH WORKSPACE</p>
            <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
            <p className="subtle">{mode === "login" ? "Sign in to continue to your library." : "Your documents are isolated to your account."}</p>
            <form className="stack-form" onSubmit={authenticate}>
              <label>Email address<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></label>
              <label>Password<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 10 characters" /></label>
              {error && <div className="error-box" role="alert">{error}</div>}
              <button className="primary-button full-button" disabled={loading}>{loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"} <span>→</span></button>
            </form>
            <p className="switch-mode">{mode === "login" ? "New to AURA?" : "Already have an account?"} <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>{mode === "login" ? "Create an account" : "Sign in"}</button></p>
            <div className="auth-foot"><span className="lock-icon">⌑</span> Your library is private to your account.</div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="workspace">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">A</span><span>AURA</span></div>
        <div className="workspace-label">WORKSPACE <span className="local-badge">LOCAL</span></div>
        <nav className="side-nav"><a className="nav-item active" href="#library"><span>▤</span> Library <b>{documents.length}</b></a><a className="nav-item" href="#research"><span>⌕</span> Research</a></nav>
        <div className="sidebar-bottom">
          <div className="privacy-card"><span className="privacy-icon">◈</span><div><strong>Private by design</strong><small>Documents stay on this machine.</small></div></div>
          <button className="profile" onClick={signOut}><span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span><span className="profile-info"><strong>{user.email}</strong><small>Personal workspace</small></span><span className="signout">↗</span></button>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar"><div><span className="breadcrumb">Workspace</span><span className="crumb-slash">/</span><strong>Research desk</strong></div><div className="topbar-right"><span className="secure-dot" /> Local session <span className="top-avatar">{user.email.slice(0, 1).toUpperCase()}</span></div></header>
        <div className="content">
          <div className="page-heading"><div><p className="eyebrow">YOUR PRIVATE KNOWLEDGE BASE</p><h1>Research desk<span className="title-dot">.</span></h1><p className="subtle">Bring your sources together. Ask questions grounded in what you’ve read.</p></div><div className="date-mark">{new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })}<small>LOCAL WORKSPACE</small></div></div>
          {(error || notice) && <div className={error ? "toast error-box" : "toast success-box"} role={error ? "alert" : "status"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss">×</button></div>}

          <section className="library-section" id="library">
            <div className="section-heading"><div><h2>Your library <span className="count-pill">{documents.length}</span></h2><p>Only your documents are visible in this workspace.</p></div><span className="section-caption">PDF · DOCX · TXT · MD</span></div>
            <form className="upload-zone" onSubmit={upload}>
              <div className="upload-symbol">↑</div><div className="upload-copy"><strong>Add a source to your library</strong><span>Drop a file here or choose from your device · 20 MB max</span></div>
              <label className="secondary-button file-button">Choose file<input name="document" type="file" accept=".pdf,.docx,.txt,.md,.markdown" required /></label>
              <button className="primary-button upload-submit" disabled={loading}>Upload</button>
            </form>
            {documents.length === 0 ? <div className="empty-library"><div className="empty-icon">▤</div><strong>Your library is ready when you are</strong><p>Upload a PDF, DOCX, text, or Markdown file to begin your research.</p></div> :
              <div className="document-list">{documents.map((doc) => <article className="document-row" key={doc.id}><div className={`file-icon ${doc.filename.toLowerCase().endsWith(".pdf") ? "pdf" : "text-file"}`}>{doc.filename.split(".").pop()?.toUpperCase().slice(0, 4)}</div><div className="document-meta"><strong>{doc.filename}</strong><span>{formatBytes(doc.size_bytes)} <i>·</i> Added {new Date(doc.created_at).toLocaleDateString()}</span></div><span className="ready-state"><span /> Ready</span><button className="icon-button" title={`Delete ${doc.filename}`} onClick={() => deleteDocument(doc)}>⌫</button></article>)}</div>}
          </section>

          <section className="research-grid" id="research">
            <div className="research-card ask-card">
              <div className="card-kicker"><span className="card-icon">✳</span><span>ASK YOUR SOURCES</span></div><h2>What would you like to understand?</h2><p>Answers are grounded in passages from your library. No evidence, no invented answer.</p>
              <form className="question-form" onSubmit={ask}><textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question about your documents…" required minLength={2} maxLength={2000} /><div className="question-actions"><span>{documents.length === 0 ? "Add a document to get started" : `Searching across ${documents.length} ${documents.length === 1 ? "source" : "sources"}`}</span><button className="primary-button" disabled={loading || documents.length === 0 || !question.trim()}>{loading ? "Thinking…" : "Ask AURA"} <span>→</span></button></div></form>
              {answer && <div className={`answer-panel ${answer.abstained ? "abstain" : ""}`}><div className="answer-label"><span>{answer.abstained ? "INSUFFICIENT EVIDENCE" : "EVIDENCE-BASED RESPONSE"}</span><span>{answer.citations.length} {answer.citations.length === 1 ? "source" : "sources"}</span></div><p className="answer-text">{answer.answer}</p>{answer.citations.length > 0 && <div className="citation-list"><strong>Sources</strong>{answer.citations.map((citation, index) => <details className="citation" key={citation.chunk_id}><summary><span className="citation-number">S{index + 1}</span><span>{citation.filename}{citation.page_number ? ` · page ${citation.page_number}` : ""}</span><span className="citation-chevron">⌄</span></summary><p>{citation.excerpt}</p></details>)}</div>}</div>}
            </div>
            <div className="research-card search-card">
              <div className="card-kicker"><span className="search-icon">⌕</span><span>PASSAGE SEARCH</span></div><h2>Find the exact passage</h2><p>Search your indexed documents and inspect matching excerpts.</p>
              <form className="search-form" onSubmit={search}><div className="search-input-wrap"><span>⌕</span><input value={searchText} onChange={(e) => setSearchText(e.target.value)} placeholder="Search a topic or phrase…" required minLength={2} /></div><button className="secondary-button" disabled={loading || !searchText.trim()}>Search</button></form>
              {searchResults.length > 0 && <div className="search-results">{searchResults.map((item, i) => <details key={item.chunk_id} className="search-result"><summary><span className="result-rank">0{i + 1}</span><span><strong>{item.filename}</strong><small>{item.page_number ? `Page ${item.page_number}` : "Text passage"} · relevance {Math.round(item.score * 100)}%</small></span><span>⌄</span></summary><p>{item.excerpt}</p></details>)}</div>}
              {searchResults.length === 0 && searchText && !loading && <div className="search-hint">Search results will appear here. Results are limited to your library.</div>}
              {!searchText && <div className="search-note"><span>◈</span> Search is private and scoped to your account.</div>}
            </div>
          </section>
          <footer className="page-footer"><span>AURA · YOUR KNOWLEDGE. YOUR CONTROL.</span><span>Local-first research workspace</span></footer>
        </div>
      </section>
    </main>
  );
}
