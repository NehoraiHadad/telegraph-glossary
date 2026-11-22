import { STRINGS } from "./i18n.js";
import { Glossary, APP_URL } from "./core/glossary.js";
import { findTerms, toTelegramHtml, toMarkdown, toPlain } from "./core/linker.js";
import { markdownToNodes, nodesToHtml } from "./core/markdown.js";
import * as tg from "./core/telegram.js";
import * as mini from "./tg.js";

const REPO = "git+https://github.com/NehoraiHadad/telegraph-glossary";

// ---------------------------------------------------------------- storage
const store = {
  get(k, d = null) { try { const v = localStorage.getItem("tgg." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { v === null ? localStorage.removeItem("tgg." + k) : localStorage.setItem("tgg." + k, JSON.stringify(v)); } catch {} },
};

const state = {
  lang: store.get("lang") || ((mini.tgUser?.language_code || navigator.language || "").startsWith("he") ? "he" : "en"),
  token: store.get("token"),
  glossary: null,
  tab: store.get("tab", "terms"),
  draft: store.get("draft", ""),
  excluded: new Set(),
  mode: store.get("mode", "first"),
  bot: store.get("bot", null), // the user's own bot (advanced): {token, username}
  chats: store.get("chats", []),
  chatId: store.get("chatId", null),
  autoBot: null, // {api, username} of the auto-link bot, from config.json
  channels: store.get("channels", []), // channels the auto-link bot serves for this glossary
  waiting: false, // user went to Telegram to connect a channel
  keySaved: store.get("keySaved", false),
  tried: store.get("tried", false),
  setupHidden: store.get("setupHidden", false),
  agent: store.get("agent", "claude"),
  selection: "",
  query: "",
};

const t = (k, ...a) => { const v = STRINGS[state.lang][k] ?? STRINGS.en[k]; return typeof v === "function" ? v(...a) : v; };

// ---------------------------------------------------------------- DOM helpers
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k === "value") el.value = v;
    else if (k in el && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}
const $app = document.getElementById("app");

function toast(msg, kind = "") {
  const el = h("div", { class: `toast ${kind}` }, msg);
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 6000 : 2200);
}
const fail = (e) => { console.error(e); toast(`${t("error")}: ${e.message || e}`, "error"); };

async function busy(btn, fn) {
  const label = [...btn.childNodes];
  btn.disabled = true;
  btn.replaceChildren(h("span", { class: "spin" }));
  try { return await fn(); } catch (e) { fail(e); } finally { btn.disabled = false; btn.replaceChildren(...label); }
}

async function copyText(s, msg = t("copied")) {
  try { await navigator.clipboard.writeText(s); toast(msg); return true; } catch { /* some webviews block it */ }
  const ta = h("textarea", { value: s, readOnly: true, style: "position:fixed;opacity:0" });
  document.body.append(ta); ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  ok ? toast(msg) : fail(new Error("clipboard"));
  return ok;
}

function applyLang() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = state.lang === "he" ? "rtl" : "ltr";
}

// ---------------------------------------------------------------- the key
// In the browser the key is the user's responsibility (download / Saved Messages).
// Inside Telegram it is also kept in Telegram's CloudStorage: per user, synced, never on our servers.
async function rememberKey(token) {
  state.token = token;
  store.set("token", token);
  if (await mini.cloudSet("tgg_key", token)) keySaved();
}

// ---------------------------------------------------------------- auto-link bot
async function loadConfig() {
  try {
    const cfg = await (await fetch("config.json", { cache: "no-store" })).json();
    if (!cfg.bot_api) return;
    const api = cfg.bot_api.replace(/\/$/, "");
    const info = await (await fetch(`${api}/api/info`)).json();
    state.autoBot = { api, username: info.bot_username };
  } catch { /* the feature stays hidden */ }
}

async function botApi(path, body) {
  const res = await fetch(state.autoBot.api + path, body
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function refreshChannels() {
  if (!state.autoBot || !state.glossary) return;
  try {
    const { channels } = await botApi(`/api/status?index=${encodeURIComponent(state.glossary.indexPath)}`);
    const changed = JSON.stringify(channels) !== JSON.stringify(state.channels);
    if (channels.length > state.channels.length) state.waiting = false;
    state.channels = channels; store.set("channels", channels);
    if (changed && !document.querySelector("dialog")) render();
  } catch (e) { console.warn("channel status", e); }
}

function notifyChanged() {
  if (state.autoBot && state.channels.length) botApi("/api/changed", { index_path: state.glossary.indexPath }).catch(() => {});
}

// ---------------------------------------------------------------- boot
async function boot() {
  mini.start();
  mini.routeLinks(document.body);
  applyLang();
  if (mini.inTelegram) {
    const cloudKey = await mini.cloudGet("tgg_key");
    if (cloudKey) { state.token = cloudKey; store.set("token", cloudKey); keySaved(); }
    else if (state.token) await rememberKey(state.token); // first open of the Mini App on a device that already had it
  }
  const m = location.hash.match(/key=([^&]+)/);
  if (m) {
    state.token = decodeURIComponent(m[1]);
    store.set("token", state.token);
    history.replaceState(null, "", location.pathname + location.search);
  }
  const config = loadConfig();
  if (!state.token) { await config; return renderWelcome(); }
  $app.replaceChildren(h("div", { class: "center" }, h("div", {}, h("span", { class: "spin" }), " ", t("loading"))));
  try {
    const [g] = await Promise.all([new Glossary(state.token).load(), config]);
    ready(g);
  } catch (e) {
    fail(e);
    if (/ACCESS_TOKEN_INVALID/.test(e.message)) { store.set("token", null); state.token = null; }
    renderWelcome();
  }
}

function ready(g) {
  state.glossary = g;
  render();
  refreshChannels();
}

const GUIDE_URL = {
  he: "https://github.com/NehoraiHadad/telegraph-glossary/blob/main/docs/GUIDE.he.md",
  en: "https://github.com/NehoraiHadad/telegraph-glossary/blob/main/docs/GUIDE.md",
};

// ---------------------------------------------------------------- welcome
function renderWelcome() {
  const [a, term1, b, term2, c] = t("heroDemo");
  const name = h("input", { type: "text", id: "gname", placeholder: t("namePh"), maxLength: 60 });
  const create = h("button", { class: "btn primary lg", type: "submit" }, t("create"));
  const form = h("form", { class: "create", onsubmit: (e) => {
    e.preventDefault();
    busy(create, async () => {
      const g = await Glossary.create({ title: name.value.trim() || (state.lang === "he" ? "המילון שלי" : "My glossary") });
      await rememberKey(g.token); go("terms", false); ready(g);
    });
  } }, h("label", { class: "lbl", for: "gname" }, t("nameLabel")), h("div", { class: "row" }, name, create));

  const keyIn = h("input", { type: "password", placeholder: t("keyPh"), autocomplete: "off", "aria-label": t("keyPh") });
  const openBtn = h("button", { class: "btn", type: "submit" }, t("open"));
  const keyRow = h("form", { class: "row", hidden: true, onsubmit: (e) => {
    e.preventDefault();
    busy(openBtn, async () => {
      const g = await new Glossary(keyIn.value.trim()).load();
      await rememberKey(g.token); keySaved(); ready(g);
    });
  } }, keyIn, openBtn);

  $app.replaceChildren(h("main", { class: "welcome" },
    h("h1", {}, t("heroTitle")),
    h("p", { class: "sub" }, t("heroSub")),
    h("p", { class: "demo", "aria-hidden": "true" }, a, h("span", { class: "mark" }, term1), b, h("span", { class: "mark second" }, term2), c),
    form,
    h("p", { class: "fine" }, t("free")),
    h("div", { class: "alt" }, h("button", { class: "textlink", onclick: () => { keyRow.hidden = !keyRow.hidden; keyIn.focus(); } }, t("haveKey")), keyRow),
    h("section", { class: "how", "aria-labelledby": "how-title" },
      h("h2", { id: "how-title" }, t("howTitle")),
      h("ol", {}, ...t("how").map((s) => h("li", {}, s))),
      h("p", { class: "fine" }, t("howNoChannel")),
      h("p", { class: "fine" }, h("a", { href: GUIDE_URL[state.lang] || GUIDE_URL.en, target: "_blank", rel: "noopener" }, t("howGuide")))),
  ));
  $app.prepend(h("div", { class: "welcome-top" }, langSwitch(renderWelcome)));
  name.focus();
}

// Language choice, always visible: עב | EN
function langSwitch(rerender) {
  return h("div", { class: "seg lang-switch", role: "group", "aria-label": "Language / שפה" },
    [["he", "עב", "עברית"], ["en", "EN", "English"]].map(([code, short, full]) =>
      h("button", { type: "button", lang: code, title: full, "aria-label": full, "aria-pressed": String(state.lang === code),
        onclick: () => { if (state.lang === code) return; state.lang = code; store.set("lang", code); applyLang(); rerender(); } }, short)));
}

// ---------------------------------------------------------------- shell
const TABS = ["terms", "post", "channel", "agents"];
const TAB_LABEL = { terms: "tabTerms", post: "tabPost", channel: "tabChannel", agents: "tabAgents" };

function go(tab, draw = true) { state.tab = tab; store.set("tab", tab); if (draw) render(); }

function render() {
  const g = state.glossary;
  const tabBtn = (id) => h("button", { role: "tab", "aria-selected": String(state.tab === id), onclick: () => go(id) },
    t(TAB_LABEL[id]),
    id === "terms" ? h("span", { class: "n" }, g.terms.length) : null,
    id === "channel" && state.channels.length ? h("span", { class: "n", style: "color:var(--ok)", "aria-label": "✓" }, "●") : null);
  const view = { terms: viewTerms, post: viewPost, channel: viewChannel, agents: viewAgents }[TABS.includes(state.tab) ? state.tab : "terms"];
  $app.replaceChildren(
    h("header", { class: "top" }, h("div", { class: "top-in" },
      h("div", { class: "brand", title: g.title }, g.title),
      h("nav", { class: "tabs", role: "tablist" }, TABS.map(tabBtn)),
      langSwitch(render),
      h("button", { class: "btn quiet", "aria-label": t("settings"), title: t("settings"), onclick: () => openSettings() }, "⚙︎"))),
    h("main", {}, setupCard(), view()),
  );
}

// ---------------------------------------------------------------- setup checklist (a real sequence)
function setupCard() {
  const g = state.glossary;
  const steps = [
    { label: t("step1"), done: g.terms.length > 0, act: () => openTerm(null, "") },
    state.autoBot
      ? { label: t("step2Auto"), done: state.channels.length > 0, act: () => go("channel") }
      : { label: t("step2Manual"), done: state.tried, act: () => go("post") },
    { label: t("step3"), done: state.keySaved, act: () => openSettings("key") },
  ];
  if (state.setupHidden || steps.every((s) => s.done)) return null;
  const next = steps.findIndex((s) => !s.done);
  return h("section", { class: "setup", "aria-label": t("setupTitle") },
    h("div", { class: "setup-head" }, h("strong", {}, t("setupTitle")),
      h("button", { class: "btn quiet sm", onclick: () => { state.setupHidden = true; store.set("setupHidden", true); render(); } }, t("hideSetup"))),
    h("ol", { class: "steps" }, steps.map((s, i) => h("li", { class: s.done ? "done" : i === next ? "next" : "" },
      h("button", { onclick: s.act, "aria-label": s.done ? `${s.label} ✓` : s.label }, s.label)))));
}

// ---------------------------------------------------------------- terms
function viewTerms() {
  const g = state.glossary;
  if (!g.terms.length) {
    return h("div", { class: "empty" },
      h("h2", {}, t("emptyTermsTitle")), h("p", {}, t("emptyTerms")),
      h("button", { class: "btn primary lg", onclick: () => openTerm(null, "") }, t("newTerm")));
  }
  const list = h("ul", { class: "terms" });
  const search = h("input", { type: "text", placeholder: t("search"), "aria-label": t("search"), value: state.query });
  const draw = () => {
    state.query = search.value;
    const q = state.query.trim().toLowerCase();
    const items = [...g.terms].sort((a, b) => a.term.localeCompare(b.term))
      .filter((x) => !q || x.term.toLowerCase().includes(q) || x.aliases.some((a) => a.toLowerCase().includes(q)));
    list.replaceChildren(...items.map((x) => h("li", {},
      h("div", { class: "grow" },
        h("span", { class: "word mark", dir: "auto" }, x.term),
        x.aliases.length ? h("div", { class: "forms" }, x.aliases.map((a, i) => [i ? ", " : "", h("bdi", {}, a)])) : null),
      h("div", { class: "acts" },
        h("a", { class: "btn quiet sm", href: x.url, target: "_blank", rel: "noopener", title: "telegra.ph", "aria-label": `${x.term}: telegra.ph` }, "↗"),
        h("button", { class: "btn sm", onclick: () => openTerm(x) }, t("edit"))))));
  };
  search.addEventListener("input", draw);
  draw();
  return h("div", {},
    h("div", { class: "toolbar" }, search, h("button", { class: "btn primary", onclick: () => openTerm(null, "") }, t("newTerm"))),
    list,
    h("p", { class: "foot" }, h("span", {}, t("termCount", g.terms.length)),
      h("a", { href: g.indexUrl, target: "_blank", rel: "noopener" }, t("publicPage"))));
}

// ---------------------------------------------------------------- post
function viewPost() {
  const g = state.glossary;
  const ta = h("textarea", { dir: "auto", placeholder: t("postPh"), "aria-label": t("postPh"), value: state.draft });
  const bubble = h("div", { class: "bubble", dir: "auto" });
  const meta = h("div", { class: "meta" });
  const addSel = h("div", { class: "addsel" });
  const actions = h("div", { class: "actions" });

  const update = () => {
    state.draft = ta.value; store.set("draft", state.draft);
    const { segments, found } = findTerms(state.draft, g.terms, { mode: state.mode, exclude: [...state.excluded] });
    if (!state.draft.trim()) {
      bubble.className = "bubble empty-b"; bubble.replaceChildren(t("postEmpty"));
    } else {
      bubble.className = "bubble";
      bubble.replaceChildren(...segments.map((s) => {
        if (s.term === undefined) return s.text;
        const off = state.excluded.has(s.term.toLowerCase());
        if (!s.linked && !off) return s.text; // a repeat in "first only" mode
        return h("a", { class: `mark${off ? " off" : ""}`, href: s.url, role: "button", title: s.term,
          onclick: (e) => { e.preventDefault(); const k = s.term.toLowerCase(); off ? state.excluded.delete(k) : state.excluded.add(k); update(); } }, s.text);
      }));
    }
    const len = state.draft.length;
    meta.replaceChildren(
      h("span", {}, state.draft.trim() ? t("found", found.length) : ""),
      h("span", { class: len > 4096 ? "bad" : "" }, len > 4096 ? t("tooLong", len) : len ? `${len}/4096` : ""));
    addSel.replaceChildren(state.selection && !g.find(state.selection)
      ? h("button", { class: "btn sm", onmousedown: (e) => e.preventDefault(), onclick: () => openTerm(null, state.selection) }, "+ ", t("addSel", state.selection)) : "");
    drawActions(actions, segments, found, len);
  };
  const onSel = () => {
    const s = ta.value.slice(ta.selectionStart, ta.selectionEnd).trim();
    const next = s && s.length <= 60 && !s.includes("\n") ? s : "";
    if (next !== state.selection) { state.selection = next; update(); }
  };
  ta.addEventListener("input", update);
  for (const ev of ["select", "keyup", "mouseup"]) ta.addEventListener(ev, onSel);
  update();

  return h("div", {},
    state.channels.length ? h("p", { class: "notice" }, t("autoOnHint", state.channels.map((c) => `„${c.title}”`).join(", "))) : null,
    h("div", { class: "post" }, h("div", {}, ta, addSel), h("div", {}, bubble, meta, actions)));
}

function markTried() { if (!state.tried) { state.tried = true; store.set("tried", true); } }

function drawActions(bar, segments, found, len) {
  const empty = !toPlain(segments).trim();
  const hasSend = state.bot && state.chats.length;
  const copyBtn = h("button", { class: hasSend ? "btn" : "btn primary", disabled: empty, onclick: async () => {
    const html = toTelegramHtml(segments).replace(/\n/g, "<br>");
    try {
      await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([toPlain(segments)], { type: "text/plain" }) })]);
      toast(t("copied"));
    } catch { await copyText(toPlain(segments)); }
    if (found.length) markTried();
  } }, t("copy"));
  let send = null;
  if (hasSend) {
    const cur = state.chats.find((c) => c.id === state.chatId) || state.chats[0];
    send = h("button", { class: "btn primary", disabled: empty || len > 4096, onclick: (e) => busy(e.currentTarget, async () => {
      await tg.sendHtml(state.bot.token, cur.id, toTelegramHtml(segments));
      toast(t("sent")); markTried();
    }) }, t("send", cur.name));
  }
  bar.replaceChildren(...[send, copyBtn, h("div", { class: "end" },
    h("button", { class: "btn quiet sm", disabled: empty, onclick: () => copyText(toMarkdown(segments)) }, t("copyMd")),
    h("button", { class: "btn quiet sm", disabled: empty, onclick: () => { state.draft = ""; store.set("draft", ""); state.excluded.clear(); render(); } }, t("clear")))].filter(Boolean));
}

// ---------------------------------------------------------------- channel
function viewChannel() {
  const g = state.glossary;
  const demo = t("heroDemo");
  const before = demo.join("");
  const after = demo.map((x, i) => (i % 2 ? h("a", { class: "mark" }, x) : x));

  const parts = [
    h("h2", { class: "page-title" }, t("chTitle")),
    h("div", { class: "ba", "aria-hidden": "true" },
      h("div", { class: "card", dir: "auto" }, h("div", { class: "cap" }, t("chBefore")), before),
      h("div", { class: "arrow" }, "→"),
      h("div", { class: "card", dir: "auto" }, h("div", { class: "cap" }, t("chAfter")), after)),
  ];

  if (state.autoBot) {
    const connect = h("button", { class: state.channels.length ? "btn" : "btn primary lg", onclick: (e) => {
      if (mini.inTelegram) {
        return busy(e.currentTarget, async () => {
          const { add_to_channel_url } = await botApi("/api/link-user", { init_data: mini.initData, index_path: g.indexPath });
          state.waiting = true; render();
          mini.openTelegram(add_to_channel_url);
        });
      }
      const win = window.open("about:blank", "_blank"); // open synchronously so popup blockers allow it
      busy(e.currentTarget, async () => {
        try {
          const { start_url } = await botApi("/api/connect", { index_path: g.indexPath, lang: state.lang });
          if (win) win.location.href = start_url; else location.href = start_url;
          state.waiting = true; render();
        } catch (err) { win?.close(); throw err; }
      });
    } }, state.channels.length ? t("chAnother") : t("chConnect"));
    parts.push(
      state.channels.length ? h("ul", { class: "chans" }, state.channels.map((c) => h("li", {}, c.title, h("span", { class: "ok" }, "✓ ", t("chConnected"))))) : null,
      h("div", { class: "row" }, connect,
        state.waiting ? h("span", { class: "muted small" }, h("span", { class: "spin" }), " ", t("chWaiting")) : h("span", { class: "muted small" }, mini.inTelegram ? t("chHowMini") : t("chHow")),
        state.waiting || state.channels.length ? h("button", { class: "btn quiet sm", onclick: (e) => busy(e.currentTarget, refreshChannels) }, t("chCheck")) : null),
      state.channels.length ? h("p", { class: "muted small", style: "margin-top:14px" }, t("chOld", state.autoBot.username)) : null,
    );
  } else {
    parts.push(h("p", { class: "muted" }, t("chUnavailable")));
  }
  parts.push(h("details", { class: "more", open: !state.autoBot && !!state.bot }, h("summary", {}, t("chOwnBot")), ownBot()));
  return h("div", {}, parts);
}

function ownBot() {
  const box = h("div", { class: "ownbot" });
  const draw = () => {
    const tokenIn = h("input", { type: "password", id: "bot-token", placeholder: "123456:ABC-…", value: state.bot?.token || "", autocomplete: "off", dir: "ltr" });
    const found = h("ul", { class: "chans" });
    const addChat = (c) => {
      if (!state.chats.some((x) => x.id === c.id)) state.chats.push(c);
      state.chatId = c.id; store.set("chats", state.chats); store.set("chatId", c.id); draw();
    };
    box.replaceChildren(...[
      h("div", {}, h("label", { class: "lbl", for: "bot-token" }, t("botTokenLabel")),
        h("div", { class: "row" }, tokenIn, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, async () => {
          const me = await tg.getMe(tokenIn.value.trim());
          state.bot = { token: tokenIn.value.trim(), username: me.username }; store.set("bot", state.bot); draw();
        }) }, t("check"))),
        state.bot ? h("p", { class: "hint ok" }, t("botOk", state.bot.username)) : null),
      state.bot ? h("div", {}, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, async () => {
        const chats = await tg.discoverChats(state.bot.token);
        found.replaceChildren(...(chats.length ? chats.map((c) => h("li", {}, c.name, h("button", { class: "btn sm", style: "margin-inline-start:auto", onclick: () => addChat(c) }, t("use"))))
          : [h("li", { class: "muted small" }, t("noChats"))]));
      }) }, t("findChats"))) : null,
      found,
      state.chats.length ? h("ul", { class: "chans" }, state.chats.map((c) => h("li", {}, c.name,
        h("button", { class: "btn quiet sm", style: "margin-inline-start:auto", onclick: () => { state.chats = state.chats.filter((x) => x.id !== c.id); store.set("chats", state.chats); draw(); } }, t("remove"))))) : null,
    ].filter(Boolean));
  };
  draw();
  return box;
}

// ---------------------------------------------------------------- AI agents
// Syntax checked against each tool's docs (Claude Code, Codex, Gemini CLI, Antigravity).
const UVX_ARGS = ["--from", REPO, "telegraph-glossary", "mcp"];
const AGENTS = {
  claude: { name: "Claude Code", kind: "cmd", make: (k) => `claude mcp add telegraph-glossary --scope user -e TELEGRAPH_ACCESS_TOKEN=${k} -- uvx ${UVX_ARGS.join(" ")}` },
  codex: { name: "Codex", kind: "cmd", make: (k) => `codex mcp add telegraph-glossary --env TELEGRAPH_ACCESS_TOKEN=${k} -- uvx ${UVX_ARGS.join(" ")}` },
  gemini: { name: "Gemini CLI", kind: "cmd", make: (k) => `gemini mcp add -s user -e TELEGRAPH_ACCESS_TOKEN=${k} telegraph-glossary uvx -- ${UVX_ARGS.join(" ")}` },
  json: { name: "Antigravity, Cursor, Claude Desktop", kind: "json",
    make: (k) => JSON.stringify({ mcpServers: { "telegraph-glossary": { command: "uvx", args: UVX_ARGS, env: { TELEGRAPH_ACCESS_TOKEN: k } } } }, null, 2) },
};

function viewAgents() {
  const a = AGENTS[state.agent] || AGENTS.claude;
  const masked = state.token.slice(0, 4) + "••••••••";
  return h("div", { class: "ag" },
    h("h2", { class: "page-title", style: "margin:0" }, t("agTitle")),
    h("div", { class: "seg", role: "group" }, Object.entries(AGENTS).map(([id, x]) =>
      h("button", { type: "button", "aria-pressed": String(id === state.agent), onclick: () => { state.agent = id; store.set("agent", id); render(); } }, x.name))),
    h("section", {},
      h("h3", {}, a.kind === "cmd" ? t("agRun") : t("agPaste")),
      h("pre", { class: "cmd" }, a.make(masked)),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { class: "btn primary", onclick: () => copyText(a.make(state.token)) }, t("copy")),
        h("span", { class: "warn" }, t("agKeyNote")),
        h("a", { class: "small", href: "https://docs.astral.sh/uv/getting-started/installation/", target: "_blank", rel: "noopener", style: "margin-inline-start:auto" }, t("agNeedsUv")))),
    h("section", {},
      h("h3", {}, t("agTry")),
      h("ul", { class: "prompts" }, t("agPrompts").map((p) => h("li", { dir: "auto" }, p)))),
  );
}

// ---------------------------------------------------------------- dialogs
function dialog(title, body, foot) {
  const d = h("dialog", { "aria-label": title },
    h("div", { class: "dh" }, h("h2", {}, title), h("button", { class: "btn quiet sm", "aria-label": t("close"), onclick: () => d.close() }, "✕")),
    h("div", { class: "db" }, body),
    foot ? h("div", { class: "df" }, foot) : null);
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

async function openTerm(entry, prefill = "") {
  const g = state.glossary;
  const term = h("input", { type: "text", id: "f-term", value: entry ? entry.term : prefill, dir: "auto", maxLength: 100 });
  const aliases = h("input", { type: "text", id: "f-aka", value: entry ? entry.aliases.join(", ") : "", dir: "auto" });
  const def = h("textarea", { id: "f-def", rows: 7, dir: "auto", placeholder: t("definitionPh") });
  const prev = h("div", { class: "defprev", dir: "auto", hidden: true });
  const wrap = (before, after = before) => () => {
    const s = def.selectionStart, e = def.selectionEnd;
    def.setRangeText(before + def.value.slice(s, e) + after, s, e, "select"); def.focus();
  };
  const tools = h("div", { class: "row", style: "gap:4px" },
    h("button", { type: "button", class: "btn sm", "aria-label": "Bold", onclick: wrap("**") }, h("b", {}, "B")),
    h("button", { type: "button", class: "btn sm", "aria-label": "Italic", onclick: wrap("*") }, h("i", {}, "I")),
    h("button", { type: "button", class: "btn sm", "aria-label": "Link", onclick: wrap("[", "](https://)") }, "🔗"));
  const bW = h("button", { type: "button", "aria-pressed": "true" }, t("writeTab"));
  const bP = h("button", { type: "button", "aria-pressed": "false" }, t("previewTab"));
  const mode = (p) => {
    def.hidden = p; tools.hidden = p; prev.hidden = !p;
    bW.setAttribute("aria-pressed", String(!p)); bP.setAttribute("aria-pressed", String(p));
    if (p) prev.innerHTML = nodesToHtml(markdownToNodes(def.value));
  };
  bW.onclick = () => mode(false); bP.onclick = () => mode(true);

  const save = h("button", { class: "btn primary", onclick: (e) => busy(e.currentTarget, async () => {
    await g.saveTerm({ term: term.value, aliases: aliases.value.split(","), definition: def.value }, entry ? entry.term : null);
    notifyChanged(); toast(t("saved")); state.selection = ""; d.close();
  }) }, t("save"));
  const del = entry ? h("button", { class: "btn danger end", onclick: async (e) => {
    const btn = e.currentTarget;
    if (!(await mini.confirmDialog(t("confirmDelete", entry.term)))) return;
    busy(btn, async () => { await g.removeTerm(entry.term); notifyChanged(); toast(t("deleted")); d.close(); });
  } }, t("delete")) : null;

  const d = dialog(entry ? entry.term : t("newTerm"), [
    h("div", {}, h("label", { class: "lbl", for: "f-term" }, t("term")), term),
    h("div", {}, h("label", { class: "lbl", for: "f-def" }, t("definition")),
      h("div", { class: "mdbar" }, tools, h("div", { class: "seg" }, bW, bP)), def, prev),
    h("div", {}, h("label", { class: "lbl", for: "f-aka" }, t("aliases")), aliases, h("p", { class: "hint" }, t("aliasesHint"))),
  ], [save, h("button", { class: "btn quiet", onclick: () => d.close() }, t("cancel")), del]);
  d.addEventListener("close", () => render());

  (entry || !prefill ? term : def).focus();
  if (entry) {
    def.disabled = true; def.value = t("loading");
    try { def.value = (await g.getDefinition(entry.path)).markdown; } catch (e) { fail(e); def.value = ""; }
    def.disabled = false;
  }
}

function keySaved() { state.keySaved = true; store.set("keySaved", true); }

function openSettings(focus) {
  const g = state.glossary;
  const sec = (id, title, ...kids) => h("section", { class: "set", id: `set-${id}` }, h("h3", {}, title), ...kids);
  const nameIn = h("input", { type: "text", value: g.title, maxLength: 60, "aria-label": t("sName") });
  const keyOut = h("input", { type: "password", value: state.token, readOnly: true, dir: "ltr", "aria-label": t("sKey") });
  const radio = (val, label) => h("label", { class: "choice" },
    h("input", { type: "radio", name: "mode", checked: state.mode === val, onchange: () => { state.mode = val; store.set("mode", val); } }), label);

  const d = dialog(t("settings"), [
    sec("key", t("sKey"),
      h("p", { class: "muted small" }, t("keyWhy")),
      h("div", { class: "row" }, keyOut,
        h("button", { class: "btn sm", onclick: (e) => { const show = keyOut.type === "password"; keyOut.type = show ? "text" : "password"; e.currentTarget.textContent = show ? t("hide") : t("show"); } }, t("show"))),
      mini.hasCloud() ? h("p", { class: "ok small" }, "✓ ", t("keyInCloud")) : null,
      h("div", { class: "row" },
        h("button", { class: mini.inTelegram ? "btn sm" : "btn sm primary", onclick: () => {
          mini.shareToTelegram(`${APP_URL}#key=${encodeURIComponent(state.token)}`, t("shareText", g.title)); keySaved();
        } }, t("saveToTelegram")),
        mini.inTelegram ? null : h("button", { class: "btn sm", onclick: () => { downloadKey(); keySaved(); } }, t("download")),
        h("button", { class: "btn sm", onclick: async () => { if (await copyText(state.token)) keySaved(); } }, t("copy")),
        h("button", { class: "btn sm", onclick: async () => { if (await copyText(`${APP_URL}#key=${encodeURIComponent(state.token)}`, t("linkCopied"))) keySaved(); } }, t("deviceLink")))),
    sec("name", t("sName"),
      h("div", { class: "row" }, nameIn, h("button", { class: "btn sm", onclick: (e) => busy(e.currentTarget, async () => { await g.rename(nameIn.value.trim() || g.title); toast(t("saved")); }) }, t("rename"))),
      h("div", { class: "row" },
        h("a", { class: "small", href: g.indexUrl, target: "_blank", rel: "noopener" }, t("publicPage")),
        h("button", { class: "textlink small", onclick: (e) => busy(e.currentTarget, async () => window.open(await g.authUrl(), "_blank", "noopener")) }, t("editOnTelegraph")))),
    sec("links", t("sLinks"), radio("first", t("linkFirst")), radio("all", t("linkAll"))),
    h("section", { class: "set" }, h("div", {}, h("button", { class: "btn danger sm", onclick: async () => {
      if (!(await mini.confirmDialog(t("confirmSignOut")))) return;
      await mini.cloudRemove("tgg_key");
      for (const k of ["token", "draft", "bot", "chats", "chatId", "channels", "keySaved", "tried", "setupHidden", "tab"]) store.set(k, null);
      location.reload();
    } }, t("signOut")))),
  ]);
  d.addEventListener("close", () => render());
  if (focus) d.querySelector(`#set-${focus}`)?.scrollIntoView({ block: "start" });
}

function downloadKey() {
  const text = [
    `Telegraph Glossary: ${state.glossary.title}`,
    "",
    `Key: ${state.token}`,
    `Open: ${APP_URL}#key=${encodeURIComponent(state.token)}`,
    `Public page: ${state.glossary.indexUrl}`,
    "",
    "Keep this private. Anyone with the key can edit the glossary.",
  ].join("\n");
  const a = h("a", { href: URL.createObjectURL(new Blob([text], { type: "text/plain" })), download: "telegraph-glossary-key.txt" });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// coming back from Telegram after "Connect a channel"
mini.onReturn(refreshChannels);

boot();
