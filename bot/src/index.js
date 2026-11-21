// Cloudflare Worker entry for the channel auto-link bot.
//
// Only one secret is needed: BOT_TOKEN (from @BotFather). The webhook secret is
// derived from it, so nothing else has to be configured.
//
// Routes:
//   POST /telegram             Telegram webhook (verified with the derived secret)
//   GET  /setup                (re)registers the webhook to this Worker. Idempotent and safe
//                              to call by anyone: it can only point the bot at itself.
//   GET  /api/info             {bot_username}
//   POST /api/connect          {index_path} -> {start_url}   (used by the web app)
//   GET  /api/status?index=... -> {channels}
//   POST /api/changed          {index_path}  glossary was edited: update old posts now
// Cron: re-applies glossary changes made elsewhere (CLI, agents, telegra.ph).

import { createBot } from "./handler.js";

const ALLOWED_UPDATES = ["message", "channel_post", "edited_channel_post", "my_chat_member", "callback_query"];

function kvAdapter(ns) {
  return {
    get: (k) => ns.get(k, "json"),
    put: (k, v, o = {}) => ns.put(k, JSON.stringify(v), o.ttl ? { expirationTtl: o.ttl } : {}),
    del: (k) => ns.delete(k),
    async list(prefix) {
      const keys = [];
      let cursor;
      do {
        const r = await ns.list({ prefix, cursor });
        keys.push(...r.keys.map((k) => k.name));
        cursor = r.list_complete ? null : r.cursor;
      } while (cursor);
      return keys;
    },
  };
}

async function webhookSecret(env) {
  if (env.WEBHOOK_SECRET) return env.WEBHOOK_SECRET;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`webhook:${env.BOT_TOKEN}`));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 48);
}

function telegram(env) {
  const base = (env.TELEGRAM_API || "https://api.telegram.org").replace(/\/$/, "");
  return async (method, params = {}) => {
    const r = await fetch(`${base}/bot${env.BOT_TOKEN}/${method}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(params),
    });
    const data = await r.json();
    if (!data.ok) throw new Error(data.description || `${method} failed`);
    return data.result;
  };
}

let usernameCache = null;

function bot(env) {
  const tg = telegram(env);
  return createBot({
    kv: kvAdapter(env.KV),
    tg,
    async username() {
      if (!usernameCache) usernameCache = (await tg("getMe")).username;
      return usernameCache;
    },
    async getPage(path) {
      const r = await fetch(`https://api.telegra.ph/getPage?path=${encodeURIComponent(path)}&return_content=true`);
      const data = await r.json();
      if (!data.ok) throw new Error(data.error || "Telegraph error");
      return data.result;
    },
  });
}

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "content-type",
};
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...CORS } });

const validPath = (p) => typeof p === "string" && /^[^/?#\s]{1,256}$/.test(p);

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (!env.BOT_TOKEN) return json({ error: "BOT_TOKEN secret is not set" }, 500);
    const b = bot(env);

    if (url.pathname === "/telegram" && request.method === "POST") {
      if (request.headers.get("x-telegram-bot-api-secret-token") !== (await webhookSecret(env))) return new Response("forbidden", { status: 403 });
      const update = await request.json();
      ctx.waitUntil(b.handleUpdate(update).catch((e) => console.error("update", e)));
      return new Response("ok");
    }

    if (url.pathname === "/setup") {
      const tg = telegram(env);
      const me = await tg("getMe");
      await tg("setWebhook", { url: `${url.origin}/telegram`, secret_token: await webhookSecret(env), allowed_updates: ALLOWED_UPDATES });
      await tg("setMyCommands", { commands: [
        { command: "status", description: "Connected channels" },
        { command: "language", description: "Language: English / עברית" },
      ] });
      await tg("setMyCommands", { language_code: "he", commands: [
        { command: "status", description: "ערוצים מחוברים" },
        { command: "language", description: "שפה: עברית / English" },
      ] });
      return json({ ok: true, bot: me.username, webhook: `${url.origin}/telegram` });
    }

    if (url.pathname === "/api/info") return json({ bot_username: await b.username() });

    if (url.pathname === "/api/connect" && request.method === "POST") {
      const { index_path } = await request.json().catch(() => ({}));
      if (!validPath(index_path)) return json({ error: "index_path required" }, 400);
      try { await b.glossary(index_path, true); } catch { return json({ error: "glossary not found" }, 404); }
      return json(await b.connectCode(index_path));
    }

    if (url.pathname === "/api/status") {
      const path = url.searchParams.get("index");
      if (!validPath(path)) return json({ error: "index required" }, 400);
      return json({ channels: await b.status(path) });
    }

    if (url.pathname === "/api/changed" && request.method === "POST") {
      const { index_path } = await request.json().catch(() => ({}));
      if (!validPath(index_path)) return json({ error: "index_path required" }, 400);
      ctx.waitUntil(b.resync(index_path).catch((e) => console.error("resync", e)));
      return json({ ok: true });
    }

    return new Response("Telegraph Glossary bot. See https://github.com/NehoraiHadad/telegraph-glossary", { headers: CORS });
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(bot(env).cron());
  },
};
