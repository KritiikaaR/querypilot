const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    const err = new Error(detail);
    err.status = res.status; // 429/503 carry a message meant to be shown to the user as-is
    throw err;
  }
  return res.json();
}

// The hosted backend sleeps when idle and takes 30-60 s to wake. Pinging it as soon as a
// page loads starts that early. Fire and forget: the result and any error are ignored.
export function warmUp() {
  fetch(`${BASE}/api/health`).catch(() => {});
}

export const getExamples = () => request("/api/examples");
export const getSchema = () => request("/api/schema");
export const askQuestion = (question) =>
  request("/api/query", { method: "POST", body: JSON.stringify({ question }) });
