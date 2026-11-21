// Cloudflare Worker entry for the channel auto-link bot.
//
// Bindings (wrangler.toml / secrets):
//   KV               KV namespace
//   BOT_TOKEN        secret: token from @BotFather
//   WEBHOOK_SECRET   secret: random string, verifies requests come from Telegram
//   BOT_USERNAME     var: the bot's @username (without @)
//
// Routes:
//   POST /telegram             Telegram webhook
//   GET  /setup?secret=...     registers the webhook + commands (run once after deploy)
//   POST /api/connect          {index_path} -> {start_url}   (used by the web app)
//   GET  /api/status?index=... -> {channels}
//   POST /api/changed          {index_path}  glossary was edited: update old posts now
// Cron: re-applies glossary changes made elsewhere (CLI, agents, telegra.ph).

import { createBot } from "./handler.js";

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

function bot(env) {
  return createBot({
    kv: kvAdapter(env.KV),
    botUsername: env.BOT_USERNAME,
    async tg(method, params) {
      const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(params),
      });
      const data = await r.json();
      if (!data.ok) throw new Error(data.description || `${method} failed`);
      return data.result;
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
    const b = bot(env);

    if (url.pathname === "/telegram" && request.method === "POST") {
      if (request.headers.get("x-telegram-bot-api-secret-token") !== env.WEBHOOK_SECRET) return new Response("forbidden", { status: 403 });
      const update = await request.json();
      // Answer Telegram right away; do the work in the background.
      ctx.waitUntil(b.handleUpdate(update).catch((e) => console.error("update", e)));
      return new Response("ok");
    }

    if (url.pathname === "/setup") {
      if (url.searchParams.get("secret") !== env.WEBHOOK_SECRET) return new Response("forbidden", { status: 403 });
      const hook = `${url.origin}/telegram`;
      const tg = (m, p) => fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${m}`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(p),
      }).then((r) => r.json());
      const results = {
        webhook: await tg("setWebhook", {
          url: hook,
          secret_token: env.WEBHOOK_SECRET,
          allowed_updates: ["message", "channel_post", "edited_channel_post", "my_chat_member"],
        }),
        commands: await tg("setMyCommands", { commands: [{ command: "status", description: "Connected channels" }] }),
        me: await tg("getMe", {}),
      };
      return json(results);
    }

    if (url.pathname === "/api/connect" && request.method === "POST") {
      const { index_path } = await request.json().catch(() => ({}));
      if (!validPath(index_path)) return json({ error: "index_path required" }, 400);
      try { await b.glossary(index_path, true); } catch { return json({ error: "glossary not found" }, 404); }
      return json(await b.connectCode(index_path));
    }

    if (url.pathname === "/api/status") {
      const path = url.searchParams.get("index");
      if (!validPath(path)) return json({ error: "index required" }, 400);
      return json({ bot_username: env.BOT_USERNAME, channels: await b.status(path) });
    }

    if (url.pathname === "/api/changed" && request.method === "POST") {
      const { index_path } = await request.json().catch(() => ({}));
      if (!validPath(index_path)) return json({ error: "index_path required" }, 400);
      ctx.waitUntil(b.resync(index_path).catch((e) => console.error("resync", e)));
      return json({ ok: true });
    }

    return new Response("Telegraph Glossary bot", { headers: CORS });
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(bot(env).cron());
  },
};
