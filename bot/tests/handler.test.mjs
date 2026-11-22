import { test } from "node:test";
import assert from "node:assert/strict";
import { createBot } from "../src/handler.js";
import { buildIndex } from "../../web/core/glossary.js";

function setup() {
  const store = new Map();
  const kv = {
    get: async (k) => (store.has(k) ? structuredClone(store.get(k)) : null),
    put: async (k, v) => { store.set(k, structuredClone(v)); },
    del: async (k) => { store.delete(k); },
    list: async (p) => [...store.keys()].filter((k) => k.startsWith(p)),
  };
  const calls = [];
  let fail = false;
  const fetched = [];
  let terms = [{ term: "API", aliases: [], path: "API-1" }, { term: "פייתון", aliases: ["Python"], path: "Py-1" }];
  const bot = createBot({
    kv,
    username: async () => "GlossBot",
    tg: async (method, params) => {
      calls.push({ method, params });
      if (fail && method.startsWith("edit")) throw new Error("Bad Gateway");
      return { message_id: 1 };
    },
    getPage: async (path) => { fetched.push(path); return { title: "My glossary", content: buildIndex(terms, "My glossary") }; },
  });
  return { bot, calls, kv, store, fetched, setTerms: (t) => { terms = t; }, failEdits: (on) => { fail = on; } };
}

const user = { id: 7, language_code: "en", first_name: "Dana" };
const channel = { id: -1001, type: "channel", title: "Dev Notes" };
const edits = (calls) => calls.filter((c) => c.method.startsWith("edit"));
const links = (entities) => entities.filter((e) => e.type === "text_link").map((e) => [e.offset, e.length, e.url]);

async function connectAndAdd(t) {
  const { code } = await t.bot.connectCode("My-glossary-11-21");
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } });
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator", can_edit_messages: true } } });
}

test("connect flow binds the channel and confirms to the owner", async () => {
  const t = setup();
  await connectAndAdd(t);
  assert.deepEqual(await t.kv.get("gchans:My-glossary-11-21"), ["-1001"]);
  const dms = t.calls.filter((c) => c.method === "sendMessage").map((c) => c.params.text);
  assert.match(dms[0], /connected/);
  assert.equal(t.calls[0].params.reply_markup.inline_keyboard[0][0].url, "https://t.me/GlossBot?startchannel&admin=edit_messages");
  assert.match(dms[1], /Dev Notes/);
});

test("new channel post gets links, author formatting kept", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  const bold = { type: "bold", offset: 0, length: 5 };
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 50, text: "Hello API and Python", entities: [bold] } });
  const [e] = edits(t.calls);
  assert.equal(e.method, "editMessageText");
  assert.equal(e.params.message_id, 50);
  assert.deepEqual(e.params.entities[0], bold);
  assert.deepEqual(links(e.params.entities), [[6, 3, "https://telegra.ph/API-1"], [14, 6, "https://telegra.ph/Py-1"]]);
  assert.deepEqual(e.params.link_preview_options, { is_disabled: true });
});

test("captions are edited with caption entities", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 51, caption: "photo of API", photo: [{}] } });
  const [e] = edits(t.calls);
  assert.equal(e.method, "editMessageCaption");
  assert.equal(e.params.reply_markup, undefined);
  assert.deepEqual(links(e.params.caption_entities), [[9, 3, "https://telegra.ph/API-1"]]);
});

// Real Telegram: a post carrying another bot's inline keyboard can't be edited by this bot
// (MESSAGE_ID_INVALID, with or without reply_markup), so it must not be touched or remembered.
test("posts with inline buttons are left alone; forwarding one explains why", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  const reply_markup = { inline_keyboard: [[{ text: "x", url: "https://x.y" }]] };
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 53, text: "API docs", reply_markup } });
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 54, caption: "photo of API", photo: [{}], reply_markup } });
  assert.equal(edits(t.calls).length, 0);
  assert.equal(await t.kv.get("post:-1001:53"), null);
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: "API docs", reply_markup,
    forward_origin: { type: "channel", chat: channel, message_id: 53 } } });
  assert.equal(edits(t.calls).length, 0);
  assert.match(t.calls.at(-1).params.text, /buttons/);
});

test("our own edit echoing back does not loop", async () => {
  const t = setup();
  await connectAndAdd(t);
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 52, text: "API" } });
  const applied = edits(t.calls)[0].params.entities;
  t.calls.length = 0;
  await t.bot.handleUpdate({ edited_channel_post: { chat: channel, message_id: 52, text: "API", entities: applied } });
  assert.equal(edits(t.calls).length, 0);
});

test("glossary change updates earlier posts; removed terms are unlinked", async () => {
  const t = setup();
  await connectAndAdd(t);
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 60, text: "API meets GraphQL" } });
  await t.bot.resync("My-glossary-11-21"); // records current version
  t.calls.length = 0;
  t.setTerms([{ term: "GraphQL", aliases: [], path: "GQL-1" }]); // API removed, GraphQL added
  const n = await t.bot.resync("My-glossary-11-21");
  assert.equal(n, 1);
  assert.deepEqual(links(edits(t.calls)[0].params.entities), [[10, 7, "https://telegra.ph/GQL-1"]]);
  t.calls.length = 0;
  assert.equal(await t.bot.resync("My-glossary-11-21"), 0); // nothing new
  assert.equal(edits(t.calls).length, 0);
});

test("forwarding an old post to the bot links the original", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: "old Python post",
    forward_origin: { type: "channel", chat: channel, message_id: 9 } } });
  const [e] = edits(t.calls);
  assert.equal(e.params.chat_id, -1001);
  assert.equal(e.params.message_id, 9);
  assert.match(t.calls.at(-1).params.text, /Updated \(1 terms\)/);
});

test("strangers cannot edit someone else's channel by forwarding", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  await t.bot.handleUpdate({ message: { chat: { id: 8, type: "private" }, from: { id: 8 }, text: "API",
    forward_origin: { type: "channel", chat: channel, message_id: 9 } } });
  assert.equal(edits(t.calls).length, 0);
});

test("connecting from the web app uses its language, unless the user already picked one", async () => {
  const t = setup();
  const { code } = await t.bot.connectCode("My-glossary-11-21", "he");
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } });
  assert.match(t.calls.at(-1).params.text, /מחובר/);
  assert.equal(t.calls.at(-1).params.reply_markup.inline_keyboard[0][0].text, "➕ הוספה לערוץ");
  assert.equal(await t.kv.get("lang:7"), "he");

  await t.kv.put("lang:8", "en");
  const again = await t.bot.connectCode("My-glossary-11-21", "he");
  await t.bot.handleUpdate({ message: { chat: { id: 8, type: "private" }, from: { id: 8, language_code: "he" }, text: `/start ${again.code}` } });
  assert.match(t.calls.at(-1).params.text, /connected/);
});

test("channel added before /start is bound once the user connects", async () => {
  const t = setup();
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator" } } });
  assert.equal(await t.kv.get("chan:-1001"), null);
  const { code } = await t.bot.connectCode("My-glossary-11-21");
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } });
  assert.equal((await t.kv.get("chan:-1001")).path, "My-glossary-11-21");
});

test("removing the bot unbinds the channel", async () => {
  const t = setup();
  await connectAndAdd(t);
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } });
  assert.equal(await t.kv.get("chan:-1001"), null);
  assert.equal(await t.kv.get("gchans:My-glossary-11-21"), null);
});

test("unconnected channels are ignored", async () => {
  const t = setup();
  await t.bot.handleUpdate({ channel_post: { chat: { id: -5, type: "channel" }, message_id: 1, text: "API" } });
  assert.equal(edits(t.calls).length, 0);
});

test("language buttons: /start offers them, a choice overrides the Telegram app language", async () => {
  const t = setup();
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: "/start" } });
  const start = t.calls.at(-1).params;
  assert.match(start.text, /Choose a language/);
  assert.deepEqual(start.reply_markup.inline_keyboard[0].map((b) => b.callback_data), ["lang:he", "lang:en"]);

  t.calls.length = 0;
  await t.bot.handleUpdate({ callback_query: { id: "q1", from: user, data: "lang:he", message: { message_id: 3, chat: { id: 7 } } } });
  assert.equal(t.calls[0].method, "answerCallbackQuery");
  assert.match(t.calls[1].params.text, /בעברית/);

  // user's Telegram app is English, but they picked Hebrew
  t.calls.length = 0;
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: "/status" } });
  assert.match(t.calls.at(-1).params.text, /אין ערוצים מחוברים/);

  t.calls.length = 0;
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: "/language" } });
  assert.ok(t.calls.at(-1).params.reply_markup.inline_keyboard);
});

test("Mini App: initData signature is verified; linkUser binds without /start", async () => {
  const { verifyInitData } = await import("../src/index.js");
  const token = "123:secret";
  const enc = new TextEncoder();
  const hmac = async (key, data) => new Uint8Array(await crypto.subtle.sign("HMAC",
    await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]), enc.encode(data)));
  const make = async (fields) => {
    const p = new URLSearchParams(fields);
    const check = [...p.entries()].map(([k, v]) => `${k}=${v}`).sort().join("\n");
    const sig = [...(await hmac(await hmac(enc.encode("WebAppData"), token), check))].map((b) => b.toString(16).padStart(2, "0")).join("");
    p.set("hash", sig);
    return p.toString();
  };
  const now = String(Math.floor(Date.now() / 1000));
  const good = await make({ auth_date: now, user: JSON.stringify({ id: 7, language_code: "he" }), query_id: "x" });
  assert.equal((await verifyInitData(good, token)).id, 7);
  assert.equal(await verifyInitData(good.replace("id%22%3A7", "id%22%3A8"), token), null); // tampered
  assert.equal(await verifyInitData(good, "999:other"), null); // other bot
  const old = await make({ auth_date: "1000", user: JSON.stringify({ id: 7 }) });
  assert.equal(await verifyInitData(old, token), null); // expired

  const t = setup();
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator" } } });
  const r = await t.bot.linkUser(user, "My-glossary-11-21");
  assert.equal(r.add_to_channel_url, "https://t.me/GlossBot?startchannel&admin=edit_messages");
  assert.equal((await t.kv.get("chan:-1001")).path, "My-glossary-11-21"); // pending channel bound
});

test("/app and /start offer the Mini App button when configured", async () => {
  const store = new Map();
  const kv = { get: async (k) => store.get(k) ?? null, put: async (k, v) => store.set(k, v), del: async (k) => store.delete(k), list: async () => [] };
  const calls = [];
  const bot = createBot({ kv, username: async () => "GlossBot", webAppUrl: "https://example.org/app/",
    tg: async (method, params) => { calls.push({ method, params }); return {}; }, getPage: async () => ({ title: "G", content: [] }) });
  await bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: "/app" } });
  assert.deepEqual(calls.at(-1).params.reply_markup.inline_keyboard[0][0].web_app, { url: "https://example.org/app/" });
});

test("a channel connected to another glossary is offered and moved on connect (no my_chat_member comes)", async () => {
  const t = setup();
  await connectAndAdd(t); // Dev Notes -> My-glossary-11-21
  t.calls.length = 0;
  // The user connects a second glossary. The bot is already an admin in Dev Notes, so Telegram sends nothing.
  await t.bot.linkUser(user, "Second-11-22");
  const offer = t.calls.find((c) => c.method === "sendMessage");
  assert.match(offer.params.text, /Dev Notes/);
  const data = offer.params.reply_markup.inline_keyboard[0][0].callback_data;
  assert.equal(data, "move:-1001");
  // Someone else pressing the button changes nothing.
  await t.bot.handleUpdate({ callback_query: { id: "q0", data, from: { id: 99 }, message: { chat: { id: 99 }, message_id: 4 } } });
  assert.equal((await t.kv.get("chan:-1001")).path, "My-glossary-11-21");
  await t.bot.handleUpdate({ callback_query: { id: "q1", data, from: user, message: { chat: { id: 7 }, message_id: 5 } } });
  assert.equal((await t.kv.get("chan:-1001")).path, "Second-11-22");
  assert.deepEqual(await t.kv.get("gchans:Second-11-22"), ["-1001"]);
  assert.equal(await t.kv.get("gchans:My-glossary-11-21"), null);
  assert.ok(t.calls.some((c) => c.method === "sendMessage" && /Dev Notes/.test(c.params.text) && c.params.chat_id === 7 && !c.params.reply_markup));
  // Connecting the same glossary again offers nothing.
  t.calls.length = 0;
  await t.bot.linkUser(user, "Second-11-22");
  assert.equal(t.calls.filter((c) => c.method === "sendMessage").length, 0);
});

test("removing the bot from a channel forgets it for move offers", async () => {
  const t = setup();
  await connectAndAdd(t);
  assert.deepEqual(await t.kv.get("uchans:7"), ["-1001"]);
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } });
  assert.equal(await t.kv.get("uchans:7"), null);
});

test("resync writes KV only on real change (anyone can trigger it through /api/changed)", async () => {
  const t = setup();
  const writes = [];
  const put = t.kv.put;
  t.kv.put = async (k, v) => { writes.push(k); return put(k, v); };
  // A page no channel uses: nothing to do and nothing written, whatever page is named.
  assert.equal(await t.bot.resync("Some-other-page-01-01"), 0);
  assert.deepEqual(writes, []);
  await connectAndAdd(t);
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 70, text: "API notes" } });
  await t.bot.resync("My-glossary-11-21");
  writes.length = 0;
  // Unchanged glossary: reads only.
  assert.equal(await t.bot.resync("My-glossary-11-21"), 0);
  assert.deepEqual(writes, []);
  // The glossary changed but the edit keeps failing (e.g. Telegram is down): retried on every
  // trigger, and nothing is rewritten until something actually changes.
  t.setTerms([{ term: "notes", aliases: [], path: "Notes-1" }]);
  t.failEdits(true);
  await t.bot.resync("My-glossary-11-21");
  await t.bot.resync("My-glossary-11-21");
  assert.deepEqual(writes, []);
  t.failEdits(false);
  assert.equal(await t.bot.resync("My-glossary-11-21"), 1);
  assert.deepEqual(writes.sort(), ["gver:My-glossary-11-21", "post:-1001:70", "posts:-1001"]);
});

test("resync budget bounds external requests, failed ones included", async () => {
  const t = setup();
  await connectAndAdd(t);
  const other = { id: -1002, type: "channel", title: "Second" };
  await t.bot.handleUpdate({ my_chat_member: { chat: other, from: user, new_chat_member: { status: "administrator", can_edit_messages: true } } });
  for (let i = 0; i < 5; i++) {
    await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 100 + i, text: "API" } });
    await t.bot.handleUpdate({ channel_post: { chat: other, message_id: 200 + i, text: "API" } });
  }
  await t.bot.resync("My-glossary-11-21");
  t.setTerms([{ term: "API", aliases: [], path: "API-2" }]);
  t.calls.length = 0;
  t.failEdits(true); // transient failure: one attempt, then the run stops (other channel included)
  await t.bot.resync("My-glossary-11-21", { requests: 4 }); // 1 Telegraph fetch + 3 Telegram attempts
  assert.equal(edits(t.calls).length, 1);
  t.failEdits(false);
  t.calls.length = 0;
  await t.bot.resync("My-glossary-11-21", { requests: 4 });
  assert.equal(edits(t.calls).length, 3);
  t.calls.length = 0;
  assert.equal(await t.bot.resync("My-glossary-11-21"), 7); // the rest, then done
  assert.equal(await t.bot.resync("My-glossary-11-21"), 0);
});

test("cron stays within the request budget and reaches every glossary in turn, even with busy ones", async () => {
  const t = setup();
  const paths = Array.from({ length: 100 }, (_, i) => `G-${String(i).padStart(3, "0")}`);
  for (const [i, p] of paths.entries()) {
    const chat = String(-2000 - i);
    await t.kv.put(`gchans:${p}`, [chat]);
    if (i % 45) continue; // G-000, G-045, G-090: 300 posts each waiting for the new glossary
    await t.kv.put(`chan:${chat}`, { path: p, mode: "first" });
    await t.kv.put(`posts:${chat}`, Array.from({ length: 300 }, (_, n) => ({ id: n, v: "old" })));
    for (let n = 0; n < 300; n++) await t.kv.put(`post:${chat}:${n}`, { text: "API", entities: [], paths: [] });
  }
  const seen = new Set();
  let cursorWrites = 0;
  const put = t.kv.put;
  t.kv.put = async (k, v) => { cursorWrites += k === "cron:next"; return put(k, v); };
  for (let run = 0; run < 5; run++) {
    t.fetched.length = 0;
    t.calls.length = 0;
    const before = cursorWrites;
    await t.bot.cron();
    assert.ok(t.fetched.length + t.calls.length <= 45, `run ${run}: ${t.fetched.length + t.calls.length} requests`);
    assert.ok(cursorWrites - before <= 1);
    t.fetched.forEach((p) => seen.add(p));
  }
  assert.equal(seen.size, paths.length);
});

test("cron with few glossaries checks them all and stores no cursor", async () => {
  const t = setup();
  await connectAndAdd(t);
  await t.bot.cron();
  assert.equal(await t.kv.get("cron:next"), null);
});

test("a retried /start or channel removal finishes the job without repeating a message", async () => {
  const t = setup();
  const dms = () => t.calls.filter((c) => c.method === "sendMessage").map((c) => c.params.text);
  const { code } = await t.bot.connectCode("My-glossary-11-21");
  const start = { message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } };
  const { put, del } = t.kv;
  t.kv.put = async () => { throw new Error("KV unavailable"); };
  await assert.rejects(t.bot.handleUpdate(start));
  t.kv.put = put;
  await t.bot.handleUpdate(start); // Telegram's retry: the code still works
  assert.equal(dms().length, 1);
  assert.match(dms()[0], /My glossary/);
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator", can_edit_messages: true } } });
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 80, text: "API" } });
  const leave = { my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } };
  let n = 0;
  t.kv.del = async (k) => { if (k.startsWith("posts:") && n++ === 0) throw new Error("KV unavailable"); return del(k); };
  await assert.rejects(t.bot.handleUpdate(leave));
  await t.bot.handleUpdate(leave); // the retry finds the binding and finishes
  for (const k of ["chan:-1001", "posts:-1001", "post:-1001:80", "uchans:7"]) assert.equal(await t.kv.get(k), null, k);
  assert.equal(dms().filter((m) => /removed/.test(m)).length, 1);
});

test("/start: a failure in its last step sends nothing; the retry sends every message once, a further retry none", async () => {
  const t = setup();
  const dms = () => t.calls.filter((c) => c.method === "sendMessage").map((c) => c.params.text);
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator", can_edit_messages: true } } });
  const { code } = await t.bot.connectCode("My-glossary-11-21");
  t.calls.length = 0;
  const start = { message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } };
  const { put, del } = t.kv;
  // Using up the code is the last step: it fails once (the webhook answers 500).
  let failed = false;
  const failCodeOnce = (fn) => async (k, ...a) => { if (k.startsWith("code:") && !failed) { failed = true; throw new Error("KV unavailable"); } return fn(k, ...a); };
  t.kv.put = failCodeOnce(put);
  t.kv.del = failCodeOnce(del);
  await assert.rejects(t.bot.handleUpdate(start));
  assert.deepEqual(dms(), []);
  t.kv.put = put;
  t.kv.del = del;
  await t.bot.handleUpdate(start); // Telegram's retry
  await t.bot.handleUpdate(start); // and another delivery of the same update
  const sent = dms();
  assert.equal(sent.filter((m) => /Glossary “My glossary” connected/.test(m)).length, 1, sent.join("\n"));
  assert.equal(sent.filter((m) => /Channel “Dev Notes” now uses/.test(m)).length, 1, sent.join("\n"));
  assert.equal(sent.length, 2, sent.join("\n"));
  assert.equal((await t.kv.get("chan:-1001")).path, "My-glossary-11-21");
  assert.equal(await t.kv.get("pending:7"), null);
  // Someone else with the same (used) link is told it no longer works.
  await t.bot.handleUpdate({ message: { chat: { id: 8, type: "private" }, from: { id: 8, language_code: "en" }, text: `/start ${code}` } });
  assert.match(dms().at(-1), /expired/);
  assert.equal(await t.kv.get("user:8"), null);
});

test("removing the bot: a channel post handled during the removal leaves no post text behind", async () => {
  const t = setup();
  await connectAndAdd(t);
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 80, text: "API" } });
  const leave = { my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } };
  // The removal fails after its first step (Telegram will retry it); a post arrives in between.
  const { del } = t.kv;
  let n = 0;
  t.kv.del = async (k) => { if (k.startsWith("post") && n++ === 0) throw new Error("KV unavailable"); return del(k); };
  await assert.rejects(t.bot.handleUpdate(leave));
  t.kv.del = del;
  t.calls.length = 0;
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 81, text: "API again" } });
  assert.equal(edits(t.calls).length, 0); // the channel is being removed: not edited, not stored
  await t.bot.handleUpdate(leave); // the retry finishes the removal
  assert.deepEqual([...t.store.keys()].filter((k) => k.includes("-1001")), []);
});

test("bot re-added before a failed removal finished: the old records are deleted and the channel works again", async () => {
  const t = setup();
  await connectAndAdd(t);
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 80, text: "API" } });
  const { del } = t.kv;
  t.kv.del = async (k) => { if (k.startsWith("post")) throw new Error("KV unavailable"); return del(k); };
  await assert.rejects(t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } }));
  t.kv.del = del;
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator", can_edit_messages: true } } });
  assert.equal(await t.kv.get("post:-1001:80"), null);
  assert.equal((await t.kv.get("chan:-1001")).removing, undefined);
  assert.deepEqual(await t.kv.get("gchans:My-glossary-11-21"), ["-1001"]);
  t.calls.length = 0;
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 81, text: "API" } });
  assert.equal(edits(t.calls).length, 1);
});

test("removing the bot: a channel post already in flight does not store its text after the removal", async () => {
  const t = setup();
  await connectAndAdd(t);
  const leave = { my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } };
  // The post's edit is slow; the removal runs while it is in flight.
  const slow = createBot({
    kv: t.kv, username: async () => "GlossBot",
    tg: async (m) => { if (m.startsWith("edit")) await t.bot.handleUpdate(leave); return {}; },
    getPage: async () => ({ title: "My glossary", content: buildIndex([{ term: "API", aliases: [], path: "API-1" }], "My glossary") }),
  });
  await slow.handleUpdate({ channel_post: { chat: channel, message_id: 82, text: "Hello API" } });
  assert.deepEqual([...t.store.keys()].filter((k) => k.includes("-1001")), []);
});

test("removing the bot deletes the channel's remembered post texts; moving it keeps them", async () => {
  const t = setup();
  await connectAndAdd(t);
  for (const id of [50, 51]) await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: id, text: "Hello API" } });
  assert.equal((await t.kv.get("posts:-1001")).length, 2);
  // moving to another glossary keeps the posts
  const { code } = await t.bot.connectCode("Other-glossary-11-22");
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } });
  await t.bot.handleUpdate({ callback_query: { id: "q", from: user, data: "move:-1001" } });
  assert.equal((await t.kv.get("chan:-1001")).path, "Other-glossary-11-22");
  assert.equal((await t.kv.get("posts:-1001")).length, 2);
  assert.ok(await t.kv.get("post:-1001:50"));
  // removal deletes them
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "left" } } });
  assert.deepEqual([...t.store.keys()].filter((k) => k.includes("-1001")), []);
});

test("bot added without the edit right: warns, binds, but does not claim the channel works", async () => {
  const t = setup();
  const { code } = await t.bot.connectCode("My-glossary-11-21");
  await t.bot.handleUpdate({ message: { chat: { id: 7, type: "private" }, from: user, text: `/start ${code}` } });
  t.calls.length = 0;
  await t.bot.handleUpdate({ my_chat_member: { chat: channel, from: user, new_chat_member: { status: "administrator", can_edit_messages: false } } });
  assert.equal((await t.kv.get("chan:-1001")).path, "My-glossary-11-21");
  const dms = t.calls.filter((c) => c.method === "sendMessage").map((c) => c.params.text);
  assert.equal(dms.length, 1);
  assert.match(dms[0], /can't edit messages/);
});

test("the same channel_post delivered twice (webhook retry) edits once and is remembered once", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  const post = { chat: channel, message_id: 50, text: "Hello API" };
  await t.bot.handleUpdate({ channel_post: post });
  assert.equal(edits(t.calls).length, 1);
  // Telegram redelivers the original (no links in it): the edit repeats identically, Telegram says "not modified"
  t.calls.length = 0;
  await t.bot.handleUpdate({ channel_post: post });
  const [e] = edits(t.calls);
  assert.equal(links(e.params.entities).length, 1);
  assert.equal((await t.kv.get("posts:-1001")).length, 1);
});

test("a post the bot can never edit does not fail the update (no endless webhook retries); transient errors do", async () => {
  const t = setup();
  await connectAndAdd(t);
  const bad = createBot({
    kv: t.kv, username: async () => "GlossBot",
    tg: async (m) => { if (m.startsWith("edit")) throw new Error("Bad Request: not enough rights to edit the message"); return {}; },
    getPage: async () => ({ title: "My glossary", content: buildIndex([{ term: "API", aliases: [], path: "API-1" }], "My glossary") }),
  });
  await bad.handleUpdate({ channel_post: { chat: channel, message_id: 60, text: "Hello API" } });
  t.failEdits(true);
  await assert.rejects(t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 61, text: "Hello API" } }), /Bad Gateway/);
});
