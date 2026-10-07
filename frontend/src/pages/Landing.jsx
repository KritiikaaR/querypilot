import { Link } from "react-router-dom";
import HeroDemo from "../components/HeroDemo.jsx";
import Logo from "../components/Logo.jsx";
import { DATA_SOURCE, EVAL_RESULTS, GITHUB_PROFILE, GITHUB_REPO } from "../content.js";

export default function Landing() {
  const facts = [
    "Read-only, so it can't change your data",
    EVAL_RESULTS &&
      `${EVAL_RESULTS.accuracy}% right on ${EVAL_RESULTS.questions} test questions` +
        (EVAL_RESULTS.runs > 1 ? ` (average of ${EVAL_RESULTS.runs} runs)` : ""),
    "Built with FastAPI, React and OpenAI",
  ].filter(Boolean);

  return (
    <div className="landing">
      <header className="site-nav">
        <Logo />
        <nav aria-label="Main">
          <a href={GITHUB_REPO} target="_blank" rel="noreferrer">GitHub</a>
          <Link to="/app" className="btn btn-small">Open the app</Link>
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <h1>Ask a database a question in plain English.</h1>
            <p className="lede">Ask it like you'd ask a coworker. It writes the SQL and shows you the answer.</p>
            <div className="hero-actions">
              <Link to="/app" className="btn">Try it on pizza sales</Link>
              <a href={GITHUB_REPO} className="btn btn-ghost" target="_blank" rel="noreferrer">Read the code</a>
            </div>
            <p className="hero-note">
              Demo data: <a href={DATA_SOURCE} target="_blank" rel="noreferrer">Pizza Place Sales</a> by Maven Analytics
            </p>
          </div>
          <HeroDemo />
        </section>

        <section className="about">
          <p className="about-line">
            It reads the menu, writes the SQL, checks it can't change anything, and runs it. If it messes up, it
            reads the error and tries again.
          </p>
          <ul className="facts">
            {facts.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </section>

        <section className="cta">
          <h2>Ask it something.</h2>
          <Link to="/app" className="btn">Try it on pizza sales</Link>
        </section>
      </main>

      <footer className="site-foot">
        <span>Built by <a href={GITHUB_PROFILE} target="_blank" rel="noreferrer">Kritika Regmi</a></span>
        <a href={GITHUB_REPO} target="_blank" rel="noreferrer">Source on GitHub</a>
      </footer>
    </div>
  );
}
