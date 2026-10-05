import { useState } from "react";
import BarChart, { chartable } from "./BarChart.jsx";
import ResultsTable from "./ResultsTable.jsx";

function summary(r) {
  const secs = (r.total_ms / 1000).toFixed(1);
  const tries = r.attempts.length;
  const tokens = (r.input_tokens + r.output_tokens).toLocaleString();
  const how = tries === 1 ? "on the first try" : `after ${tries} tries`;
  if (r.status === "ok") return `Answered in ${secs} seconds ${how}, using ${tokens} tokens.`;
  return `Took ${secs} seconds and ${tokens} tokens.`;
}

export default function ResultView({ item, onEdit, onAsk }) {
  const r = item.result;

  return (
    <article className="result">
      <header className="result-head">
        <h1 className="result-title">{item.question}</h1>
        {r.status === "ok" && r.answer && <p className="result-answer">{r.answer}</p>}
        {r.status === "ok" && r.explanation && (
          <p className={r.answer ? "result-looked" : "result-expl"}>
            {r.answer ? <>What it looked up: {r.explanation}</> : r.explanation}
          </p>
        )}
        <div className="row-actions">
          <button className="btn btn-ghost btn-small" onClick={onEdit}>Edit question</button>
          <button className="btn btn-ghost btn-small" onClick={() => onAsk(item.question)}>Ask again</button>
        </div>
      </header>

      {r.status === "ok" && <Answer r={r} />}

      {r.status === "unanswerable" && (
        <div className="notice">
          <h2>The pizza data can't answer this one</h2>
          <p>{r.explanation || "The data needed for this question isn't in the database."}</p>
        </div>
      )}

      {r.status === "failed" && (
        <>
          <div className="notice notice-error">
            <h2>QueryPilot couldn't write a query that runs</h2>
            <p>It tried {r.attempts.length} times. Rewording the question often helps, for example by naming the table or column you mean.</p>
          </div>
          <h2 className="tried-title">What it tried</h2>
          <StepsLog attempts={r.attempts} />
        </>
      )}

      <p className="result-meta">{summary(r)}</p>
    </article>
  );
}

function Answer({ r }) {
  const canChart = chartable(r);
  const [tab, setTab] = useState("answer");
  const [asChart, setAsChart] = useState(canChart);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(r.sql || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked; the SQL is still selectable */
    }
  };

  const tabs = [
    ["answer", "Answer"],
    ["sql", "SQL"],
    ["steps", r.attempts.length > 1 ? `Steps (${r.attempts.length})` : "Steps"],
  ];

  return (
    <>
      <div className="tabs" role="tablist" aria-label="Result views">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={`tab ${tab === id ? "is-on" : ""}`}
                  onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

      <div className="tab-panel" role="tabpanel">
        {tab === "answer" && (
          <>
            {canChart && (
              <div className="view-toggle">
                <button className={asChart ? "is-on" : ""} onClick={() => setAsChart(true)}>Chart</button>
                <button className={!asChart ? "is-on" : ""} onClick={() => setAsChart(false)}>Table</button>
              </div>
            )}
            {canChart && asChart ? <BarChart result={r} /> : <ResultsTable result={r} />}
            {r.truncated && (
              <p className="fine">Showing the first {r.row_count} rows. Add a filter or a "top N" to narrow it down.</p>
            )}
          </>
        )}

        {tab === "sql" && (
          <div className="sql-wrap">
            <button className="btn btn-ghost btn-small sql-copy" onClick={copy}>{copied ? "Copied" : "Copy SQL"}</button>
            <pre className="sql">{r.sql}</pre>
            <p className="fine">This is the exact query that ran, after the safety check added a row limit.</p>
          </div>
        )}

        {tab === "steps" && <StepsLog attempts={r.attempts} />}
      </div>
    </>
  );
}

function StepsLog({ attempts }) {
  return (
    <ol className="steps-log">
      {attempts.map((a, i) => (
        <li key={i} className={a.error ? "is-bad" : "is-good"}>
          <p className="steps-head">
            {i === 0 ? "First try" : i === 1 ? "Second try" : `Try ${i + 1}`}
            {": "}
            {a.error ? "failed" : a.sql ? "worked" : "no query, the data can't answer this"}
          </p>
          {a.sql && <pre className="sql sql-small">{a.sql}</pre>}
          {a.error && <p className="steps-err">{a.error}</p>}
          {a.error && i < attempts.length - 1 && (
            <p className="fine">The error was sent back to the model so it could fix the query.</p>
          )}
        </li>
      ))}
    </ol>
  );
}
