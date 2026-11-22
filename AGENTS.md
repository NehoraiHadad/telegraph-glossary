# AGENTS.md

Guide for anyone, human or coding agent, who changes this repo. What the project does and how
to use it: [README.md](README.md). Storage format: [docs/FORMAT.md](docs/FORMAT.md). Bot setup
and routes: [bot/README.md](bot/README.md).

## Architecture

There is no server of our own that holds data. A glossary is a Telegraph account:

* one index page (the account's `author_url`) lists every term and its aliases;
* every term is its own page (title = term, content = definition).

The user's Telegraph access token is the only key to the glossary. It lives in the user's
browser (localStorage, plus Telegram CloudStorage inside the Mini App) or in their env/config
for the CLI and MCP server. It never reaches the bot.

| Part | Where | Runs on |
|---|---|---|
| Web app + Mini App | `web/` (static, no build step) | GitHub Pages |
| Shared JS core | `web/core/` (linker, entities, Markdown, Telegraph client, storage) | browser and bot |
| Channel bot | `bot/` | Cloudflare Worker + KV |
| CLI + MCP server | `src/telegraph_glossary/` | the user's machine |

The bot stores which channel uses which glossary (public index paths) and the text of each
channel's last 300 posts, because Telegram's edit methods need the full text. Removing the bot
from a channel deletes that channel's records. KV key prefixes are in `bot/src/handler.js`.

## Rules that the code does not show

* **Two implementations, one behavior.** These pairs must change together, in the same PR:

  | JS | Python |
  |---|---|
  | `web/core/linker.js` | `src/telegraph_glossary/linker.py` |
  | `web/core/glossary.js` | `src/telegraph_glossary/glossary.py` |
  | `web/core/markdown.js` | `src/telegraph_glossary/markdown.py` |

  Linker behavior is pinned by `spec/linker-cases.json`, which both test suites run. Add a case
  there for any linker change. The index format is in `docs/FORMAT.md`. Update it when you
  change the format, and keep old glossaries readable.
* **Index writes go through `updateIndex` / `update_index`.** Telegraph has no compare-and-swap,
  so a plain read-modify-write loses concurrent edits (web app plus an agent, two devices). The
  helper writes, waits for writes in flight, re-reads and re-applies. This narrows the window but
  cannot close it: a write slower than the wait can still drop a change. The function passed to
  it must be idempotent (filter or replace by path).
* **Telegraph pages cannot be deleted.** Removing a term drops it from the index first, then
  blanks its page, so a failed index write never loses a listed definition.
* **An index page holds at most 64 KB.** Writers check the new index size before writing any
  term page (`checkIndexFits` / `check_index_fits`).
* **The bot imports `web/core/`.** A change there is a bot change too: it triggers a Worker
  deploy and must pass `bot/tests`.
* **Strings are bilingual.** The web app strings are in `web/i18n.js`, and the bot's are in
  `T` in `bot/src/handler.js`. Add every new string in both `he` and `en`. Layout must work
  in both RTL and LTR.
* **MCP tool descriptions are the agent's docs.** Keep `INSTRUCTIONS` and the docstrings in
  `mcp_server.py` accurate. When tools change, also update the tool table in `README.md` and
  `web/llms.txt`.

## Secrets

* Never commit, print or log a Telegraph token or a bot token, including in tests, fixtures,
  CI output, PR text or agent transcripts. Read them from the environment.
* `BOT_TOKEN` is a Worker secret (`wrangler secret put`). The webhook secret is derived from it.
  GitHub holds no deploy secrets.
* IDs in `bot/wrangler.toml` (KV namespace) and the Worker URL in `web/config.json` are not secrets.

## Tests

```bash
node --test web/tests/*.mjs bot/tests/*.mjs   # JS units, shared spec, bot flows (mocked Telegram + KV)
pip install -e . pytest && pytest             # Python, same spec; agent tools use an in-memory Telegraph
e2e/run.sh                                    # site + local Worker + fake Telegram in a real browser
node e2e/screenshots.cjs                      # README screenshots (fake Telegraph and bot)
node e2e/guide.cjs                            # docs/GUIDE images, same fakes
```

CI (`.github/workflows/tests.yml`) runs the first two on every push. `e2e/run.sh` uses the real
Telegraph API (it creates a small test glossary) and needs Playwright with Chromium. Run it
before merging changes to the web app flow or to the bot.

## Deploy

Merging to `main` deploys both:

* `web/` is published to GitHub Pages by `.github/workflows/deploy.yml`;
* `bot/` is deployed by Cloudflare Workers Builds (watch paths `bot/*`, `web/core/*`).

After a change to the bot's commands, menu button, `WEB_APP_URL` or Worker URL, open
`<worker-url>/setup` once.

## Workflow

* Branch from `main` and open a PR. CI must pass.
* Fix root causes. Don't add special cases that hide a symptom.
* Keep docs in English, short and plain.
