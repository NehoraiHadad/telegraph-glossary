// Add glossary links to an existing Telegram message *as entities*, keeping the
// author's own formatting (bold, links, buttons...) untouched. Used by the
// channel bot (bot/). Offsets are UTF-16 code units, like Telegram's.

import { findTerms } from "./linker.js";

// Formatting entities may nest around/inside a link; anything else may not overlap one.
const NESTABLE = new Set(["bold", "italic", "underline", "strikethrough", "spoiler"]);

/** Remove links this glossary added earlier (so we can recompute from the author's original). */
export function stripGlossaryLinks(entities, isGlossaryUrl) {
  return (entities || []).filter((e) => !(e.type === "text_link" && isGlossaryUrl(e.url)));
}

/**
 * @param {string} text
 * @param {object[]} entities  the author's entities (without glossary links)
 * @param {object[]} terms     [{term, aliases, url}]
 * @param {{mode?: "first"|"all"}} options
 * @returns {{entities: object[], found: string[]}}
 */
export function addLinkEntities(text, entities, terms, options = {}) {
  const mode = options.mode || "first";
  const base = entities || [];
  const { segments } = findTerms(text, terms, { mode: "all" });
  const added = [];
  const found = [];
  const done = new Set();
  let offset = 0;
  for (const s of segments) {
    const start = offset;
    offset += s.text.length; // JS string length is UTF-16, same unit as Telegram
    if (s.term === undefined) continue;
    const key = s.term.toLowerCase();
    if (mode === "first" && done.has(key)) continue;
    const end = start + s.text.length;
    const ok = base.every((e) => {
      const es = e.offset, ee = e.offset + e.length;
      if (ee <= start || es >= end) return true; // no overlap
      if (!NESTABLE.has(e.type)) return false; // never link inside code/links/mentions/...
      return (es <= start && ee >= end) || (es >= start && ee <= end); // nesting only, no partial overlap
    });
    if (!ok) continue;
    added.push({ type: "text_link", offset: start, length: s.text.length, url: s.url });
    if (!done.has(key)) { done.add(key); found.push(s.term); }
  }
  const merged = [...base, ...added].sort((a, b) => a.offset - b.offset || b.length - a.length);
  return { entities: merged, found };
}

/** Stable comparison of entity lists (ignores key order / extra fields). */
export function sameEntities(a, b) {
  const norm = (list) => JSON.stringify((list || [])
    .map((e) => [e.type, e.offset, e.length, e.url || "", e.language || "", e.custom_emoji_id || "", e.user?.id || ""])
    .sort());
  return norm(a) === norm(b);
}
