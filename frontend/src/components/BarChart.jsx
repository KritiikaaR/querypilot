// A dependency-free horizontal bar chart for "label + number" results.
// The biggest bar is drawn darker so the answer stands out.
import { formatValue, humanizeColumn } from "../lib/format.js";

export function chartable(result) {
  if (!result || result.status !== "ok") return false;
  const { columns, rows } = result;
  if (columns.length !== 2 || rows.length < 2 || rows.length > 31) return false;
  return rows.every((r) => typeof r[1] === "number" && r[1] >= 0);
}

export default function BarChart({ result }) {
  const [labelCol, valueCol] = result.columns;
  const values = result.rows.map((r) => r[1]);
  const max = Math.max(...values, 0) || 1;
  const top = values.indexOf(Math.max(...values));

  return (
    <figure className="chart" aria-label={`${humanizeColumn(valueCol)} by ${humanizeColumn(labelCol)}`}>
      <div className="chart-axis" aria-hidden="true">
        <span>{humanizeColumn(labelCol)}</span>
        <span>{humanizeColumn(valueCol)}</span>
      </div>
      {result.rows.map(([label, value], i) => (
        <div className={`bar-row ${i === top ? "is-top" : ""}`} key={i}>
          <span className="bar-label" title={String(label)}>{formatValue(label, labelCol)}</span>
          <span className="bar-track">
            <span className="bar" style={{ width: `${Math.max(0.8, (value / max) * 100)}%` }} />
          </span>
          <span className="bar-value">{formatValue(value, valueCol)}</span>
        </div>
      ))}
    </figure>
  );
}
