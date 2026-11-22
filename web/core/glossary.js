// Glossary storage on Telegraph. Format (see docs/FORMAT.md), shared with
// src/telegraph_glossary/glossary.py:
//   * every term is a Telegraph page (title = term, content = definition)
//   * one index page lists all terms, one paragraph per term:
//       <p><a href="https://telegra.ph/<path>">term</a> · alias1, alias2</p>
//   * the account's author_url points at the index page, so the access
//     token alone is enough to find everything.

import { call, pageUrl, pathFromUrl } from "./telegraph.js";
import { markdownToNodes, nodesToMarkdown } from "./markdown.js";

export const APP_URL = "https://nehoraihadad.github.io/telegraph-glossary/";
const ALIAS_SEP = " · ";
// https://telegra.ph/api: "content (Array of Node, up to 64 KB)". Assumed (not verified with a
// real call) to measure the JSON-serialized `content` parameter in UTF-8 bytes, which is what
// call() in telegraph.js sends (JSON.stringify). Same constant and measure in glossary.py.
export const PAGE_LIMIT_BYTES = 64 * 1024;

export const contentBytes = (nodes) => new TextEncoder().encode(JSON.stringify(nodes)).length;

// Stand-in for the path Telegraph will give a new page, used only to size the index before the
// page exists. Assumes Telegraph's observed form: the title with spaces as "-", then "-MM-DD" and
// a "-N" suffix on collisions (here the longest date and a 3-digit suffix).
export const projectedPath = (term) => term.replace(/\s+/g, "-") + "-12-31-999";

/** Throw before any page is written if the index that `terms` builds is over Telegraph's limit.
 *  Otherwise a new term page is created and then orphaned when the index write is rejected. */
export function checkIndexFits(terms) {
  const size = contentBytes(buildIndex(terms));
  if (size > PAGE_LIMIT_BYTES) {
    throw new Error(`The glossary is full: Telegraph limits a page to 64 KB, and the index would be ${(size / 1024).toFixed(1)} KB. Remove terms or shorten aliases first.`);
  }
}

export function parseIndex(nodes) {
  const terms = [];
  for (const n of nodes || []) {
    if (typeof n === "string" || n.tag !== "p") continue;
    const [first, ...rest] = n.children || [];
    if (!first || typeof first === "string" || first.tag !== "a") continue;
    const path = pathFromUrl(first.attrs?.href);
    const term = textOf(first.children).trim();
    if (!path || !term) continue;
    let tail = textOf(rest).trim();
    if (tail.startsWith(ALIAS_SEP.trim())) tail = tail.slice(ALIAS_SEP.trim().length);
    const aliases = tail.split(",").map((s) => s.trim()).filter(Boolean);
    terms.push({ term, aliases, path, url: pageUrl(path) });
  }
  return terms;
}

function textOf(nodes) {
  return (nodes || []).map((n) => (typeof n === "string" ? n : textOf(n.children))).join("");
}

export function buildIndex(terms, title) {
  const sorted = [...terms].sort((a, b) => a.term.localeCompare(b.term));
  const nodes = [
    { tag: "p", children: [{ tag: "em", children: [`${sorted.length} · `, { tag: "a", attrs: { href: APP_URL }, children: ["Telegraph Glossary"] }] }] },
  ];
  for (const t of sorted) {
    const kids = [{ tag: "a", attrs: { href: pageUrl(t.path) }, children: [t.term] }];
    if (t.aliases?.length) kids.push(ALIAS_SEP + t.aliases.join(", "));
    nodes.push({ tag: "p", children: kids });
  }
  if (!sorted.length) nodes.push({ tag: "p", children: ["—"] });
  return nodes;
}

export function cleanAliases(aliases, term) {
  const seen = new Set([term.trim().toLowerCase()]);
  const out = [];
  for (const a of aliases || []) {
    const s = a.replace(/[,·]/g, " ").replace(/\s+/g, " ").trim();
    if (s && !seen.has(s.toLowerCase())) { seen.add(s.toLowerCase()); out.push(s); }
  }
  return out;
}

export class Glossary {
  constructor(token, fetchImpl) {
    this.token = token;
    this.fetch = fetchImpl;
    this.account = null;
    this.indexPath = null;
    this.title = "";
    this.terms = [];
    this.settleMs = 1500; // see updateIndex
  }

  api(method, params = {}) {
    return call(method, { access_token: this.token, ...params }, this.fetch);
  }

  /** Create a new Telegraph account + empty glossary. Returns a Glossary. */
  static async create({ title, authorName }, fetchImpl) {
    const shortName = (title || "Glossary").slice(0, 32);
    const acc = await call("createAccount", { short_name: shortName, author_name: authorName || shortName }, fetchImpl);
    const g = new Glossary(acc.access_token, fetchImpl);
    g.account = acc;
    g.title = title || "Glossary";
    const page = await g.api("createPage", { title: g.title, author_name: acc.author_name, content: buildIndex([], g.title) });
    g.indexPath = page.path;
    g.account = await g.api("editAccountInfo", { short_name: shortName, author_name: acc.author_name, author_url: pageUrl(page.path) });
    await g.api("editPage", { path: page.path, title: g.title, author_name: acc.author_name, author_url: pageUrl(page.path), content: buildIndex([], g.title) });
    return g;
  }

  /** Load account info + index. Creates an index if the account has none. */
  async load() {
    this.account = await this.api("getAccountInfo", { fields: ["short_name", "author_name", "author_url", "page_count"] });
    this.indexPath = pathFromUrl(this.account.author_url);
    if (!this.indexPath) {
      const title = this.account.short_name || "Glossary";
      const page = await this.api("createPage", { title, author_name: this.account.author_name, content: buildIndex([], title) });
      this.indexPath = page.path;
      this.account = await this.api("editAccountInfo", { author_url: pageUrl(page.path) });
    }
    await this.refresh();
    return this;
  }

  async refresh() {
    const page = await call("getPage", { path: this.indexPath, return_content: true }, this.fetch);
    this.title = page.title;
    this.terms = parseIndex(page.content);
    return this.terms;
  }

  get indexUrl() { return pageUrl(this.indexPath); }

  find(term) {
    const k = term.trim().toLowerCase();
    return this.terms.find((t) => t.term.toLowerCase() === k || t.aliases.some((a) => a.toLowerCase() === k));
  }

  pageMeta() {
    return { author_name: this.account?.author_name || this.title, author_url: this.indexUrl };
  }

  async saveIndex() {
    await this.api("editPage", { path: this.indexPath, title: this.title, ...this.pageMeta(), content: buildIndex(this.terms, this.title) });
  }

  async getDefinition(path) {
    const page = await call("getPage", { path, return_content: true }, this.fetch);
    return { title: page.title, nodes: page.content, markdown: nodesToMarkdown(page.content), views: page.views };
  }

  /** Add or update a term. `original` is the existing term name when editing. */
  async saveTerm({ term, aliases = [], definition }, original = null) {
    term = term.replace(/\s+/g, " ").trim();
    if (!term) throw new Error("empty term");
    if (/[,·]/.test(term)) throw new Error("term cannot contain , or ·");
    aliases = cleanAliases(aliases, term);
    await this.refresh(); // read-modify-write: pick up changes from other devices/agents
    const existing = original ? this.find(original) : null;
    const clash = this.find(term) || aliases.map((a) => this.find(a)).find(Boolean);
    if (clash && clash !== existing) throw new Error(`"${clash.term}" already exists`);
    const content = markdownToNodes(definition);
    if (!content.length) throw new Error("empty definition");
    checkIndexFits([...this.terms.filter((t) => t !== existing), { term, aliases, path: existing ? existing.path : projectedPath(term) }]);
    let path;
    if (existing) {
      path = existing.path;
      await this.api("editPage", { path, title: term, ...this.pageMeta(), content });
    } else {
      path = (await this.api("createPage", { title: term, ...this.pageMeta(), content })).path;
    }
    await this.updateIndex((terms) => [...terms.filter((t) => t.path !== path), { term, aliases, path, url: pageUrl(path) }]);
    return this.terms.find((t) => t.path === path);
  }

  /**
   * Change the index while others may edit it too (another tab, an AI agent).
   * Telegraph has no compare-and-swap: two writers that read the same index both write, and the
   * later write drops the earlier change. So each writer writes, waits for writes already in
   * flight to land, re-reads, and re-applies its change on top if it was dropped. `apply` must be
   * idempotent (replace by path, filter by path), so re-applying never duplicates. A write that
   * lands later than settleMs can still drop a change: this narrows the window, it can't close it.
   */
  async updateIndex(apply, attempts = 4) {
    const sig = (terms) => JSON.stringify(terms.map((t) => [t.path, t.term, t.aliases]).sort());
    const missing = () => sig(apply(this.terms)) !== sig(this.terms);
    await this.refresh();
    for (let i = 0; i < attempts; i++) {
      if (!missing()) return;
      this.terms = apply(this.terms);
      await this.saveIndex();
      await new Promise((r) => setTimeout(r, this.settleMs));
      await this.refresh();
    }
    if (missing()) throw new Error("The glossary is being edited somewhere else right now. Try again.");
  }

  async removeTerm(term) {
    await this.refresh();
    const t = this.find(term);
    if (!t) return false;
    // Telegraph pages cannot be deleted: drop it from the index, then blank the page. Index first,
    // so a failed index write (network, concurrent edit) leaves the term intact. If the blanking
    // fails after that, an unlisted page with the old definition is left: harmless, since the
    // index no longer lists or links it.
    await this.updateIndex((terms) => terms.filter((x) => x.path !== t.path));
    await this.api("editPage", { path: t.path, title: t.term, ...this.pageMeta(), content: [{ tag: "p", children: ["—"] }] });
    return true;
  }

  async rename(title) {
    await this.refresh(); // don't write back a stale term list (terms added elsewhere since loading)
    this.title = title;
    await this.saveIndex();
  }

  async authUrl() {
    const r = await this.api("getAccountInfo", { fields: ["auth_url"] });
    return r.auth_url;
  }
}
