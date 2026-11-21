# Channel auto-link bot

Users post in their channel as usual. The bot, a channel admin with the "edit messages" right,
edits each post and adds glossary links as message entities. The author's formatting, buttons
and link-preview setting stay as they were. When the glossary changes, the bot re-applies it to
the posts it remembers (the last 300 per channel). Older posts can be forwarded to the bot, and it
updates the originals.

The bot never sees anyone's Telegraph key. Glossaries are public pages, so all it stores is
*which channel uses which glossary*.

## Deploy

This is automatic from GitHub Actions (`.github/workflows/deploy.yml`) once the repo has the
secrets `BOT_TOKEN` and `CLOUDFLARE_API_TOKEN`; see the main README. On each push to `main`, the workflow:

1. finds or creates the KV namespace `telegraph-glossary-bot-KV`
2. deploys the Worker with `BOT_TOKEN` as a secret
3. calls `<worker>/setup`, which points the bot's webhook at the Worker and sets its commands
4. writes the Worker URL into the site's `config.json`, so the site shows the Channel feature

Only `BOT_TOKEN` is needed: the webhook secret is derived from it. `/setup` is idempotent and safe
to call by anyone, because it can only point the bot at this Worker.

Manual deploy: `cd bot && npm ci && npx wrangler deploy` (KV is provisioned automatically),
`npx wrangler secret put BOT_TOKEN`, then open `<worker-url>/setup`.

## Routes

| | |
|---|---|
| `POST /telegram` | webhook (checks `X-Telegram-Bot-Api-Secret-Token`) |
| `GET /setup` | registers the webhook and commands (`/status`, `/language`) |
| `GET /api/info` | `{bot_username}` |
| `POST /api/connect` | `{index_path}` → one-time `start_url` for the user |
| `GET /api/status?index=` | connected channels |
| `POST /api/changed` | `{index_path}`: re-apply the glossary to remembered posts now |
| cron `*/15` | catches glossary edits made elsewhere |

## Limits

* The bot talks Hebrew or English: it follows the Telegram app language until the user picks one (buttons on Start, or `/language`).
* Channels only. In groups, bots cannot edit other people's messages.
* Bots can't read channel history, so posts from before the bot joined are updated only when forwarded.
* Free plan: about 1,000 KV writes a day (about 2 per new post) and 50 outgoing requests per
  invocation, so a glossary change updates up to 30 posts per run and the rest on the next run.
  The $5 Workers plan lifts both limits.

## Tests

`npm test` runs the flow tests (connect, post, caption and buttons, no loops, glossary changes,
forwarding, removal) with mocked Telegram and KV. `../e2e/run.sh` runs the real Worker locally
against a fake Telegram API, with the web app in a browser.
