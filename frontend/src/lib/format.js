// Turn raw query output into something a non-technical person can read:
// "total_revenue" -> "Total revenue", "2015-07" -> "Jul 2015", 72557.9 -> "$72,557.90", hour 12 -> "12 PM".

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function humanizeColumn(name) {
  const words = String(name)
    .replace(/_/g, " ")
    .replace(/\b(avg)\b/gi, "average")
    .replace(/\b(pct)\b/gi, "percent")
    .replace(/\b(qty)\b/gi, "quantity")
    .replace(/\s+/g, " ")
    .trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const isCount = (col) => /count|orders?\b|pizzas|quantit|units|sold|number|\bn\b|days|items/i.test(col);

export function columnKind(col) {
  const c = String(col).toLowerCase();
  if (/percent|pct|share|rate/.test(c)) return "percent";
  if (/revenue|price|spend|sales|amount|value|cost/.test(c)) return "money";
  if (/total/.test(c) && !isCount(c)) return "money";
  if (/^hour|_hour$|^hr$/.test(c)) return "hour";
  return "plain";
}

function formatDateish(s) {
  let m = /^(\d{4})-(\d{2})$/.exec(s);
  if (m) return `${MONTHS[+m[2] - 1]} ${m[1]}`;
  m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (m) return `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}`;
  return s;
}

export function formatHour(h) {
  const n = Number(h);
  if (!Number.isInteger(n) || n < 0 || n > 23) return String(h);
  if (n === 0) return "12 AM";
  if (n === 12) return "12 PM";
  return n < 12 ? `${n} AM` : `${n - 12} PM`;
}

export function formatValue(value, column) {
  if (value === null || value === undefined) return "—";
  const kind = columnKind(column);
  if (typeof value === "string") {
    if (kind === "hour" && /^\d{1,2}$/.test(value)) return formatHour(value);
    return formatDateish(value);
  }
  if (typeof value !== "number") return String(value);
  if (kind === "hour") return formatHour(value);
  if (kind === "money") return "$" + value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (kind === "percent") return value.toLocaleString(undefined, { maximumFractionDigits: 2 }) + "%";
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export const isNumeric = (v) => typeof v === "number";
