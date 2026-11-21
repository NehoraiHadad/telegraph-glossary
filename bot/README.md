# Channel auto-link bot

Users post in their channel as usual. The bot (a channel admin) edits each post and adds
glossary links as message entities, so the author's formatting, buttons and link-preview
setting stay as they were. When the glossary changes, the bot re-applies it to the posts it
remembers (the last 300 per channel). Older posts can be forwarded to the bot in a private
chat, and it updates the originals.

The bot never sees anyone's Telegraph key: glossaries are public pages, so it only stores
*which channel uses which glossary*.

Runs as a single Cloudflare Worker (free plan) with KV storage. One deployment serves all users.

## Deploy (one time, ~10 minutes)

1. **Create the bot:** in Telegram, open @BotFather, send `/newbot`, keep the token.
   Optional: `/setdescription`, `/setuserpic`.
2. **Configure:**
   ```bash
   cd bot
   npm install
   npx wrangler login
   npx wrangler kv namespace create KV      # paste the id into wrangler.toml
   ```
   In `wrangler.toml`, set `BOT_USERNAME`.
3. **Secrets:**
   ```bash
   npx wrangler secret put BOT_TOKEN        # the token from BotFather
   npx wrangler secret put WEBHOOK_SECRET   # any long random string
   ```
4. **Deploy and register the webhook:**
   ```bash
   npx wrangler deploy
   curl "https://telegraph-glossary-bot.<your-subdomain>.workers.dev/setup?secret=<WEBHOOK_SECRET>"
   ```
5. **Turn it on in the web app:** fill in `web/config.js` (`api` = the Worker URL,
   `username` = the bot's username) and push. Optionally set `TELEGRAPH_GLOSSARY_BOT_API` for the
   CLI/MCP, so their edits reach channels right away and not only on the 15-minute schedule.

## How a user connects

1. Web app → Settings → **Auto-link my channel** → *Connect a channel*.
2. Telegram opens the bot. They press **Start**, and the bot replies with an *Add to channel* button.
   That button pre-selects the "edit messages" admin right.
3. Done. The bot confirms in the private chat, and the web app shows the channel as connected.

## Limits and notes

* Channels only. In groups, bots cannot edit other people's messages.
* Telegram does not give bots access to channel history, so posts from before the bot joined
  are updated only when forwarded to it.
* Free-plan budgets: KV allows about 1,000 writes a day (about 2 per new post) and a Worker
  invocation allows 50 outgoing requests (so a glossary change updates up to 30 posts per run;
  the rest follow on the next scheduled run). For heavier use, the $5 Workers plan lifts both.
* `npm test` runs the flow tests with mocked Telegram and KV.
