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
  let terms = [{ term: "API", aliases: [], path: "API-1" }, { term: "פייתון", aliases: ["Python"], path: "Py-1" }];
  const bot = createBot({
    kv,
    username: async () => "GlossBot",
    tg: async (method, params) => { calls.push({ method, params }); return { message_id: 1 }; },
    getPage: async () => ({ title: "My glossary", content: buildIndex(terms, "My glossary") }),
  });
  return { bot, calls, kv, store, setTerms: (t) => { terms = t; } };
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

test("captions are edited with caption entities; buttons are kept", async () => {
  const t = setup();
  await connectAndAdd(t);
  t.calls.length = 0;
  const markup = { inline_keyboard: [[{ text: "x", url: "https://x.y" }]] };
  await t.bot.handleUpdate({ channel_post: { chat: channel, message_id: 51, caption: "photo of API", photo: [{}], reply_markup: markup } });
  const [e] = edits(t.calls);
  assert.equal(e.method, "editMessageCaption");
  assert.deepEqual(e.params.reply_markup, markup);
  assert.deepEqual(links(e.params.caption_entities), [[9, 3, "https://telegra.ph/API-1"]]);
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
