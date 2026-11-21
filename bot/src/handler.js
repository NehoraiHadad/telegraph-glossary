// Channel auto-link bot. Platform independent: all I/O is injected, so the same
// logic runs in the Cloudflare Worker (index.js) and in tests.
//
// The bot never holds anyone's Telegraph key. Glossaries are public pages, so all
// it needs is "channel X uses the glossary whose index page is P".
//
// KV layout (values are JSON):
//   code:<code>        -> index path          (one-time connect codes, 1 day)
//   user:<userId>      -> index path          (the glossary a person connected)
//   pending:<userId>   -> [chat]              (channels added before /start)
//   chan:<chatId>      -> {path, owner, title, mode}
//   gchans:<path>      -> [chatId]            (channels using a glossary)
//   gver:<path>        -> version hash of the glossary last applied
//   posts:<chatId>     -> [{id, v}]           (recent posts + glossary version applied)
//   post:<chatId>:<id> -> {text, entities, caption, preview, markup, paths}

import { addLinkEntities, stripGlossaryLinks, sameEntities } from "../../web/core/entities.js";
import { parseIndex } from "../../web/core/glossary.js";
import { pathFromUrl } from "../../web/core/telegraph.js";

const MAX_POSTS = 300; // remembered per channel
const MAX_EDITS_PER_RUN = 30; // stay well under platform subrequest limits
const CODE_TTL = 24 * 3600;

const T = {
  he: {
    hello: "היי! אני מוסיף קישורים למונחים מהמילון שלך בפוסטים בערוץ, אוטומטית.\n\nכדי להתחיל, פתח את אתר המילון ← הגדרות ← \"קישור אוטומטי בערוץ\".",
    linked: (title) => `✅ המילון „${title}” מחובר.\n\nעכשיו הוסף אותי כמנהל לערוץ (עם הרשאת עריכת הודעות):`,
    addBtn: "➕ הוספה לערוץ",
    chanOk: (c, g) => `✅ הערוץ „${c}” מחובר למילון „${g}”.\nכל פוסט חדש יקבל קישורים אוטומטית. כשתוסיף מונחים, אעדכן גם פוסטים קודמים.\n\nפוסטים ישנים מלפני החיבור? פשוט תעביר (forward) אותם אליי.`,
    chanNoGlossary: (c) => `נוספתי לערוץ „${c}”, אבל עוד לא ידוע לי איזה מילון לחבר. פתח את אתר המילון ← הגדרות ← "קישור אוטומטי בערוץ".`,
    noEditRight: (c) => `⚠️ אין לי הרשאה לערוך הודעות בערוץ „${c}”. תן לי את ההרשאה „עריכת הודעות של אחרים” בהגדרות המנהלים.`,
    removed: (c) => `הוסרתי מהערוץ „${c}”, הוא כבר לא מחובר.`,
    status: (list) => (list.length ? `ערוצים מחוברים:\n${list.join("\n")}` : "אין ערוצים מחוברים."),
    fwdDone: (n) => (n ? `✅ עודכן (${n} מונחים).` : "אין בפוסט הזה מונחים מהמילון."),
    fwdUnknown: "את הפוסט הזה אני לא יכול לעדכן: הערוץ שלו לא מחובר אליי, או שהפוסט לא הועבר ישירות מהערוץ.",
    badCode: "הקישור פג תוקף. פתח שוב את ההגדרות באתר ולחץ על החיבור מחדש.",
    help: "פקודות: /status — ערוצים מחוברים. כדי לעדכן פוסט ישן, העבר אותו אליי.",
  },
  en: {
    hello: "Hi! I add links to your glossary terms in your channel posts, automatically.\n\nTo start, open the glossary web app → Settings → \"Auto-link my channel\".",
    linked: (title) => `✅ Glossary “${title}” connected.\n\nNow add me to your channel as an admin (with “edit messages”):`,
    addBtn: "➕ Add to channel",
    chanOk: (c, g) => `✅ Channel “${c}” now uses the glossary “${g}”.\nEvery new post gets links automatically, and when you add terms I update earlier posts too.\n\nOlder posts from before? Just forward them to me.`,
    chanNoGlossary: (c) => `I was added to “${c}”, but I don't know which glossary to use yet. Open the glossary web app → Settings → "Auto-link my channel".`,
    noEditRight: (c) => `⚠️ I can't edit messages in “${c}”. Please give me the “Edit messages of others” admin right.`,
    removed: (c) => `I was removed from “${c}”, so it's no longer connected.`,
    status: (list) => (list.length ? `Connected channels:\n${list.join("\n")}` : "No connected channels."),
    fwdDone: (n) => (n ? `✅ Updated (${n} terms).` : "No glossary terms in this post."),
    fwdUnknown: "I can't update that post: its channel isn't connected to me, or it wasn't forwarded straight from the channel.",
    badCode: "That link expired. Open the settings in the web app and connect again.",
    help: "Commands: /status — connected channels. To update an old post, forward it to me.",
  },
};
const tr = (user) => T[(user?.language_code || "").startsWith("he") ? "he" : "en"];

export function hashTerms(terms) {
  const s = JSON.stringify([...terms].map((t) => [t.term, t.aliases, t.path]).sort());
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(36);
}

export function randomCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(9));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_");
}

/**
 * deps: {
 *   kv: { get(key) -> json|null, put(key, json, {ttl}?), del(key), list(prefix) -> [key] },
 *   tg(method, params) -> result (throws Error with .description),
 *   getPage(path) -> {title, content},   // Telegraph page (public)
 *   username() -> bot @username (without @),
 * }
 */
export function createBot(deps) {
  const { kv, tg } = deps;
  const cache = new Map(); // path -> {at, g}

  async function glossary(path, fresh = false) {
    const c = cache.get(path);
    if (!fresh && c && Date.now() - c.at < 60_000) return c.g;
    const page = await deps.getPage(path);
    const terms = parseIndex(page.content);
    const g = { path, title: page.title, terms, version: hashTerms(terms), paths: new Set(terms.map((t) => t.path)) };
    cache.set(path, { at: Date.now(), g });
    return g;
  }

  const say = (chatId, text, extra = {}) => tg("sendMessage", { chat_id: chatId, text, ...extra }).catch(() => {});
  // Deep link that opens "add to channel" with the edit right preselected (core.telegram.org/api/links).
  const addToChannelUrl = async () => `https://t.me/${await deps.username()}?startchannel&admin=edit_messages`;

  // ------------------------------------------------------------ binding
  async function connectCode(path) {
    const code = randomCode();
    await kv.put(`code:${code}`, path, { ttl: CODE_TTL });
    const bot = await deps.username();
    return { code, start_url: `https://t.me/${bot}?start=${code}`, bot_username: bot };
  }

  async function bindChannel(chat, owner, path) {
    const prev = await kv.get(`chan:${chat.id}`);
    if (prev && prev.path !== path) await unlistChannel(prev.path, chat.id);
    await kv.put(`chan:${chat.id}`, { path, owner: owner?.id, lang: owner?.language_code, title: chat.title, mode: prev?.mode || "first" });
    const list = (await kv.get(`gchans:${path}`)) || [];
    if (!list.includes(String(chat.id))) await kv.put(`gchans:${path}`, [...list, String(chat.id)]);
    const g = await glossary(path);
    if (owner) await say(owner.id, tr(owner).chanOk(chat.title, g.title));
  }

  async function unlistChannel(path, chatId) {
    const list = ((await kv.get(`gchans:${path}`)) || []).filter((id) => id !== String(chatId));
    list.length ? await kv.put(`gchans:${path}`, list) : await kv.del(`gchans:${path}`);
  }

  async function unbindChannel(chat, by) {
    const b = await kv.get(`chan:${chat.id}`);
    if (!b) return;
    await unlistChannel(b.path, chat.id);
    await kv.del(`chan:${chat.id}`);
    if (b.owner) await say(b.owner, tr(by).removed(chat.title));
  }

  // ------------------------------------------------------------ linking posts
  /** Recompute links for a stored post and edit it if anything changed. Returns #terms linked. */
  async function apply(chatId, id, rec, g, mode, current) {
    const { entities, found } = addLinkEntities(rec.text, rec.entities, g.terms, { mode });
    rec.paths = [...new Set(entities.filter((e) => e.type === "text_link").map((e) => pathFromUrl(e.url)).filter((p) => p && (g.paths.has(p) || rec.paths?.includes(p))))];
    if (!sameEntities(entities, current)) {
      const common = { chat_id: chatId, message_id: id, ...(rec.markup ? { reply_markup: rec.markup } : {}) };
      try {
        if (rec.caption) await tg("editMessageCaption", { ...common, caption: rec.text, caption_entities: entities });
        else await tg("editMessageText", { ...common, text: rec.text, entities, link_preview_options: rec.preview || { is_disabled: true } });
      } catch (e) {
        if (!/not modified/i.test(e.message)) throw e;
      }
    }
    rec.applied = entities;
    return found.length;
  }

  async function remember(chatId, id, rec, version) {
    await kv.put(`post:${chatId}:${id}`, rec);
    const list = ((await kv.get(`posts:${chatId}`)) || []).filter((p) => p.id !== id);
    list.push({ id, v: version });
    for (const old of list.splice(0, Math.max(0, list.length - MAX_POSTS))) await kv.del(`post:${chatId}:${old.id}`);
    await kv.put(`posts:${chatId}`, list);
  }

  /** A post arrived (new, edited by its author, or forwarded to us). */
  async function handlePost(chatId, msg, { forwarded = false } = {}) {
    const binding = await kv.get(`chan:${chatId}`);
    if (!binding) return null;
    const text = msg.text ?? msg.caption;
    if (!text) return 0;
    const id = forwarded ? msg.forward_origin.message_id : msg.message_id;
    const g = await glossary(binding.path);
    const prev = await kv.get(`post:${chatId}:${id}`);
    const known = new Set([...g.paths, ...(prev?.paths || [])]);
    const isOurs = (u) => { const p = pathFromUrl(u); return !!p && known.has(p); };
    const current = msg.entities ?? msg.caption_entities ?? [];
    const rec = {
      text,
      entities: stripGlossaryLinks(current, isOurs),
      caption: msg.text === undefined,
      preview: msg.link_preview_options || prev?.preview || null,
      markup: msg.reply_markup || prev?.markup || null,
      paths: prev?.paths || [],
    };
    try {
      const n = await apply(chatId, id, rec, g, binding.mode, current);
      await remember(chatId, id, rec, g.version);
      return n;
    } catch (e) {
      if (/rights|can't be edited|not enough/i.test(e.message) && binding.owner) await say(binding.owner, tr({ language_code: binding.lang }).noEditRight(binding.title));
      throw e;
    }
  }

  /** Glossary changed: re-apply to remembered posts (newest first, bounded per run). */
  async function resync(path, budget = { edits: MAX_EDITS_PER_RUN }) {
    const g = await glossary(path, true);
    if ((await kv.get(`gver:${path}`)) === g.version) return 0;
    let done = 0, complete = true;
    for (const chatId of (await kv.get(`gchans:${path}`)) || []) {
      const binding = await kv.get(`chan:${chatId}`);
      const list = (await kv.get(`posts:${chatId}`)) || [];
      for (const p of [...list].reverse()) {
        if (p.v === g.version) continue;
        if (budget.edits <= 0) { complete = false; break; }
        const rec = await kv.get(`post:${chatId}:${p.id}`);
        if (rec) {
          try { await apply(chatId, p.id, rec, g, binding?.mode, rec.applied || rec.entities); budget.edits--; done++; await kv.put(`post:${chatId}:${p.id}`, rec); }
          catch (e) { if (!/not found|can't be edited|MESSAGE_ID_INVALID/i.test(e.message)) { complete = false; break; } }
        }
        p.v = g.version;
      }
      await kv.put(`posts:${chatId}`, list);
    }
    if (complete) await kv.put(`gver:${path}`, g.version);
    return done;
  }

  // ------------------------------------------------------------ updates
  async function handleUpdate(u) {
    if (u.channel_post) return handlePost(u.channel_post.chat.id, u.channel_post);
    if (u.edited_channel_post) return handlePost(u.edited_channel_post.chat.id, u.edited_channel_post);

    if (u.my_chat_member) {
      const { chat, from, new_chat_member: m } = u.my_chat_member;
      if (chat.type !== "channel") return;
      if (["left", "kicked"].includes(m.status)) return unbindChannel(chat, from);
      if (m.status !== "administrator") return;
      if (m.can_edit_messages === false) await say(from.id, tr(from).noEditRight(chat.title));
      const path = await kv.get(`user:${from.id}`);
      if (path) return bindChannel(chat, from, path);
      const pending = (await kv.get(`pending:${from.id}`)) || [];
      await kv.put(`pending:${from.id}`, [...pending.filter((c) => c.id !== chat.id), { id: chat.id, title: chat.title }], { ttl: 7 * 24 * 3600 });
      return say(from.id, tr(from).chanNoGlossary(chat.title));
    }

    const msg = u.message;
    if (!msg || msg.chat.type !== "private") return;
    const user = msg.from, s = tr(user);

    if (msg.forward_origin?.type === "channel") {
      const chat = msg.forward_origin.chat;
      const binding = await kv.get(`chan:${chat.id}`);
      if (!binding || (binding.owner && binding.owner !== user.id)) return say(user.id, s.fwdUnknown);
      try { return say(user.id, s.fwdDone(await handlePost(chat.id, msg, { forwarded: true }))); }
      catch (e) { return say(user.id, `⚠️ ${e.message}`); }
    }

    const [cmd, arg] = (msg.text || "").trim().split(/\s+/, 2);
    if (cmd === "/start" && arg) {
      const path = await kv.get(`code:${arg}`);
      if (!path) return say(user.id, s.badCode);
      await kv.del(`code:${arg}`);
      await kv.put(`user:${user.id}`, path);
      const g = await glossary(path);
      await say(user.id, s.linked(g.title), { reply_markup: { inline_keyboard: [[{ text: s.addBtn, url: await addToChannelUrl() }]] } });
      for (const c of (await kv.get(`pending:${user.id}`)) || []) await bindChannel(c, user, path);
      await kv.del(`pending:${user.id}`);
      return;
    }
    if (cmd === "/status") {
      const path = await kv.get(`user:${user.id}`);
      const ids = path ? (await kv.get(`gchans:${path}`)) || [] : [];
      const names = await Promise.all(ids.map(async (id) => (await kv.get(`chan:${id}`))?.title || id));
      return say(user.id, s.status(names.map((n) => `• ${n}`)));
    }
    return say(user.id, cmd === "/start" ? s.hello : s.help);
  }

  async function status(path) {
    const ids = (await kv.get(`gchans:${path}`)) || [];
    return Promise.all(ids.map(async (id) => ({ id, title: (await kv.get(`chan:${id}`))?.title || id })));
  }

  async function cron() {
    let budget = { edits: MAX_EDITS_PER_RUN };
    for (const key of await kv.list("gchans:")) {
      if (budget.edits <= 0) break;
      try { await resync(key.slice("gchans:".length), budget); } catch (e) { console.error("resync", key, e); }
    }
  }

  return { handleUpdate, connectCode, status, resync, cron, glossary, username: deps.username };
}
