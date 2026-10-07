import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSchema } from "../api.js";
import HeroDemo from "../components/HeroDemo.jsx";
import Logo from "../components/Logo.jsx";
import { DATA_SOURCE, EVAL_RESULTS, GITHUB_PROFILE, GITHUB_REPO, TABLE_NOTES } from "../content.js";

const FALLBACK_COUNTS = { orders: 21350, order_details: 48620, pizzas: 96, pizza_types: 32 };
const TABLE_ORDER = ["orders", "order_details", "pizzas", "pizza_types"];

export default function Landing() {
  const [counts, setCounts] = useState(FALLBACK_COUNTS);

  useEffect(() => {
    getSchema()
      .then((d) => setCounts(Object.fromEntries(d.tables.map((t) => [t.name, t.row_count]))))
      .catch(() => {});
  }, []);

  return (
    <div className="landing">
      <header className="site-nav">
        <Logo />
        <nav aria-label="Main">
          <a href="#how">How it works</a>
          <a href="#safety">Safety</a>
          <a href={GITHUB_REPO} target="_blank" rel="noreferrer">GitHub</a>
          <Link to="/app" className="btn btn-small">Open the app</Link>
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <h1>Ask a database a question in plain English.</h1>
            <p className="lede">
              QueryPilot turns your question into SQL, checks that it can only read data, runs it,
              and shows you the answer with the exact query it used.
            </p>
            <div className="hero-actions">
              <Link to="/app" className="btn">Try it on pizza sales</Link>
              <a href={GITHUB_REPO} className="btn btn-ghost" target="_blank" rel="noreferrer">Read the code</a>
            </div>
            <p className="hero-sub">
              No sign-up. The demo data is a year of sales from a pizza shop: {counts.orders?.toLocaleString()} orders.
            </p>
          </div>
          <HeroDemo />
        </section>

        <section id="how" className="band">
          <div className="band-head">
            <h2>How it works</h2>
            <p>Every question goes through the same four steps. If the query fails, QueryPilot reads the error and tries again.</p>
          </div>

          <ol className="steps">
            <li>
              <h3>Read the schema</h3>
              <p>The model sees every table, its columns, a few sample rows, and notes like "revenue is quantity × price paid".</p>
            </li>
            <li>
              <h3>Write the SQL</h3>
              <p>It writes one query and a one-line explanation. If the data can't answer the question, it says so instead of guessing.</p>
            </li>
            <li>
              <h3>Check it</h3>
              <p>Before anything runs, the query is parsed and rejected unless it's a single read-only SELECT. A row limit is added.</p>
            </li>
            <li>
              <h3>Run it</h3>
              <p>The query runs on a read-only copy of the database with a 3-second time limit, and the result comes back as a chart or table.</p>
            </li>
          </ol>

          <div className="retry">
            <div className="retry-copy">
              <h3>When it gets something wrong</h3>
              <p>
                Models make typos too. Here the first query used a table that doesn't exist. The database error went back
                to the model, and the second query worked. You can see every attempt in the app.
              </p>
            </div>
            <div className="retry-attempts">
              <div className="attempt attempt-bad">
                <span className="attempt-label">First try</span>
                <code>… FROM <mark>order_detail</mark> od JOIN pizzas p …</code>
                <span className="attempt-msg">no such table: order_detail</span>
              </div>
              <div className="attempt attempt-good">
                <span className="attempt-label">Second try</span>
                <code>… FROM <mark>order_details</mark> od JOIN pizzas p …</code>
                <span className="attempt-msg">Ran and returned 5 rows</span>
              </div>
            </div>
          </div>
        </section>

        <section id="safety" className="band band-split">
          <div className="band-head">
            <h2>It can look, but it can't touch</h2>
            <p>
              Letting a model write SQL against real data is only okay if it can't break anything. QueryPilot stacks
              several protections, so one bug in one layer doesn't become lost data.
            </p>
          </div>
          <div className="safety">
            <div className="blocked" aria-label="Example of a rejected query">
              <code className="blocked-q">DELETE FROM orders WHERE date &lt; '2015-07-01'</code>
              <p className="blocked-a">
                Rejected before it ran: only read-only SELECT queries are allowed; this statement is DELETE.
              </p>
            </div>
            <dl className="protections">
              <div><dt>One statement, read-only</dt><dd>No DELETE, DROP, UPDATE, PRAGMA, ATTACH, or stacked queries.</dd></div>
              <div><dt>Read-only database</dt><dd>Even if a write slipped past the check, the connection itself can't write.</dd></div>
              <div><dt>Time limit</dt><dd>Runaway queries are stopped after 3 seconds.</dd></div>
              <div><dt>Row cap</dt><dd>Results are capped at 200 rows, and the app tells you when it cut some off.</dd></div>
            </dl>
          </div>
        </section>

        <section className="band">
          <div className="band-head">
            <h2>The demo data: a year at a pizza shop</h2>
            <p>
              Every order from 2015 at one pizza place, from the public{" "}
              <a href={DATA_SOURCE} target="_blank" rel="noreferrer">Pizza Place Sales</a> dataset by Maven Analytics.
              The shop is fictional; the data is loaded as published, with dates and times cleaned up so they sort
              correctly. Try asking which day sold the most pizzas. It's a holiday.
            </p>
          </div>
          <table className="tables-overview">
            <thead>
              <tr><th>Table</th><th>What it holds</th><th className="num">Rows</th></tr>
            </thead>
            <tbody>
              {TABLE_ORDER.map((t) => (
                <tr key={t}>
                  <td><code>{t}</code></td>
                  <td>{TABLE_NOTES[t]}</td>
                  <td className="num">{counts[t]?.toLocaleString() ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="band band-split">
          <div className="band-head">
            <h2>How it's tested</h2>
            <p>
              QueryPilot is checked against 30 questions with hand-written answers. A question counts as correct only if
              the result matches the expected rows exactly, not just if the query runs.
            </p>
          </div>
          {EVAL_RESULTS ? (
            <div className="eval">
              <p className="eval-big">{EVAL_RESULTS.accuracy}%</p>
              <p className="eval-label">
                {`of ${EVAL_RESULTS.questions} questions answered correctly with ${EVAL_RESULTS.model}`}
                {EVAL_RESULTS.runs > 1 ? `, averaged over ${EVAL_RESULTS.runs} runs.` : "."}{" "}
                {EVAL_RESULTS.selfCorrected > 0 && `${EVAL_RESULTS.selfCorrected} needed a second try.`}
              </p>
            </div>
          ) : (
            <ul className="eval-mix">
              <li><strong>8 easy</strong> counts and simple filters</li>
              <li><strong>10 medium</strong> revenue, joins, busiest hours, and averages</li>
              <li><strong>10 hard</strong> ingredients, weekdays, rankings, and days the shop was closed</li>
              <li><strong>2 to refuse</strong> like delivery drivers or profit, which the data doesn't cover</li>
            </ul>
          )}
        </section>

        <section className="cta">
          <h2>Ask it something.</h2>
          <Link to="/app" className="btn">Try it on pizza sales</Link>
        </section>
      </main>

      <footer className="site-foot">
        <span>
          Built by <a href={GITHUB_PROFILE} target="_blank" rel="noreferrer">Kritika Regmi</a> with FastAPI, React, and OpenAI.
          Data: <a href={DATA_SOURCE} target="_blank" rel="noreferrer">Maven Analytics</a> (public domain).
        </span>
        <a href={GITHUB_REPO} target="_blank" rel="noreferrer">Source on GitHub</a>
      </footer>
    </div>
  );
}
