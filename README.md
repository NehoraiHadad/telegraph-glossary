# Telegraph Glossary

**Write a Telegram post, and terms from your glossary become links to short explanation pages.**

Each term is a [Telegraph](https://telegra.ph) page, so explanations open instantly inside
Telegram (Instant View). Free, no sign-up, no server.

> כותבים פוסט, והמונחים מהמילון שלך הופכים לקישורים לדפי הסבר קצרים שנפתחים ישר בטלגרם.

## Ways to use it

| | For | How |
|---|---|---|
| **Channel auto-link** | everyone with a channel | connect once; links are added to every post automatically ([bot/](bot/)) |
| **Web app** | everyone | open **https://nehoraihadad.github.io/telegraph-glossary/** |
| **AI agents** | Claude Code, Codex, Antigravity, Cursor, Claude Desktop… | MCP server, see below |
| **CLI / Python** | scripts, automation | `telegraph-glossary` command, or `import telegraph_glossary` |

All three work on **the same glossary**. Copy your key from the web app's settings and use it anywhere.

## Web app

1. **Create a glossary.** Give it a name. A Telegraph account is created in the background.
2. **Add terms.** A term has a name, other forms to link (plural, English name, abbreviation)
   and a short explanation (Markdown).
3. **Write.** Terms are detected automatically, including Hebrew prefixes (`בפייתון`, `ל-API`).
   Click a detected term to turn its link off. Select a word in your text to add it as a new term.
4. **Send or copy.** *Copy* puts the text on the clipboard with its links (HTML + plain text).
   With your own bot (Settings → Send to Telegram, about 2 minutes with @BotFather), *Send* posts
   straight to your channel. The app finds the channels your bot was added to, so you never need
   to look up a chat ID.

Your **key** (the Telegraph access token) is kept in your browser only. Back it up from
Settings: download it, or copy a link that opens the glossary on another device.
Whoever has the key can edit the glossary.

## Channel auto-link

Settings → **Auto-link my channel** → press Start in the bot → add it to your channel as an admin.
From then on you simply post in Telegram: within seconds the bot edits the post and links every
glossary term, keeping your formatting. When you add or remove a term, earlier posts are updated
too. To update posts from before the bot joined, forward them to the bot.

The bot only knows which channel uses which glossary. It never gets your key.
Deployment instructions are in [bot/README.md](bot/README.md).

## Use it from AI agents

Requires [uv](https://docs.astral.sh/uv/). Replace `<KEY>` with your key (Settings → Your key in
the web app, or run `telegraph-glossary init` to create a glossary from the terminal).

**Claude Code**

```bash
claude mcp add telegraph-glossary -e TELEGRAPH_ACCESS_TOKEN=<KEY> -- \
  uvx --from git+https://github.com/NehoraiHadad/telegraph-glossary telegraph-glossary mcp
```

**Codex**

```bash
codex mcp add telegraph-glossary --env TELEGRAPH_ACCESS_TOKEN=<KEY> -- \
  uvx --from git+https://github.com/NehoraiHadad/telegraph-glossary telegraph-glossary mcp
```

**Anything else that speaks MCP** (Antigravity, Cursor, Claude Desktop, Gemini CLI…):

```json
{
  "mcpServers": {
    "telegraph-glossary": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/NehoraiHadad/telegraph-glossary", "telegraph-glossary", "mcp"],
      "env": {
        "TELEGRAPH_ACCESS_TOKEN": "<KEY>",
        "TELEGRAM_BOT_TOKEN": "optional, for send_to_telegram",
        "TELEGRAM_CHAT_ID": "optional default, e.g. @mychannel"
      }
    }
  }
}
```

Tools: `glossary_info`, `list_terms`, `get_term`, `add_term`, `update_term`, `remove_term`,
`link_text`, `send_to_telegram` (has `dry_run`).

Then just talk to the agent: *"Here's my post. Link the glossary terms, suggest definitions for
jargon that's missing, and send it to my channel."*

## CLI

```bash
pip install git+https://github.com/NehoraiHadad/telegraph-glossary   # or: uvx --from ... telegraph-glossary

telegraph-glossary init --title "My glossary"     # new glossary (or: login <KEY>)
tgg add API -a "APIs,ממשק תכנות" -d "**Application Programming Interface**"
tgg list
tgg link post.txt                  # Telegram HTML to stdout (--format markdown)
tgg telegram --bot-token 123:ABC --chat @mychannel
tgg chats                          # chats your bot has seen
tgg send post.txt --dry-run
```

Settings live in `~/.config/telegraph-glossary/config.json`. The environment variables
`TELEGRAPH_ACCESS_TOKEN`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` take precedence.

## How it's built

```
web/            static web app (no build step), deployed to GitHub Pages
  core/         linker, entity linking, Markdown <-> Telegraph nodes, storage. Plain ES modules.
bot/            channel auto-link bot (Cloudflare Worker), reuses web/core
src/telegraph_glossary/
                the same core in Python + CLI + MCP server
spec/           shared test cases both linkers must pass
docs/FORMAT.md  how a glossary is stored on Telegraph
legacy/         the previous Streamlit app (kept for reference)
```

Both Telegraph and the Telegram Bot API allow browser (CORS) requests, so the web app talks
to them directly. Nothing goes through a backend.

```bash
node --test web/tests/*.mjs bot/tests/*.mjs   # web core + bot
pip install -e . pytest && pytest
python -m http.server -d web    # run the web app locally
```

**Deploying the web app:** in the repo settings, set *Pages → Source* to *GitHub Actions*.
`.github/workflows/pages.yml` publishes `web/` on every push to `main`.

## Related

[telegraph-mcp](https://github.com/NehoraiHadad/telegraph-mcp) /
[telegraph-mcp-py](https://github.com/NehoraiHadad/telegraph-mcp-py): general Telegraph MCP servers ·
[telegraph-js](https://github.com/NehoraiHadad/telegraph-js) /
[telegraph-py](https://github.com/NehoraiHadad/telegraph-py): Telegraph API clients.
