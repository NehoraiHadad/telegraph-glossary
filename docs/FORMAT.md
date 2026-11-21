# Storage format (v2)

Everything lives in one Telegraph account. The **access token is the only key**:
whoever has it can find and edit the whole glossary. Nothing is stored on any
server of ours, because there is no server.

## Account

| field        | value                                   |
|--------------|-----------------------------------------|
| `short_name` | glossary name (max 32 chars)            |
| `author_name`| shown on every page                     |
| `author_url` | **URL of the index page**. That is how a token finds its glossary. |

## Term pages

One Telegraph page per term.

* `title`: the term
* `content`: the definition (written as Markdown in the apps, converted to Telegraph nodes)
* `author_name` / `author_url`: the account's, so the byline on every term page links back to the index

Telegraph pages cannot be deleted. Removing a term blanks its page and drops it from the index.

## Index page

The `title` is the glossary name. The content is a plain, human-readable list
that doubles as the data store:

```html
<p><em>2 · <a href="https://nehoraihadad.github.io/telegraph-glossary/">Telegraph Glossary</a></em></p>
<p><a href="https://telegra.ph/API-11-21">API</a> · APIs, ממשק תכנות</p>
<p><a href="https://telegra.ph/פייתון-11-21">פייתון</a> · Python</p>
```

* A paragraph whose **first child is a link to a telegra.ph page** is a term: the link text
  is the term and the href gives the page path. Telegraph stores links to its own pages as
  relative, percent-encoded paths (`/%D7%A4...`), so parsers accept both forms.
* Text after ` · ` is a comma-separated list of **aliases** (other forms that should also be linked).
  For that reason terms and aliases cannot contain `,` or `·`.
* Any other paragraph is ignored.

Writers always re-read the index right before writing (read-modify-write), so the web
app, the CLI and AI agents can safely edit the same glossary.

Telegraph limits a page to 64 KB of content, so one index holds several hundred terms (fewer with long Hebrew names, whose URLs are percent-encoded).

## Linking rules (`spec/linker-cases.json`)

* Matching is case-insensitive. The longest term or alias wins.
* A match must not be glued to other letters or digits, with one exception: up to three
  Hebrew prefix letters (ו ה ב כ ל מ ש), optionally followed by `-`/`־`, may come before it.
  The prefix is not part of the link (`ב<a>פייתון</a>`).
* URLs, `@mentions` and `#hashtags` are never touched.
* Default mode links only the **first** occurrence of each term. `all` links every occurrence.
* The web linker (`web/core/linker.js`) and the Python linker (`src/telegraph_glossary/linker.py`)
  must both pass the shared cases.
