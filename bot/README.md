# Channel auto-link bot

Users post in their channel as usual. The bot, a channel admin with the "edit messages" right,
edits each post and adds glossary links as message entities. The author's formatting and
link-preview setting stay as they were. When the glossary changes, the bot re-applies it to
the posts it remembers (the last 300 per channel). Older posts can be forwarded to the bot, and it
updates the originals.

The bot never sees anyone's Telegraph key. Glossaries are public pages, so all it stores is
*which channel uses which glossary*.

The bot speaks Hebrew or English. Connecting from the web app sets the web app's language;
otherwise it follows the Telegram app language. The user can change it any time (buttons on
Start, or `/language`).

## Deploy

Cloudflare Workers Builds deploys the Worker on every push to `main` that touches the bot.
GitHub holds no Cloudflare or Telegram secrets.

One-time setup:

1. Create the KV namespace and put its id in `wrangler.toml` (the id is not a secret):
   `npx wrangler kv namespace create telegraph-glossary-bot-KV`
2. First deploy and the bot token (stored as a Worker secret, kept across deploys):
   `cd bot && npm ci && npx wrangler deploy`, then `npx wrangler secret put BOT_TOKEN`.
3. Open `<worker-url>/setup` once. It points the bot's webhook at the Worker and sets its
   commands. Run it again only if the Worker URL changes. It is idempotent and safe to call by
   anyone, because it can only point the bot at this Worker.
4. Put the Worker URL in `web/config.json` (`{"bot_api": "<worker-url>"}`). The site shows the
   Channel tab only when it is set, and the CLI and MCP server read it from the published site.
5. Cloudflare dashboard → the Worker → **Settings → Build** → connect this GitHub repo:

   | Setting | Value |
   |---|---|
   | Git branch (production) | `main` |
   | Enable Preview Builds | off |
   | Root directory | `bot` |
   | Build command | `npm ci && npm test` |
   | Deploy command | `npx wrangler deploy` (default) |
   | Build watch paths, include | `bot/*`, `web/core/*` (the bot imports shared code from `web/core/`) |

Only `BOT_TOKEN` is needed: the webhook secret is derived from it.

## Routes

| | |
|---|---|
| `POST /telegram` | webhook (checks `X-Telegram-Bot-Api-Secret-Token`) |
| `GET /setup` | registers the webhook and commands (`/status`, `/language`) |
| `GET /api/info` | `{bot_username}` |
| `POST /api/connect` | `{index_path, lang?}` → one-time `start_url` for the user |
| `GET /api/status?index=` | connected channels |
| `POST /api/changed` | `{index_path}`: re-apply the glossary to remembered posts now |
| cron `*/15` | catches glossary edits made elsewhere |

## Limits

* Channels only. In groups, bots cannot edit other people's messages.
* Posts with inline buttons are left as they are. The buttons come from another bot (a post
  scheduler, for example), and Telegram lets only that bot edit the post.
* Bots can't read channel history, so posts from before the bot joined are updated only when forwarded.
* Free plan: about 1,000 KV writes a day (about 2 per new post) and 50 outgoing requests per
  invocation, so a glossary change updates up to 30 posts per run and the rest on the next run.
  The $5 Workers plan lifts both limits.

## Tests

`npm test` runs the flow tests (connect, post, caption, posts with buttons, no loops, glossary changes,
forwarding, removal) with mocked Telegram and KV. `../e2e/run.sh` runs the real Worker locally
against a fake Telegram API, with the web app in a browser.
