// Term linker: finds glossary terms in plain text and turns them into links.
// Must stay behavior-identical to src/telegraph_glossary/linker.py
// (both are tested against spec/linker-cases.json).

// One-to-three Hebrew prefix letters (ו ה ב כ ל מ ש) optionally followed by a maqaf/hyphen.
const HEB_PREFIX = "(?:[והבכלמש]{1,3}[-־]?)?";
const WORD = "[\\p{L}\\p{N}_]";
// Spans that must never be touched: URLs, @mentions, #hashtags.
const PROTECTED = /(?:https?:\/\/|www\.)\S+|[@#][\p{L}\p{N}_]+/gu;

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}

/**
 * Split text into segments.
 * @param {string} text
 * @param {{term:string, aliases?:string[], url:string}[]} terms
 * @param {{mode?:"first"|"all", exclude?:string[]}} options
 * @returns {{segments: ({text:string}|{text:string, term:string, url:string, linked:boolean})[], found: string[]}}
 *   Segments with `term` are glossary matches; `linked` is false for repeat
 *   occurrences (mode "first") or excluded terms, so a UI can still show them.
 */
export function findTerms(text, terms, options = {}) {
  const mode = options.mode || "first";
  const exclude = new Set((options.exclude || []).map((t) => t.toLowerCase()));

  const formToTerm = new Map();
  for (const t of terms) {
    for (const form of [t.term, ...(t.aliases || [])]) {
      const f = form.trim();
      if (f && !formToTerm.has(f.toLowerCase())) formToTerm.set(f.toLowerCase(), t);
    }
  }
  if (formToTerm.size === 0) return { segments: text ? [{ text }] : [], found: [] };

  const forms = [...formToTerm.keys()].sort((a, b) => b.length - a.length || (a < b ? -1 : 1));
  const re = new RegExp(
    `(?<!${WORD})(${HEB_PREFIX})(${forms.map(escapeRegex).join("|")})(?!${WORD})`,
    "giu",
  );

  const segments = [];
  const found = [];
  const seen = new Set();
  const push = (s) => {
    if (!s) return;
    const last = segments[segments.length - 1];
    if (last && last.term === undefined) last.text += s;
    else segments.push({ text: s });
  };

  const scan = (chunk) => {
    let pos = 0;
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(chunk)) !== null) {
      const [whole, prefix, form] = m;
      const t = formToTerm.get(form.toLowerCase());
      push(chunk.slice(pos, m.index) + prefix);
      const key = t.term.toLowerCase();
      const excluded = exclude.has(key);
      const linked = !excluded && (mode === "all" || !seen.has(key));
      if (!excluded && !seen.has(key)) {
        seen.add(key);
        found.push(t.term);
      }
      segments.push({ text: form, term: t.term, url: t.url, linked });
      pos = m.index + whole.length;
    }
    push(chunk.slice(pos));
  };

  let pos = 0;
  for (const m of text.matchAll(PROTECTED)) {
    scan(text.slice(pos, m.index));
    push(m[0]);
    pos = m.index + m[0].length;
  }
  scan(text.slice(pos));
  return { segments, found };
}

/** Telegram-flavoured HTML (parse_mode=HTML). */
export function toTelegramHtml(segments) {
  return segments
    .map((s) =>
      s.term !== undefined && s.linked
        ? `<a href="${escapeAttr(s.url)}">${escapeHtml(s.text)}</a>`
        : escapeHtml(s.text),
    )
    .join("");
}

export function toMarkdown(segments) {
  return segments
    .map((s) => (s.term !== undefined && s.linked ? `[${s.text.replace(/([\[\]])/g, "\\$1")}](${s.url})` : s.text))
    .join("");
}

export function toPlain(segments) {
  return segments.map((s) => s.text).join("");
}

export function linkText(text, terms, options = {}) {
  const { segments, found } = findTerms(text, terms, options);
  return { html: toTelegramHtml(segments), markdown: toMarkdown(segments), found, segments };
}
