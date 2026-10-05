// Saved questions live in this browser only. Storage can be unavailable
// (private windows, blocked site data), so every access is guarded.
const KEY = "querypilot.history.v1";
const MAX_ITEMS = 50;

export function loadHistory() {
  try {
    const raw = window.localStorage.getItem(KEY);
    const items = raw ? JSON.parse(raw) : [];
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

export function saveHistory(items) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
  } catch {
    /* storage full or blocked: history just won't persist */
  }
}

export const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
