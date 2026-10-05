import { Link } from "react-router-dom";

// Three highlighter strokes: phrases in a question becoming parts of a query.
export default function Logo({ to = "/" }) {
  return (
    <Link to={to} className="logo" aria-label="QueryPilot home">
      <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="var(--ink)" />
        <rect x="7" y="9" width="12" height="4" rx="2" fill="var(--hl-amber)" />
        <rect x="7" y="16" width="18" height="4" rx="2" fill="var(--hl-blue)" />
        <rect x="7" y="23" width="8" height="4" rx="2" fill="var(--hl-green)" />
      </svg>
      <span>QueryPilot</span>
    </Link>
  );
}
