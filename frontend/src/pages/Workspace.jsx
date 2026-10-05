import { useEffect, useRef, useState } from "react";
import { askQuestion, getSchema } from "../api.js";
import Logo from "../components/Logo.jsx";
import ResultView from "../components/ResultView.jsx";
import { SUGGESTIONS, TABLE_NOTES } from "../content.js";
import { loadHistory, newId, saveHistory } from "../lib/history.js";

export default function Workspace() {
  const [history, setHistory] = useState(loadHistory); // newest first
  const [activeId, setActiveId] = useState(null);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(null); // question currently being answered
  const [error, setError] = useState(null); // { question, message }
  const [tables, setTables] = useState([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => saveHistory(history), [history]);
  useEffect(() => {
    getSchema().then((d) => setTables(d.tables)).catch(() => {});
  }, []);

  const active = history.find((h) => h.id === activeId) || null;

  async function ask(text) {
    const question = (text ?? input).trim();
    if (question.length < 3 || pending) return;
    setPending(question);
    setError(null);
    setActiveId(null);
    setMenuOpen(false);
    try {
      const result = await askQuestion(question);
      const item = { id: newId(), question, result, askedAt: Date.now() };
      setHistory((h) => [item, ...h]);
      setActiveId(item.id);
      setInput("");
    } catch (e) {
      setError({ question, message: e.message });
    } finally {
      setPending(null);
    }
  }

  function startNew(prefill = "") {
    setActiveId(null);
    setError(null);
    setInput(prefill);
    setMenuOpen(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function open(id) {
    setActiveId(id);
    setError(null);
    setMenuOpen(false);
  }

  function remove(id) {
    setHistory((h) => h.filter((x) => x.id !== id));
    if (id === activeId) setActiveId(null);
  }

  const showEmpty = !active && !pending && !error;

  return (
    <div className="ws">
      <aside className={`ws-side ${menuOpen ? "is-open" : ""}`} aria-label="Your questions">
        <div className="ws-side-top">
          <Logo />
          <button className="icon-btn ws-close" onClick={() => setMenuOpen(false)} aria-label="Close menu">✕</button>
        </div>

        <button className="btn ws-new" onClick={() => startNew()}>New question</button>

        <div className="ws-history">
          <h2 className="ws-side-title">Your questions</h2>
          {history.length === 0 ? (
            <p className="ws-side-empty">Questions you ask show up here, so you can come back to them.</p>
          ) : (
            <ul>
              {history.map((h) => (
                <li key={h.id} className={h.id === activeId ? "is-active" : ""}>
                  <button className="ws-item" onClick={() => open(h.id)} title={h.question}>
                    <span className={`dot dot-${h.result.status}`} aria-hidden="true" />
                    <span className="ws-item-text">{h.question}</span>
                  </button>
                  <button className="icon-btn ws-del" onClick={() => remove(h.id)} aria-label={`Remove "${h.question}"`}>✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <details className="ws-data">
          <summary>Pizza shop data</summary>
          <ul>
            {tables.map((t) => (
              <li key={t.name}>
                <code>{t.name}</code>
                <span>{t.row_count.toLocaleString()} rows</span>
                <p>{t.columns.map((c) => c.name).join(", ")}</p>
              </li>
            ))}
          </ul>
        </details>
      </aside>
      {menuOpen && <div className="ws-scrim" onClick={() => setMenuOpen(false)} aria-hidden="true" />}

      <main className="ws-main">
        <div className="ws-topbar">
          <button className="icon-btn ws-menu" onClick={() => setMenuOpen(true)} aria-label="Open your questions">
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 4h14M2 9h14M2 14h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
          <form
            className="ask"
            onSubmit={(e) => {
              e.preventDefault();
              ask();
            }}
          >
            <label htmlFor="q" className="sr-only">Ask a question about the pizza shop</label>
            <input
              id="q"
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about orders, pizzas, sizes, prices, or ingredients"
              maxLength={500}
              autoComplete="off"
              autoFocus
            />
            <button type="submit" className="btn" disabled={!!pending || input.trim().length < 3}>
              {pending ? "Asking…" : "Ask"}
            </button>
          </form>
        </div>

        <div className="ws-body">
          {pending && (
            <div className="ws-pending" role="status">
              <h1 className="result-title">{pending}</h1>
              <p className="pending-line"><span className="spinner" aria-hidden="true" /> Writing the SQL and running it. This usually takes a few seconds.</p>
            </div>
          )}

          {error && !pending && (
            <div className="ws-error" role="alert">
              <h1 className="result-title">{error.question}</h1>
              <p>QueryPilot couldn't reach the server: {error.message}</p>
              <div className="row-actions">
                <button className="btn" onClick={() => ask(error.question)}>Try again</button>
                <button className="btn btn-ghost" onClick={() => startNew(error.question)}>Edit question</button>
              </div>
            </div>
          )}

          {active && !pending && (
            <ResultView key={active.id} item={active} onEdit={() => startNew(active.question)} onAsk={ask} />
          )}

          {showEmpty && (
            <div className="ws-empty">
              <h1>What do you want to know about the pizza shop?</h1>
              <p className="ws-empty-sub">
                Type a question above, or start with one of these. You'll get the answer and the SQL that produced it.
              </p>
              <div className="suggest">
                {SUGGESTIONS.map((group) => (
                  <section key={group.topic}>
                    <h2>{group.topic}</h2>
                    <ul>
                      {group.questions.map((q) => (
                        <li key={q}>
                          <button className="suggest-q" onClick={() => ask(q)}>{q}</button>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
              <p className="ws-empty-foot">
                The data covers every order from 2015 in {Object.keys(TABLE_NOTES).length} tables: orders, the pizzas in
                each order, the menu with sizes and prices, and pizza types with their ingredients. There's no customer,
                delivery, or cost data, so it can't answer questions about those.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
