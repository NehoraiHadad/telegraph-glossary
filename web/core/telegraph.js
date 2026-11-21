// Tiny Telegraph API client (https://telegra.ph/api). The API sends CORS
// headers, so this runs directly in the browser.

const API = "https://api.telegra.ph";

export class TelegraphError extends Error {}

export async function call(method, params = {}, fetchImpl = globalThis.fetch) {
  const body = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    body.set(k, typeof v === "string" ? v : JSON.stringify(v));
  }
  // form-encoded POST is a "simple" CORS request: no preflight needed.
  const res = await fetchImpl(`${API}/${method}`, { method: "POST", body });
  const data = await res.json();
  if (!data.ok) throw new TelegraphError(data.error || `Telegraph ${method} failed`);
  return data.result;
}

export const pageUrl = (path) => `https://telegra.ph/${encodeURIComponent(path)}`;
// Telegraph rewrites links to its own pages as relative, percent-encoded
// paths ("/%D7%90-11-21"), so accept both absolute and relative forms.
export const pathFromUrl = (url) => {
  const m = /^(?:https?:\/\/(?:telegra\.ph|graph\.org))?\/([^?#/]+)$/.exec(url || "");
  if (!m) return null;
  try { return decodeURIComponent(m[1]); } catch { return m[1]; }
};
