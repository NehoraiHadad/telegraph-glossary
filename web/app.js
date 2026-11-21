import { STRINGS } from "./i18n.js";
import { Glossary, APP_URL } from "./core/glossary.js";
import { findTerms, toTelegramHtml, toMarkdown, toPlain, escapeHtml } from "./core/linker.js";
import { markdownToNodes, nodesToHtml } from "./core/markdown.js";
import * as tg from "./core/telegram.js";
import { BOT } from "./config.js";

const REPO = "git+https://github.com/NehoraiHadad/telegraph-glossary";

// ---------------------------------------------------------------- storage
const store = {
  get(k, d = null) { try { const v = localStorage.getItem("tgg." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { v === null ? localStorage.removeItem("tgg." + k) : localStorage.setItem("tgg." + k, JSON.stringify(v)); } catch {} },
};

const state = {
  lang: store.get("lang") || ((navigator.language || "").startsWith("he") ? "he" : "en"),
  token: store.get("token"),
  glossary: null,
  view: "write",
  draft: store.get("draft", ""),
  excluded: new Set(),
  mode: store.get("mode", "first"),
  bot: store.get("bot", null), // { token, username }
  chats: store.get("chats", []), // [{id, name}]
  autoChannels: store.get("autoChannels", []), // channels the auto-link bot serves
  chatId: store.get("chatId", null),
  selection: "",
  query: "",
};

const t = (k, ...a) => { const v = STRINGS[state.lang][k] ?? STRINGS.en[k]; return typeof v === "function" ? v(...a) : v; };

// ---------------------------------------------------------------- tiny DOM helper
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
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}
const $app = document.getElementById("app");

function toast(msg, kind = "") {
  const el = h("div", { class: `toast ${kind}` }, msg);
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 6000 : 2600);
}
const fail = (e) => { console.error(e); toast(`${t("error")}: ${e.message || e}`, "error"); };

async function busy(btn, fn) {
  const label = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin" style="width:16px;height:16px;border-width:2px"></span>';
  try { return await fn(); } catch (e) { fail(e); } finally { btn.disabled = false; btn.innerHTML = label; }
}

function ready(g) {
  state.glossary = g;
  render();
  refreshAuto();
}

// ---------------------------------------------------------------- auto-link bot
async function botApi(path, body) {
  const res = await fetch(BOT.api.replace(/\/$/, "") + path, body
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }
    : {});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function refreshAuto() {
  if (!BOT.api || !state.glossary) return;
  try {
    const { channels } = await botApi(`/api/status?index=${encodeURIComponent(state.glossary.indexPath)}`);
    const changed = JSON.stringify(channels) !== JSON.stringify(state.autoChannels);
    state.autoChannels = channels; store.set("autoChannels", channels);
    if (changed && state.view === "write" && !document.querySelector("dialog")) render();
  } catch (e) { console.warn("auto-link status", e); }
}

/** Tell the bot the glossary changed so it updates earlier posts right away. */
function notifyChanged() {
  if (BOT.api && state.autoChannels.length) botApi("/api/changed", { index_path: state.glossary.indexPath }).catch(() => {});
}

function applyLang() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = state.lang === "he" ? "rtl" : "ltr";
}

// ---------------------------------------------------------------- boot
async function boot() {
  applyLang();
  // A key can be handed over in the URL hash (from the CLI or "open on another device").
  const m = location.hash.match(/key=([^&]+)/);
  if (m) {
    state.token = decodeURIComponent(m[1]);
    store.set("token", state.token);
    history.replaceState(null, "", location.pathname + location.search);
  }
  if (!state.token) return renderWelcome();
  $app.replaceChildren(h("div", { class: "center" }, h("div", {}, h("span", { class: "spin" }), " ", t("loading"))));
  try {
    ready(await new Glossary(state.token).load());
  } catch (e) {
    fail(e);
    if (/ACCESS_TOKEN_INVALID/.test(e.message)) { store.set("token", null); state.token = null; }
    renderWelcome();
  }
}

// ---------------------------------------------------------------- welcome
function renderWelcome() {
  const name = h("input", { type: "text", id: "gname", placeholder: t("glossaryNamePh"), maxLength: 60 });
  const author = h("input", { type: "text", id: "gauthor", maxLength: 128 });
  const keyInput = h("input", { type: "password", placeholder: t("keyPh"), autocomplete: "off" });
  const keyRow = h("div", { class: "row", hidden: true }, keyInput,
    h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, () => connectKey(keyInput.value.trim())) }, t("connect")));

  const createBtn = h("button", { class: "btn primary big", onclick: (e) => busy(e.currentTarget, async () => {
    const g = await Glossary.create({ title: name.value.trim() || t("glossaryNamePh"), authorName: author.value.trim() });
    state.token = g.token; store.set("token", g.token); ready(g);
  }) }, t("create"));

  $app.replaceChildren(h("div", { class: "welcome" },
    h("div", { class: "brand-mark", "aria-hidden": "true" }, "A"),
    h("h1", {}, t("appName")),
    h("p", { class: "tagline" }, t("tagline")),
    h("div", { class: "demo-bubble", html: t("demo").replace(/<a>/g, '<a href="#" tabindex="-1" onclick="return false">') }),
    h("ul", { class: "points" }, t("welcomePoints").filter((_, i) => BOT.api || i !== 1).map((p) => h("li", {}, p))),
    h("div", { class: "card" },
      h("div", { class: "field" }, h("label", { for: "gname" }, t("glossaryName")), name),
      h("div", { class: "field" }, h("label", { for: "gauthor" }, t("authorName")), author),
      h("div", { class: "actions" }, createBtn,
        h("button", { class: "linkish", onclick: () => { keyRow.hidden = !keyRow.hidden; keyInput.focus(); } }, t("haveKey"))),
      h("div", { style: "margin-top:12px" }, keyRow)),
    langSwitch(renderWelcome),
  ));
}

async function connectKey(key) {
  if (!key) return;
  const g = await new Glossary(key).load();
  state.token = key; store.set("token", key); ready(g);
}

function langSwitch(rerender) {
  return h("p", { class: "muted small", style: "margin-top:24px;text-align:center" },
    h("button", { class: "linkish", onclick: () => { state.lang = state.lang === "he" ? "en" : "he"; store.set("lang", state.lang); applyLang(); rerender(); } },
      state.lang === "he" ? "English" : "עברית"));
}

// ---------------------------------------------------------------- shell
function render() {
  const g = state.glossary;
  const tab = (id, label, extra) => h("button", { role: "tab", "aria-selected": String(state.view === id), onclick: () => { state.view = id; render(); } }, label, extra);
  $app.replaceChildren(
    h("header", { class: "topbar" }, h("div", { class: "topbar-inner" },
      h("div", { class: "title" }, h("div", { class: "brand-mark", "aria-hidden": "true" }, "A"), h("span", {}, g.title)),
      h("nav", { class: "tabs", role: "tablist" },
        tab("write", t("tabWrite")),
        tab("terms", t("tabTerms"), h("span", { class: "count" }, g.terms.length))),
      h("button", { class: "btn ghost", title: t("settings"), "aria-label": t("settings"), onclick: openSettings }, "⚙︎"))),
    h("main", {}, state.view === "write" ? renderWrite() : renderTerms()),
  );
}

// ---------------------------------------------------------------- write view
function linkOptions() { return { mode: state.mode, exclude: [...state.excluded] }; }

function renderWrite() {
  const g = state.glossary;
  const ta = h("textarea", { dir: "auto", placeholder: t("writePh"), value: state.draft, "aria-label": t("writePh") });
  const chips = h("div", { class: "chips" });
  const bubble = h("div", { class: "bubble", dir: "auto" });
  const meta = h("div", { class: "bubble-meta" });
  const sendBar = h("div", { class: "send-bar" });

  const update = () => {
    state.draft = ta.value;
    store.set("draft", state.draft);
    const { segments, found } = findTerms(state.draft, g.terms, linkOptions());
    const inText = new Set(segments.filter((s) => s.term).map((s) => s.term));

    // chips: found terms (+ excluded ones still present) and "add selection"
    chips.replaceChildren(...[
      ...[...inText].map((term) => h("button", {
        class: `chip ${state.excluded.has(term.toLowerCase()) ? "off" : ""}`, title: t("detectedHint"),
        onclick: () => { const k = term.toLowerCase(); state.excluded.has(k) ? state.excluded.delete(k) : state.excluded.add(k); update(); },
      }, term)),
      state.selection && !g.find(state.selection)
        ? h("button", { class: "chip add", onmousedown: (e) => e.preventDefault(), onclick: () => openTermDialog(null, state.selection) }, t("addSelection", state.selection))
        : null,
      h("button", { class: "chip add", onclick: () => openTermDialog(null, "") }, t("newTerm")),
    ].filter(Boolean));
    noneMsg.hidden = inText.size > 0 || !state.draft.trim();

    if (!state.draft.trim()) {
      bubble.className = "bubble empty"; bubble.textContent = t("previewEmpty");
    } else {
      bubble.className = "bubble";
      bubble.innerHTML = segments.map((s) => s.term === undefined ? escapeHtml(s.text)
        : s.linked ? `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" title="${escapeHtml(s.term)}">${escapeHtml(s.text)}</a>`
          : `<span class="off">${escapeHtml(s.text)}</span>`).join("");
    }
    const len = state.draft.length;
    meta.className = `bubble-meta ${len > 4096 ? "bad" : ""}`;
    meta.textContent = len > 4096 ? t("tooLong", len) : len ? `${len}/4096` : "";
    renderSendBar(sendBar, segments, len);
  };

  const noneMsg = h("p", { class: "muted small", hidden: true }, t("noneDetected"));
  ta.addEventListener("input", update);
  const onSel = () => {
    const s = ta.value.slice(ta.selectionStart, ta.selectionEnd).trim();
    const next = s && s.length <= 60 && !/\n/.test(s) ? s : "";
    if (next !== state.selection) { state.selection = next; update(); }
  };
  ta.addEventListener("select", onSel);
  ta.addEventListener("keyup", onSel);
  ta.addEventListener("mouseup", onSel);

  const banner = state.autoChannels.length
    ? h("p", { class: "banner" }, "✨ ", t("autoBanner", state.autoChannels.map((c) => c.title).join(", ")))
    : null;
  const view = h("div", { class: "write" + (banner ? " has-banner" : "") }, banner,
    h("div", { class: "editor" },
      h("p", { class: "pane-label" }, t("tabWrite")),
      ta,
      h("div", { class: "chips-wrap" }, h("p", { class: "pane-label" }, t("detected")), chips, noneMsg)),
    h("div", { class: "preview-pane" },
      h("p", { class: "pane-label" }, t("preview")),
      bubble, meta, sendBar,
      g.terms.length < 3 ? h("div", { class: "how" }, h("strong", {}, t("help")), h("ol", {}, t("helpSteps").map((s) => h("li", {}, s)))) : null),
  );
  update();
  queueMicrotask(() => { if (!state.draft) ta.focus(); });
  return view;
}

function renderSendBar(bar, segments, len) {
  const html = toTelegramHtml(segments);
  const empty = !toPlain(segments).trim();
  const copyBtn = h("button", { class: "btn", disabled: empty, onclick: () => copyRich(segments) }, t("copy"));
  const mdBtn = h("button", { class: "btn ghost small", disabled: empty, onclick: () => copyText(toMarkdown(segments)) }, t("copyMd"));
  const clearBtn = h("button", { class: "btn ghost small", disabled: empty, onclick: () => { state.draft = ""; store.set("draft", ""); state.excluded.clear(); render(); } }, t("clear"));

  let send;
  if (state.bot && state.chats.length) {
    const current = state.chats.find((c) => c.id === state.chatId) || state.chats[0];
    const picker = state.chats.length > 1
      ? h("select", { "aria-label": "chat", onchange: (e) => { state.chatId = e.target.value; store.set("chatId", state.chatId); } },
        state.chats.map((c) => h("option", { value: c.id, selected: c.id === current.id }, c.name)))
      : null;
    send = [h("button", { class: "btn primary", disabled: empty || len > 4096, onclick: (e) => busy(e.currentTarget, async () => {
      const id = picker ? picker.value : current.id;
      await tg.sendHtml(state.bot.token, id, html);
      toast(t("sent"));
    }) }, picker ? t("sendShort") : t("send", current.name)), picker];
  } else {
    send = state.autoChannels.length ? [] : [h("button", { class: "btn", onclick: () => openSettings(BOT.api ? "auto" : "telegram") }, t("connectTelegram"))];
  }
  bar.replaceChildren(...send.filter(Boolean), copyBtn, h("span", { class: "spacer" }), mdBtn, clearBtn);
}

async function copyRich(segments) {
  const html = toTelegramHtml(segments).replace(/\n/g, "<br>");
  const plain = toPlain(segments);
  try {
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([html], { type: "text/html" }),
      "text/plain": new Blob([plain], { type: "text/plain" }),
    })]);
    toast(t("copied"));
  } catch { copyText(plain); }
}
async function copyText(s, msg = t("copied")) {
  try { await navigator.clipboard.writeText(s); toast(msg); } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- terms view
function renderTerms() {
  const g = state.glossary;
  const list = h("ul", { class: "term-list" });
  const search = h("input", { type: "text", placeholder: t("search"), value: state.query, "aria-label": t("search") });
  const draw = () => {
    state.query = search.value;
    const q = state.query.trim().toLowerCase();
    const items = [...g.terms].sort((a, b) => a.term.localeCompare(b.term))
      .filter((x) => !q || x.term.toLowerCase().includes(q) || x.aliases.some((a) => a.toLowerCase().includes(q)));
    list.hidden = !items.length;
    list.replaceChildren(...items.map((x) => h("li", {},
      h("div", { class: "grow" }, h("div", { class: "name", dir: "auto" }, x.term), x.aliases.length ? h("div", { class: "aka", dir: "auto" }, x.aliases.join(", ")) : null),
      h("a", { class: "btn ghost small", href: x.url, target: "_blank", rel: "noopener" }, t("open"), " ↗"),
      h("button", { class: "btn small", onclick: () => openTermDialog(x) }, t("edit")))));
  };
  search.addEventListener("input", draw);
  draw();

  if (!g.terms.length) {
    return h("div", { class: "empty-state" },
      h("h2", { style: "font-family:var(--display)" }, t("emptyTerms")),
      h("p", {}, t("emptyTermsHint")),
      h("button", { class: "btn primary big", onclick: () => openTermDialog(null, "") }, "+ ", t("newTerm")));
  }
  return h("div", {},
    h("div", { class: "terms-head" }, search, h("button", { class: "btn primary", onclick: () => openTermDialog(null, "") }, "+ ", t("newTerm"))),
    list,
    h("p", { class: "terms-foot muted" }, t("terms", g.terms.length), " · ", h("a", { href: g.indexUrl, target: "_blank", rel: "noopener" }, t("viewIndex"), " ↗")));
}

// ---------------------------------------------------------------- dialogs
function dialog(title, body, foot) {
  const d = h("dialog", { "aria-label": title },
    h("div", { class: "dlg-head" }, h("h2", {}, title), h("span", { class: "spacer" }),
      h("button", { class: "btn ghost", "aria-label": t("close"), onclick: () => d.close() }, "✕")),
    h("div", { class: "dlg-body" }, [].concat(body).filter(Boolean)),
    foot ? h("div", { class: "dlg-foot" }, foot) : null);
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

async function openTermDialog(entry, prefill = "") {
  const g = state.glossary;
  const term = h("input", { type: "text", id: "f-term", value: entry ? entry.term : prefill, dir: "auto", maxLength: 100 });
  const aliases = h("input", { type: "text", id: "f-aka", value: entry ? entry.aliases.join(", ") : "", dir: "auto" });
  const def = h("textarea", { id: "f-def", rows: 8, dir: "auto", placeholder: t("definitionPh") });
  const preview = h("div", { class: "def-preview", dir: "auto", hidden: true });
  const modeBtns = { write: null, preview: null };
  const setMode = (m) => {
    def.hidden = m !== "write"; preview.hidden = m !== "preview"; tools.hidden = m !== "write";
    modeBtns.write.setAttribute("aria-pressed", String(m === "write")); modeBtns.preview.setAttribute("aria-pressed", String(m === "preview"));
    if (m === "preview") preview.innerHTML = nodesToHtml(markdownToNodes(def.value));
  };
  modeBtns.write = h("button", { type: "button", "aria-pressed": "true", onclick: () => setMode("write") }, t("write"));
  modeBtns.preview = h("button", { type: "button", "aria-pressed": "false", onclick: () => setMode("preview") }, t("preview"));
  const wrap = (before, after = before, ph = "") => () => {
    const s = def.selectionStart, e = def.selectionEnd, sel = def.value.slice(s, e) || ph;
    def.setRangeText(before + sel + after, s, e, "select"); def.focus();
  };
  const tools = h("div", { class: "md-tools" },
    h("button", { type: "button", class: "btn small", title: "Bold", onclick: wrap("**") }, h("b", {}, "B")),
    h("button", { type: "button", class: "btn small", title: "Italic", onclick: wrap("*") }, h("i", {}, "I")),
    h("button", { type: "button", class: "btn small", title: "Link", onclick: wrap("[", "](https://)") }, "🔗"),
    h("button", { type: "button", class: "btn small", title: "List", onclick: () => { def.setRangeText("\n- ", def.selectionStart, def.selectionEnd, "end"); def.focus(); } }, "•"));

  const saveBtn = h("button", { class: "btn primary", onclick: (e) => busy(e.currentTarget, async () => {
    await g.saveTerm({ term: term.value, aliases: aliases.value.split(","), definition: def.value }, entry ? entry.term : null);
    notifyChanged();
    toast(t("saved"));
    state.selection = "";
    d.close(); render();
  }) }, t("save"));
  const delBtn = entry ? h("button", { class: "btn danger", onclick: (e) => {
    if (!confirm(t("confirmDelete", entry.term))) return;
    busy(e.currentTarget, async () => { await g.removeTerm(entry.term); notifyChanged(); toast(t("deleted")); d.close(); render(); });
  } }, t("delete")) : null;

  const d = dialog(entry ? entry.term : t("newTerm"), [
    h("div", { class: "field" }, h("label", { for: "f-term" }, t("term")), term),
    h("div", { class: "field" }, h("label", { for: "f-aka" }, t("aliases")), aliases, h("span", { class: "hint" }, t("aliasesHint"))),
    h("div", { class: "field" },
      h("div", { class: "row" }, h("label", { for: "f-def" }, t("definition")), h("span", { class: "spacer" }), h("div", { class: "seg" }, modeBtns.write, modeBtns.preview)),
      tools, def, preview),
  ], [saveBtn, h("button", { class: "btn ghost", onclick: () => d.close() }, t("cancel")), h("span", { class: "spacer" }), delBtn]);

  (entry || !prefill ? term : def).focus();
  if (entry) {
    def.disabled = true; def.value = t("loading");
    try { def.value = (await g.getDefinition(entry.path)).markdown; } catch (e) { fail(e); def.value = ""; }
    def.disabled = false;
  }
}

function openSettings(focus) {
  const g = state.glossary;
  const sec = (id, title, ...kids) => h("section", { class: "set", id: `set-${id}` }, h("h3", {}, title), ...kids);

  // glossary
  const nameIn = h("input", { type: "text", value: g.title, maxLength: 60 });
  const glossarySec = sec("glossary", t("sGlossary"),
    h("div", { class: "row" }, nameIn, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, async () => { await g.rename(nameIn.value.trim() || g.title); toast(t("saved")); render(); }) }, t("rename"))),
    h("div", { class: "row" },
      h("a", { class: "btn small", href: g.indexUrl, target: "_blank", rel: "noopener" }, t("viewIndex"), " ↗"),
      h("button", { class: "btn small", onclick: (e) => busy(e.currentTarget, async () => { window.open(await g.authUrl(), "_blank", "noopener"); }) }, t("editOnTelegraph"), " ↗")));

  // links
  const radio = (val, label) => h("label", { class: "choice" },
    h("input", { type: "radio", name: "mode", value: val, checked: state.mode === val, onchange: () => { state.mode = val; store.set("mode", val); } }), label);
  const linksSec = sec("links", t("sLinks"), radio("first", t("linkFirst")), radio("all", t("linkAll")));

  // telegram
  const tgBody = h("div", { style: "display:grid;gap:10px" });
  const drawTg = () => {
    const botIn = h("input", { type: "password", placeholder: "123456:ABC-…", value: state.bot?.token || "", autocomplete: "off" });
    const status = h("span", { class: state.bot ? "ok small" : "small" }, state.bot ? t("tgBotOk", state.bot.username) : "");
    const manual = h("input", { type: "text", placeholder: "@channel", dir: "ltr" });
    const found = h("ul", { class: "chat-list" });
    const addChat = (c) => {
      if (!state.chats.some((x) => x.id === c.id)) state.chats.push(c);
      state.chatId = c.id; store.set("chats", state.chats); store.set("chatId", c.id); drawTg();
    };
    tgBody.replaceChildren(...[
      h("p", { class: "muted small", style: "margin:0" }, t("tgIntro")),
      h("div", { class: "field" }, h("label", {}, "1. ", t("tgStep1")),
        h("div", { class: "row" }, botIn, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, async () => {
          const me = await tg.getMe(botIn.value.trim());
          state.bot = { token: botIn.value.trim(), username: me.username }; store.set("bot", state.bot); drawTg();
        }) }, t("tgCheck"))),
        h("div", { class: "row" }, status, state.bot ? h("button", { class: "btn ghost small", onclick: () => { state.bot = null; store.set("bot", null); drawTg(); } }, t("remove")) : null)),
      state.bot ? h("div", { class: "field" }, h("label", {}, "2. ", t("tgStep2")),
        h("div", { class: "row" }, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, async () => {
          const chats = await tg.discoverChats(state.bot.token);
          found.replaceChildren(...(chats.length ? chats.map((c) => h("li", {}, h("span", { class: "spacer" }, c.name, " ", h("span", { class: "muted small" }, c.type)), h("button", { class: "btn small", onclick: () => addChat(c) }, t("use"))))
            : [h("li", { class: "muted small" }, t("tgNoneFound"))]));
        }) }, t("tgFind"))),
        found,
        h("div", { class: "row" }, manual, h("button", { class: "btn small", onclick: (e) => busy(e.currentTarget, async () => {
          const id = manual.value.trim(); if (!id) return;
          const chat = await tg.botCall(state.bot.token, "getChat", { chat_id: id });
          addChat({ id: String(chat.id), name: chat.title || chat.username || id });
        }) }, t("add"))), h("span", { class: "hint" }, t("tgManual"))) : null,
      state.chats.length ? h("ul", { class: "chat-list" }, state.chats.map((c) => h("li", {},
        h("span", { class: "spacer" }, c.id === state.chatId ? "● " : "", c.name),
        h("button", { class: "btn ghost small", onclick: () => { state.chats = state.chats.filter((x) => x.id !== c.id); store.set("chats", state.chats); drawTg(); } }, t("remove"))))) : null,
    ].filter(Boolean));
  };
  drawTg();
  const tgSec = BOT.api
    ? h("section", { class: "set", id: "set-telegram" },
      h("details", { open: !!state.bot || focus === "telegram" }, h("summary", {}, h("strong", {}, t("sManual"))), h("div", { style: "margin-top:10px" }, tgBody)))
    : sec("telegram", t("sTelegram"), tgBody);

  // auto-link bot
  const autoList = h("div", {});
  const drawAuto = () => autoList.replaceChildren(state.autoChannels.length
    ? h("div", {}, h("p", { class: "small", style: "margin:0 0 6px" }, t("autoConnected")),
      h("ul", { class: "chat-list" }, state.autoChannels.map((c) => h("li", {}, "✅ ", c.title))))
    : h("p", { class: "muted small", style: "margin:0" }, t("autoNone")));
  drawAuto();
  const autoSec = BOT.api ? sec("auto", t("sAuto"),
    h("p", { class: "small", style: "margin:0" }, t("autoIntro")),
    h("p", { class: "muted small", style: "margin:0" }, t("autoStep")),
    h("div", { class: "row" },
      h("button", { class: "btn primary", onclick: (e) => {
        // open the tab synchronously (popup blockers), then point it at the bot
        const win = window.open("about:blank", "_blank");
        busy(e.currentTarget, async () => {
          try {
            const { start_url } = await botApi("/api/connect", { index_path: g.indexPath });
            if (win) win.location.href = start_url; else location.href = start_url;
          } catch (err) { win?.close(); throw err; }
        });
      } }, t("autoConnect")),
      h("button", { class: "btn ghost small", onclick: (e) => busy(e.currentTarget, async () => { await refreshAuto(); drawAuto(); }) }, t("autoRefresh"))),
    autoList,
    h("p", { class: "muted small", style: "margin:0" }, t("autoOld"))) : null;

  // agents
  let revealed = false;
  const tok = () => (revealed ? state.token : "<YOUR_KEY>");
  const snippets = {
    "Claude Code": () => `claude mcp add telegraph-glossary -e TELEGRAPH_ACCESS_TOKEN=${tok()} -- uvx --from ${REPO} telegraph-glossary mcp`,
    Codex: () => `codex mcp add telegraph-glossary --env TELEGRAPH_ACCESS_TOKEN=${tok()} -- uvx --from ${REPO} telegraph-glossary mcp`,
    [t("other")]: () => JSON.stringify({ mcpServers: { "telegraph-glossary": { command: "uvx", args: ["--from", REPO, "telegraph-glossary", "mcp"], env: { TELEGRAPH_ACCESS_TOKEN: tok() } } } }, null, 2),
  };
  let which = "Claude Code";
  const code = h("pre", { class: "code" });
  const segBtns = Object.keys(snippets).map((k) => h("button", { type: "button", "aria-pressed": String(k === which), onclick: () => { which = k; segBtns.forEach((b) => b.setAttribute("aria-pressed", String(b.textContent === k))); drawCode(); } }, k));
  const drawCode = () => { code.textContent = snippets[which](); };
  drawCode();
  const agentsSec = sec("agents", t("sAgents"),
    h("p", { class: "muted small", style: "margin:0" }, t("agentsIntro")),
    h("div", { class: "seg" }, segBtns), code,
    h("div", { class: "row" },
      h("button", { class: "btn small", onclick: () => { revealed = true; copyText(snippets[which]()); drawCode(); } }, t("copy")),
      h("a", { class: "btn ghost small", href: "https://github.com/NehoraiHadad/telegraph-glossary#use-it-from-ai-agents", target: "_blank", rel: "noopener" }, "README ↗")));

  // key
  const keyOut = h("input", { type: "password", value: state.token, readOnly: true, dir: "ltr" });
  const keySec = sec("key", t("sKey"),
    h("p", { class: "warn", style: "margin:0" }, t("keyWarn")),
    h("div", { class: "row" }, keyOut,
      h("button", { class: "btn small", onclick: (e) => { const show = keyOut.type === "password"; keyOut.type = show ? "text" : "password"; e.currentTarget.textContent = show ? t("hide") : t("show"); } }, t("show")),
      h("button", { class: "btn small", onclick: () => copyText(state.token) }, t("copy"))),
    h("div", { class: "row" },
      h("button", { class: "btn small", onclick: () => downloadKey() }, t("downloadKey")),
      h("button", { class: "btn small", onclick: () => copyText(`${APP_URL}#key=${encodeURIComponent(state.token)}`, t("linkCopied")) }, t("deviceLink"))));

  const langSec = sec("lang", t("sLanguage"), h("div", { class: "seg" },
    ["he", "en"].map((l) => h("button", { type: "button", "aria-pressed": String(state.lang === l), onclick: () => { state.lang = l; store.set("lang", l); applyLang(); d.close(); render(); openSettings(); } }, l === "he" ? "עברית" : "English"))));

  const d = dialog(t("settings"), [autoSec, glossarySec, tgSec, linksSec, agentsSec, keySec, langSec,
    h("section", { class: "set" }, h("button", { class: "btn danger", onclick: () => {
      if (!confirm(t("confirmSignOut"))) return;
      ["token", "draft", "bot", "chats", "chatId", "autoChannels"].forEach((k) => store.set(k, null));
      Object.assign(state, { token: null, glossary: null, draft: "", bot: null, chats: [], chatId: null, autoChannels: [] });
      d.close(); renderWelcome();
    } }, t("signOut")))]);
  d.addEventListener("close", () => { if (state.view === "write") render(); });
  if (typeof focus === "string") d.querySelector(`#set-${focus}`)?.scrollIntoView({ block: "start" });
}

function downloadKey() {
  const text = [
    `Telegraph Glossary — ${state.glossary.title}`,
    "",
    `Key: ${state.token}`,
    `Open: ${APP_URL}#key=${encodeURIComponent(state.token)}`,
    `Index: ${state.glossary.indexUrl}`,
    "",
    "Keep this file private: anyone with the key can edit the glossary.",
  ].join("\n");
  const a = h("a", { href: URL.createObjectURL(new Blob([text], { type: "text/plain" })), download: "telegraph-glossary-key.txt" });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refreshAuto(); });

boot();
