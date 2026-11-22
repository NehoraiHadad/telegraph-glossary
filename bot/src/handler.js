// Channel auto-link bot. Platform independent: all I/O is injected, so the same
// logic runs in the Cloudflare Worker (index.js) and in tests.
//
// The bot never holds anyone's Telegraph key. Glossaries are public pages, so it
// stores which channel uses which glossary, plus the text of each channel's last
// MAX_POSTS posts (Telegram's edit methods need the full text). Removing the bot from
// a channel deletes that channel's binding and post texts.
//
// KV layout (values are JSON):
//   code:<code>        -> {path, lang, usedBy?} (one-time connect codes, 1 day; usedBy once used)
//   user:<userId>      -> index path          (the glossary a person connected)
//   pending:<userId>   -> [chat]              (channels added before /start)
//   chan:<chatId>      -> {path, owner, title, mode, removing?}  (removing: the bot left, cleanup under way)
//   gchans:<path>      -> [chatId]            (channels using a glossary)
//   gver:<path>        -> version hash of the glossary last applied
//   cron:next          -> gchans key the next cron run starts at (only when a run stops early)
//   posts:<chatId>     -> [{id, v}]           (recent posts + glossary version applied)
//   post:<chatId>:<id> -> {text, entities, caption, preview, paths}

import { addLinkEntities, stripGlossaryLinks, sameEntities } from "../../web/core/entities.js";
import { parseIndex } from "../../web/core/glossary.js";
import { pathFromUrl } from "../../web/core/telegraph.js";

const MAX_POSTS = 300; // remembered per channel
// External requests (Telegraph fetches, Telegram edits) per run. The Workers free plan allows 50
// per invocation (developers.cloudflare.com/workers/platform/limits/#subrequests); leave headroom.
const MAX_REQUESTS_PER_RUN = 45;
const CODE_TTL = 24 * 3600;
// Telegram edit failures that a retry cannot fix.
const PERMANENT_EDIT_ERROR = /rights|can't be edited|not enough|MESSAGE_ID_INVALID|message to edit not found/i;

const T = {
  he: {
    hello: "היי! אני מוסיף קישורים למונחים מהמילון שלך בפוסטים בערוץ, אוטומטית.\n\nפתח את המילון, הוסף מונח, וחבר את הערוץ.",
    openApp: "📖 פתיחת המילון",
    langSet: "מעכשיו אדבר איתך בעברית.",
    linked: (title) => `✅ המילון „${title}” מחובר.\n\nעכשיו הוסף אותי כמנהל לערוץ (עם הרשאת עריכת הודעות):`,
    addBtn: "➕ הוספה לערוץ",
    chanOk: (c, g) => `✅ הערוץ „${c}” מחובר למילון „${g}”.\nכל פוסט חדש יקבל קישורים אוטומטית. כשתוסיף מונחים, אעדכן גם פוסטים קודמים.\n\nפוסטים ישנים מלפני החיבור? פשוט תעביר (forward) אותם אליי.`,
    chanNoGlossary: (c) => `נוספתי לערוץ „${c}”, אבל עוד לא ידוע לי איזה מילון לחבר. פתח את אתר המילון ← הגדרות ← "קישור אוטומטי בערוץ".`,
    noEditRight: (c) => `⚠️ אין לי הרשאה לערוך הודעות בערוץ „${c}”. תן לי את ההרשאה „עריכת הודעות של אחרים” בהגדרות המנהלים.`,
    moveOffer: (c, g) => `הערוץ „${c}” מחובר כרגע למילון אחר. להעביר אותו למילון „${g}”?`,
    moveBtn: "העברה לכאן",
    removed: (c) => `הוסרתי מהערוץ „${c}”, הוא כבר לא מחובר.`,
    status: (list) => (list.length ? `ערוצים מחוברים:\n${list.join("\n")}` : "אין ערוצים מחוברים."),
    fwdDone: (n) => (n ? `✅ עודכן (${n} מונחים).` : "אין בפוסט הזה מונחים מהמילון."),
    fwdButtons: "לפוסט הזה יש כפתורים, ואת הפוסט יכול לערוך רק הבוט שהוסיף אותם. לכן אני לא יכול להוסיף לו קישורים.",
    fwdUnknown: "את הפוסט הזה אני לא יכול לעדכן: הערוץ שלו לא מחובר אליי, או שהפוסט לא הועבר ישירות מהערוץ.",
    badCode: "הקישור פג תוקף. פתח שוב את ההגדרות באתר ולחץ על החיבור מחדש.",
    help: "/status: ערוצים מחוברים\n/language: שפה\nכדי לעדכן פוסט ישן, העבר אותו אליי.",
  },
  en: {
    hello: "Hi! I add links to your glossary terms in your channel posts, automatically.\n\nOpen the glossary, add a term, and connect your channel.",
    openApp: "📖 Open the glossary",
    langSet: "I'll talk to you in English from now on.",
    linked: (title) => `✅ Glossary “${title}” connected.\n\nNow add me to your channel as an admin (with “edit messages”):`,
    addBtn: "➕ Add to channel",
    chanOk: (c, g) => `✅ Channel “${c}” now uses the glossary “${g}”.\nEvery new post gets links automatically, and when you add terms I update earlier posts too.\n\nOlder posts from before? Just forward them to me.`,
    chanNoGlossary: (c) => `I was added to “${c}”, but I don't know which glossary to use yet. Open the glossary web app → Settings → "Auto-link my channel".`,
    noEditRight: (c) => `⚠️ I can't edit messages in “${c}”. Please give me the “Edit messages of others” admin right.`,
    moveOffer: (c, g) => `Channel “${c}” is connected to another glossary. Move it to “${g}”?`,
    moveBtn: "Move it here",
    removed: (c) => `I was removed from “${c}”, so it's no longer connected.`,
    status: (list) => (list.length ? `Connected channels:\n${list.join("\n")}` : "No connected channels."),
    fwdDone: (n) => (n ? `✅ Updated (${n} terms).` : "No glossary terms in this post."),
    fwdButtons: "This post has buttons, and only the bot that added them can edit it, so I can't add links to it.",
    fwdUnknown: "I can't update that post: its channel isn't connected to me, or it wasn't forwarded straight from the channel.",
    badCode: "That link expired. Open the settings in the web app and connect again.",
    help: "/status: connected channels\n/language: language\nTo update an old post, forward it to me.",
  },
};
/**
 * Inline keyboards on channel posts always belong to some other bot (users can't add them, and
 * this bot never does). Telegram rejects every edit of such a post by any other bot with
 * MESSAGE_ID_INVALID, with or without reply_markup, so these posts are left alone.
 */
const hasButtons = (msg) => !!msg.reply_markup?.inline_keyboard?.length;

const tr = (user) => T[(user?.language_code || "").startsWith("he") ? "he" : "en"];
const CHOOSE_LANG = "בחר שפה · Choose a language";
const LANG_BUTTONS = { inline_keyboard: [[{ text: "עברית", callback_data: "lang:he" }, { text: "English", callback_data: "lang:en" }]] };

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
 *   webAppUrl?,                           // the web app, opened as a Telegram Mini App
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

  // A language the user picked with /language wins over their Telegram app language.
  async function langOf(user) {
    const pref = user?.id ? await kv.get(`lang:${user.id}`) : null;
    return pref || ((user?.language_code || "").startsWith("he") ? "he" : "en");
  }
  const trU = async (user) => T[await langOf(user)];

  const say = (chatId, text, extra = {}) => tg("sendMessage", { chat_id: chatId, text, ...extra }).catch(() => {});
  // A message to send later: flows that save state collect these and send them once all state is saved.
  const notice = (chatId, text, extra = {}) => ({ chatId, text, extra });
  const send = async (notices) => { for (const n of notices) if (n) await say(n.chatId, n.text, n.extra); };
  // Deep link that opens "add to channel" with the edit right preselected (core.telegram.org/api/links).
  const addToChannelUrl = async () => `https://t.me/${await deps.username()}?startchannel&admin=edit_messages`;

  // ------------------------------------------------------------ binding
  /** `lang` is the web app's language: the bot then talks in it, unless the user picked another one. */
  async function connectCode(path, lang) {
    const code = randomCode();
    await kv.put(`code:${code}`, { path, lang: T[lang] ? lang : null }, { ttl: CODE_TTL });
    const bot = await deps.username();
    return { code, start_url: `https://t.me/${bot}?start=${code}`, bot_username: bot };
  }

  /**
   * Saves the binding and returns the owner's notice (or null), for the caller to send after all of
   * its state is saved. `canEdit: false`: bound, but not usable yet, so the owner gets the
   * missing-right warning instead of "connected".
   */
  async function bindChannel(chat, owner, path, { canEdit = true } = {}) {
    let prev = await kv.get(`chan:${chat.id}`);
    if (prev?.removing) { await purgeChannel(chat.id, prev); prev = null; } // re-added before a removal finished
    if (prev && prev.path !== path) {
      await unlistChannel(prev.path, chat.id);
      await kv.del(`gver:${path}`); // the next resync must also cover this channel's posts
    }
    if (prev?.owner && prev.owner !== owner?.id) await setOwned(prev.owner, chat.id, false);
    if (owner) await setOwned(owner.id, chat.id, true);
    await kv.put(`chan:${chat.id}`, { path, owner: owner?.id, lang: owner ? await langOf(owner) : "en", title: chat.title, mode: prev?.mode || "first" });
    const list = (await kv.get(`gchans:${path}`)) || [];
    if (!list.includes(String(chat.id))) await kv.put(`gchans:${path}`, [...list, String(chat.id)]);
    const g = await glossary(path);
    if (!owner) return null;
    const s = await trU(owner);
    return notice(owner.id, canEdit ? s.chanOk(chat.title, g.title) : s.noEditRight(chat.title));
  }

  /**
   * Channels each user connected. Telegram sends my_chat_member only when the bot's status changes,
   * so re-adding the bot to a channel where it is already an admin produces no update at all. To move
   * such a channel to another glossary the bot has to know it already, and offer the move itself.
   */
  async function setOwned(userId, chatId, on) {
    const list = ((await kv.get(`uchans:${userId}`)) || []).filter((id) => id !== String(chatId));
    if (on) list.push(String(chatId));
    list.length ? await kv.put(`uchans:${userId}`, list) : await kv.del(`uchans:${userId}`);
  }

  /** Called when a user connects a glossary: offers to move their channels that use another one (reads only). */
  async function moveOffers(user, path) {
    const s = await trU(user);
    const offers = [];
    let g;
    for (const id of (await kv.get(`uchans:${user.id}`)) || []) {
      const b = await activeBinding(id);
      if (!b || b.path === path) continue;
      g ||= await glossary(path);
      offers.push(notice(user.id, s.moveOffer(b.title, g.title), { reply_markup: { inline_keyboard: [[{ text: s.moveBtn, callback_data: `move:${id}` }]] } }));
    }
    return offers;
  }

  async function unlistChannel(path, chatId) {
    const list = ((await kv.get(`gchans:${path}`)) || []).filter((id) => id !== String(chatId));
    list.length ? await kv.put(`gchans:${path}`, list) : await kv.del(`gchans:${path}`);
  }

  /**
   * The bot left the channel. The binding is first marked `removing`: from then on no post of the
   * channel is edited or stored (activeBinding is checked by handlePost, remember and resync), so the
   * cleanup cannot race a post into an orphan record. The cleanup is idempotent and deletes the
   * binding last, so a failure part-way is finished by Telegram's retry (the webhook answers 500),
   * which finds the marked binding. The message goes out after everything is deleted.
   */
  async function unbindChannel(chat, by) {
    let b = await kv.get(`chan:${chat.id}`);
    if (!b) return;
    if (!b.removing) { b = { ...b, removing: true }; await kv.put(`chan:${chat.id}`, b); }
    await purgeChannel(chat.id, b);
    if (b.owner) await say(b.owner, (await trU(by)).removed(chat.title));
  }

  /** Deletes everything stored for a channel whose binding is marked `removing`; the binding goes last. */
  async function purgeChannel(chatId, b) {
    await unlistChannel(b.path, chatId);
    if (b.owner) await setOwned(b.owner, chatId, false);
    // The bot no longer belongs to the channel, so it must not keep the channel's post texts.
    // One delete per remembered post (up to MAX_POSTS): the KV free plan allows 1,000 deletes a
    // day (developers.cloudflare.com/kv/platform/pricing/), which is enough because removal is rare.
    // A channel that only moves to another glossary never comes here: its posts stay valid.
    for (const p of (await kv.get(`posts:${chatId}`)) || []) await kv.del(`post:${chatId}:${p.id}`);
    await kv.del(`posts:${chatId}`);
    await kv.del(`chan:${chatId}`);
  }

  /** The channel's binding, unless there is none or the bot is leaving the channel. */
  async function activeBinding(chatId) {
    const b = await kv.get(`chan:${chatId}`);
    return b && !b.removing ? b : null;
  }

  // ------------------------------------------------------------ linking posts
  /** Recompute links for a stored post and edit it if anything changed. Returns #terms linked. */
  async function apply(chatId, id, rec, g, mode, current) {
    const { entities, found } = addLinkEntities(rec.text, rec.entities, g.terms, { mode });
    rec.paths = [...new Set(entities.filter((e) => e.type === "text_link").map((e) => pathFromUrl(e.url)).filter((p) => p && (g.paths.has(p) || rec.paths?.includes(p))))];
    if (!sameEntities(entities, current)) {
      const common = { chat_id: chatId, message_id: id };
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
    // Checked again right before storing: a removal may have started while the post was being
    // edited. (KV has no transactions, so a removal that starts during these few writes can still race.)
    if (!(await activeBinding(chatId))) return;
    await kv.put(`post:${chatId}:${id}`, rec);
    const list = ((await kv.get(`posts:${chatId}`)) || []).filter((p) => p.id !== id);
    list.push({ id, v: version });
    for (const old of list.splice(0, Math.max(0, list.length - MAX_POSTS))) await kv.del(`post:${chatId}:${old.id}`);
    await kv.put(`posts:${chatId}`, list);
  }

  /** A post arrived (new, edited by its author, or forwarded to us). */
  async function handlePost(chatId, msg, { forwarded = false } = {}) {
    const binding = await activeBinding(chatId);
    if (!binding) return null;
    const text = msg.text ?? msg.caption;
    if (!text || hasButtons(msg)) return 0;
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

  /**
   * Glossary changed: re-apply to remembered posts (newest first, bounded per run).
   * Anyone may trigger this (/api/changed carries no authority), so it only acts on public state
   * and writes to KV only what actually changed: an unchanged glossary or a glossary without
   * channels costs reads only.
   * `budget.requests` counts external requests, failed ones included: the Telegraph fetch and
   * every Telegram attempt. An unexpected (likely transient) error ends the run.
   */
  async function resync(path, budget = { requests: MAX_REQUESTS_PER_RUN }) {
    const chats = (await kv.get(`gchans:${path}`)) || [];
    if (!chats.length || budget.requests <= 0) return 0;
    budget.requests--;
    const g = await glossary(path, true);
    if ((await kv.get(`gver:${path}`)) === g.version) return 0;
    let done = 0, complete = true, stop = false;
    for (const chatId of chats) {
      const binding = await activeBinding(chatId);
      if (!binding) continue; // the bot is leaving this channel: its posts are being deleted
      const list = (await kv.get(`posts:${chatId}`)) || [];
      let dirty = false;
      for (const p of [...list].reverse()) {
        if (p.v === g.version) continue;
        if (budget.requests <= 0) { complete = false; stop = true; break; }
        const rec = await kv.get(`post:${chatId}:${p.id}`);
        if (rec) {
          budget.requests--;
          try { await apply(chatId, p.id, rec, g, binding.mode,rec.applied || rec.entities); done++; await kv.put(`post:${chatId}:${p.id}`, rec); }
          catch (e) { if (!/not found|can't be edited|MESSAGE_ID_INVALID/i.test(e.message)) { complete = false; stop = true; break; } }
        }
        p.v = g.version;
        dirty = true;
      }
      if (dirty) await kv.put(`posts:${chatId}`, list);
      if (stop) break;
    }
    if (complete) await kv.put(`gver:${path}`, g.version);
    return done;
  }

  // ------------------------------------------------------------ updates
  /**
   * A channel post the bot can never edit (missing right, post owned by another bot, post gone).
   * handlePost already told the owner where that helps. Throwing would make the webhook answer 500
   * and Telegram redeliver the same update that fails the same way, so it is swallowed here.
   */
  async function channelPost(msg) {
    try { return await handlePost(msg.chat.id, msg); }
    catch (e) { if (!PERMANENT_EDIT_ERROR.test(e.message)) throw e; }
  }

  /**
   * Throws only on errors a retry can fix (Telegraph or Telegram unreachable, KV failure), so the
   * webhook can answer 500 and Telegram redelivers. A redelivered update is harmless: an edit that
   * changes nothing is "not modified", and remember() replaces a post's record by id.
   */
  async function handleUpdate(u) {
    if (u.channel_post) return channelPost(u.channel_post);
    if (u.edited_channel_post) return channelPost(u.edited_channel_post);

    if (u.my_chat_member) {
      const { chat, from, new_chat_member: m } = u.my_chat_member;
      if (chat.type !== "channel") return;
      if (["left", "kicked"].includes(m.status)) return unbindChannel(chat, from);
      if (m.status !== "administrator") return;
      // Bind anyway: Telegram promises no update when rights change, so the channel must work as
      // soon as the right is granted. Until then only the warning is true, not "connected".
      // Messages are sent after the state is saved, so a retried update doesn't repeat them.
      const canEdit = m.can_edit_messages !== false;
      const path = await kv.get(`user:${from.id}`);
      if (path) return send([await bindChannel(chat, from, path, { canEdit })]);
      const pending = (await kv.get(`pending:${from.id}`)) || [];
      await kv.put(`pending:${from.id}`, [...pending.filter((c) => c.id !== chat.id), { id: chat.id, title: chat.title }], { ttl: 7 * 24 * 3600 });
      const sf = await trU(from);
      if (!canEdit) await say(from.id, sf.noEditRight(chat.title));
      return say(from.id, sf.chanNoGlossary(chat.title));
    }

    if (u.callback_query) {
      const q = u.callback_query;
      const move = /^move:(-?\d+)$/.exec(q.data || "")?.[1];
      if (move) {
        await tg("answerCallbackQuery", { callback_query_id: q.id }).catch(() => {});
        const b = await activeBinding(move), path = await kv.get(`user:${q.from.id}`);
        if (q.message) await tg("editMessageReplyMarkup", { chat_id: q.message.chat.id, message_id: q.message.message_id, reply_markup: { inline_keyboard: [] } }).catch(() => {});
        if (!b || b.owner !== q.from.id || !path || b.path === path) return;
        return send([await bindChannel({ id: Number(move), title: b.title }, q.from, path)]);
      }
      const lang = /^lang:(he|en)$/.exec(q.data || "")?.[1];
      if (!lang) return tg("answerCallbackQuery", { callback_query_id: q.id }).catch(() => {});
      await kv.put(`lang:${q.from.id}`, lang);
      await tg("answerCallbackQuery", { callback_query_id: q.id, text: T[lang].langSet }).catch(() => {});
      if (q.message) await tg("editMessageText", { chat_id: q.message.chat.id, message_id: q.message.message_id, text: T[lang].langSet }).catch(() => {});
      return;
    }

    const msg = u.message;
    if (!msg || msg.chat.type !== "private") return;
    const user = msg.from, s = await trU(user);

    if (msg.forward_origin?.type === "channel") {
      const chat = msg.forward_origin.chat;
      const binding = await activeBinding(chat.id);
      if (!binding || (binding.owner && binding.owner !== user.id)) return say(user.id, s.fwdUnknown);
      if (hasButtons(msg)) return say(user.id, s.fwdButtons);
      try { return say(user.id, s.fwdDone(await handlePost(chat.id, msg, { forwarded: true }))); }
      catch (e) { return say(user.id, `⚠️ ${e.message}`); }
    }

    const [cmd, arg] = (msg.text || "").trim().split(/\s+/, 2);
    if (cmd === "/start" && arg) {
      const entry = await kv.get(`code:${arg}`);
      if (!entry) return say(user.id, s.badCode);
      const { path, lang, usedBy } = typeof entry === "string" ? { path: entry } : entry; // codes made before lang was stored
      // Used already. By this user: a redelivered update (or the link tapped again) whose messages
      // went out once, so only the cleanup that follows them is finished, silently.
      if (usedBy !== undefined) {
        if (usedBy !== user.id) return say(user.id, s.badCode);
        if (await kv.get(`pending:${user.id}`)) await kv.del(`pending:${user.id}`);
        return;
      }
      // Every state change first, then the code is marked used (the commit point), then messages.
      // A failure before the commit has sent nothing, and Telegram's retry redoes the idempotent steps.
      const g = await glossary(path);
      await kv.put(`user:${user.id}`, path);
      if (lang && !(await kv.get(`lang:${user.id}`))) await kv.put(`lang:${user.id}`, lang);
      const sl = await trU(user);
      const pending = (await kv.get(`pending:${user.id}`)) || [];
      const bound = [];
      for (const c of pending) bound.push(await bindChannel(c, user, path));
      const offers = await moveOffers(user, path);
      await kv.put(`code:${arg}`, { path, lang: lang || null, usedBy: user.id }, { ttl: CODE_TTL });
      await send([notice(user.id, sl.linked(g.title), { reply_markup: { inline_keyboard: [[{ text: sl.addBtn, url: await addToChannelUrl() }]] } }), ...bound, ...offers]);
      // The pending list is still needed by a retry until the commit; after it, the branch above finishes this.
      if (pending.length) await kv.del(`pending:${user.id}`);
      return;
    }
    if (cmd === "/language") return say(user.id, CHOOSE_LANG, { reply_markup: LANG_BUTTONS });
    if (cmd === "/status") {
      const path = await kv.get(`user:${user.id}`);
      const ids = path ? (await kv.get(`gchans:${path}`)) || [] : [];
      const names = await Promise.all(ids.map(async (id) => (await kv.get(`chan:${id}`))?.title || id));
      return say(user.id, s.status(names.map((n) => `• ${n}`)));
    }
    if (cmd === "/start" || cmd === "/app") {
      const rows = [...(deps.webAppUrl ? [[{ text: s.openApp, web_app: { url: deps.webAppUrl } }]] : []), ...(cmd === "/start" ? LANG_BUTTONS.inline_keyboard : [])];
      return say(user.id, cmd === "/start" ? `${s.hello}\n\n${CHOOSE_LANG}` : s.openApp, { reply_markup: { inline_keyboard: rows } });
    }
    return say(user.id, s.help);
  }

  /** Mini App path: the caller verified initData, so no /start code round trip is needed. */
  async function linkUser(user, path) {
    await glossary(path); // must exist
    await kv.put(`user:${user.id}`, path);
    const pending = (await kv.get(`pending:${user.id}`)) || [];
    const bound = [];
    for (const c of pending) bound.push(await bindChannel(c, user, path));
    if (pending.length) await kv.del(`pending:${user.id}`);
    await send([...bound, ...(await moveOffers(user, path))]);
    return { add_to_channel_url: await addToChannelUrl(), bot_username: await deps.username() };
  }

  async function status(path) {
    const ids = (await kv.get(`gchans:${path}`)) || [];
    return Promise.all(ids.map(async (id) => ({ id, title: (await kv.get(`chan:${id}`))?.title || id })));
  }

  /**
   * Catches glossary edits made elsewhere. One run may not reach every glossary (each check is a
   * Telegraph fetch, and a changed glossary spends requests on edits), so the next run starts
   * right after the last glossary this one reached (`cron:next`). That key is written only when a
   * run stops early, at most once per run.
   */
  async function cron() {
    const budget = { requests: MAX_REQUESTS_PER_RUN };
    const keys = await kv.list("gchans:"); // sorted
    if (!keys.length) return;
    const saved = await kv.get("cron:next");
    const start = saved ? Math.max(0, keys.findIndex((k) => k >= saved)) : 0; // a removed key: the one after it
    let i = 0;
    for (; i < keys.length && budget.requests > 0; i++) {
      const key = keys[(start + i) % keys.length];
      try { await resync(key.slice("gchans:".length), budget); } catch (e) { console.error("resync", key, e); }
    }
    if (i < keys.length) {
      const next = keys[(start + i) % keys.length];
      if (next !== saved) await kv.put("cron:next", next);
    }
  }

  return { handleUpdate, connectCode, linkUser, status, resync, cron, glossary, username: deps.username };
}
