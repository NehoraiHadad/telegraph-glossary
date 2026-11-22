// Telegram Mini App bridge. Outside Telegram every helper falls back to normal
// browser behaviour, so the same app runs as a website and as a Mini App.

const W = globalThis.Telegram?.WebApp;
export const inTelegram = !!(W && W.initData);
export const tgUser = inTelegram ? W.initDataUnsafe?.user || null : null;
export const initData = inTelegram ? W.initData : "";
const atLeast = (v) => inTelegram && W.isVersionAtLeast?.(v);

export function start() {
  if (!inTelegram) return;
  W.ready();
  W.expand?.();
  applyTheme();
  W.onEvent?.("themeChanged", applyTheme);
}

// Map Telegram's theme onto our tokens, so the app looks native in every Telegram theme.
function applyTheme() {
  const p = W.themeParams || {};
  const root = document.documentElement;
  root.dataset.theme = W.colorScheme === "dark" ? "dark" : "light";
  const map = {
    "--paper": p.secondary_bg_color, "--surface": p.bg_color, "--ink": p.text_color, "--muted": p.hint_color,
    "--link": p.link_color, "--action": p.button_color, "--action-ink": p.button_text_color,
    "--sunken": p.secondary_bg_color, "--danger": p.destructive_text_color,
  };
  for (const [k, v] of Object.entries(map)) if (v) root.style.setProperty(k, v);
  if (p.section_separator_color) root.style.setProperty("--line", p.section_separator_color);
  if (p.bg_color) W.setHeaderColor?.(p.bg_color);
}

// ---- CloudStorage: per user, kept by Telegram, synced across the user's devices.
// Our servers never see it. Used for the glossary key.
const cloudOk = () => atLeast("6.9") && W.CloudStorage;
export function cloudGet(key) {
  if (!cloudOk()) return Promise.resolve(null);
  return new Promise((res) => W.CloudStorage.getItem(key, (err, v) => res(err ? null : v || null)));
}
export function cloudSet(key, value) {
  if (!cloudOk()) return Promise.resolve(false);
  return new Promise((res) => W.CloudStorage.setItem(key, value, (err, ok) => res(!err && ok !== false)));
}
export function cloudRemove(key) {
  if (!cloudOk()) return Promise.resolve(false);
  return new Promise((res) => W.CloudStorage.removeItem(key, (err) => res(!err)));
}
export const hasCloud = () => !!cloudOk();

// ---- links
export function openTelegram(url) {
  if (inTelegram && /^https:\/\/t\.me\//.test(url)) return W.openTelegramLink(url);
  window.open(url, "_blank", "noopener");
}
export function openExternal(url) {
  if (inTelegram) return W.openLink(url);
  window.open(url, "_blank", "noopener");
}
/** Inside Telegram, plain target=_blank links must go through the bridge. */
export function routeLinks(root) {
  if (!inTelegram) return;
  root.addEventListener("click", (e) => {
    const a = e.target.closest?.("a[href]");
    if (!a || a.getAttribute("role") === "button" || a.hasAttribute("download")) return;
    const href = a.href;
    if (!/^https?:/.test(href) || href.startsWith(location.origin + location.pathname + "#")) return;
    e.preventDefault();
    /^https:\/\/t\.me\//.test(href) ? openTelegram(href) : openExternal(href);
  });
}

// ---- dialogs (window.confirm is unreliable in mobile webviews)
export function confirmDialog(message) {
  if (inTelegram && W.showConfirm) return new Promise((res) => W.showConfirm(message, (ok) => res(!!ok)));
  return Promise.resolve(window.confirm(message));
}

export function haptic(kind = "success") {
  if (inTelegram) W.HapticFeedback?.notificationOccurred?.(kind);
}

/** "Share to…" sheet; the user picks Saved Messages. Nothing passes through our servers. */
export function shareToTelegram(url, text) {
  openTelegram(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
}

/** Run when the user comes back to the app (tab focus, or Mini App re-activated). */
export function onReturn(fn) {
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") fn(); });
  if (inTelegram) W.onEvent?.("activated", fn);
}
