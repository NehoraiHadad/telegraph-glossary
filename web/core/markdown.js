// Minimal Markdown <-> Telegraph node conversion.
// Supported: paragraphs, line breaks, # / ## (h3), ### (h4), lists (- / 1.),
// > quotes, ``` code blocks, ---, ![alt](url) images, **bold**, *italic*,
// ~~strike~~, `code`, [text](url).
// Mirrors src/telegraph_glossary/markdown.py.

const INLINE = /`([^`]+)`|!\[([^\]]*)\]\(([^)\s]+)\)|\[([^\]]+)\]\(([^)\s]+)\)|\*\*(.+?)\*\*|~~(.+?)~~|\*([^*\s][^*]*?)\*|(?<![\p{L}\p{N}])_([^_\s][^_]*?)_(?![\p{L}\p{N}])/gu;

export function inlineToNodes(text) {
  const out = [];
  let pos = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > pos) out.push(text.slice(pos, m.index));
    const [, code, imgAlt, imgSrc, linkText, href, bold, strike, em1, em2] = m;
    if (code !== undefined) out.push({ tag: "code", children: [code] });
    else if (imgSrc !== undefined) out.push({ tag: "img", attrs: { src: imgSrc, ...(imgAlt ? { alt: imgAlt } : {}) } });
    else if (href !== undefined) out.push({ tag: "a", attrs: { href }, children: inlineToNodes(linkText) });
    else if (bold !== undefined) out.push({ tag: "strong", children: inlineToNodes(bold) });
    else if (strike !== undefined) out.push({ tag: "s", children: inlineToNodes(strike) });
    else out.push({ tag: "em", children: inlineToNodes(em1 ?? em2) });
    pos = m.index + m[0].length;
  }
  if (pos < text.length) out.push(text.slice(pos));
  return out;
}

function joinLines(lines) {
  const children = [];
  lines.forEach((l, i) => {
    if (i) children.push({ tag: "br" });
    children.push(...inlineToNodes(l));
  });
  return children;
}

export function markdownToNodes(md) {
  const lines = (md || "").replace(/\r\n?/g, "\n").split("\n");
  const nodes = [];
  let para = [];
  const flush = () => {
    if (para.length) nodes.push({ tag: "p", children: joinLines(para) });
    para = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();
    if (t.startsWith("```")) {
      flush();
      const code = [];
      while (++i < lines.length && !lines[i].trim().startsWith("```")) code.push(lines[i]);
      nodes.push({ tag: "pre", children: [code.join("\n")] });
      continue;
    }
    if (!t) { flush(); continue; }
    let m;
    if ((m = t.match(/^(#{1,6})\s+(.*)$/))) {
      flush();
      nodes.push({ tag: m[1].length <= 2 ? "h3" : "h4", children: inlineToNodes(m[2]) });
    } else if (/^(-{3,}|\*{3,})$/.test(t)) {
      flush();
      nodes.push({ tag: "hr" });
    } else if ((m = t.match(/^!\[([^\]]*)\]\(([^)\s]+)\)$/))) {
      flush();
      const fig = [{ tag: "img", attrs: { src: m[2] } }];
      if (m[1]) fig.push({ tag: "figcaption", children: [m[1]] });
      nodes.push({ tag: "figure", children: fig });
    } else if (t.startsWith(">")) {
      flush();
      const q = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) q.push(lines[i++].trim().replace(/^>\s?/, ""));
      i--;
      nodes.push({ tag: "blockquote", children: joinLines(q) });
    } else if (/^([-*+]|\d+[.)])\s+/.test(t)) {
      flush();
      const ordered = /^\d/.test(t);
      const items = [];
      while (i < lines.length && /^([-*+]|\d+[.)])\s+/.test(lines[i].trim()) && /^\d/.test(lines[i].trim()) === ordered) {
        items.push({ tag: "li", children: inlineToNodes(lines[i++].trim().replace(/^([-*+]|\d+[.)])\s+/, "")) });
      }
      i--;
      nodes.push({ tag: ordered ? "ol" : "ul", children: items });
    } else {
      para.push(t);
    }
  }
  flush();
  return nodes;
}

function inlineToMd(nodes) {
  return (nodes || [])
    .map((n) => {
      if (typeof n === "string") return n;
      const inner = inlineToMd(n.children);
      switch (n.tag) {
        case "b": case "strong": return `**${inner}**`;
        case "i": case "em": return `*${inner}*`;
        case "s": return `~~${inner}~~`;
        case "code": return `\`${inner}\``;
        case "a": return `[${inner}](${n.attrs?.href || ""})`;
        case "br": return "\n";
        case "img": return `![${n.attrs?.alt || ""}](${n.attrs?.src || ""})`;
        default: return inner;
      }
    })
    .join("");
}

export function nodesToMarkdown(nodes) {
  const blocks = [];
  for (const n of nodes || []) {
    if (typeof n === "string") { if (n.trim()) blocks.push(n.trim()); continue; }
    const kids = n.children || [];
    switch (n.tag) {
      case "h3": blocks.push(`## ${inlineToMd(kids)}`); break;
      case "h4": blocks.push(`### ${inlineToMd(kids)}`); break;
      case "hr": blocks.push("---"); break;
      case "pre": blocks.push("```\n" + inlineToMd(kids) + "\n```"); break;
      case "blockquote": case "aside":
        blocks.push(inlineToMd(kids).split("\n").map((l) => `> ${l}`).join("\n")); break;
      case "ul": case "ol":
        blocks.push(kids.filter((k) => typeof k !== "string").map((li, idx) =>
          `${n.tag === "ol" ? `${idx + 1}.` : "-"} ${inlineToMd(li.children)}`).join("\n")); break;
      case "figure": {
        const img = kids.find((k) => k.tag === "img");
        const cap = kids.find((k) => k.tag === "figcaption");
        if (img) blocks.push(`![${cap ? inlineToMd(cap.children) : ""}](${img.attrs?.src || ""})`);
        break;
      }
      case "img": blocks.push(inlineToMd([n])); break;
      default: { const s = inlineToMd(kids).trim(); if (s) blocks.push(s); }
    }
  }
  return blocks.join("\n\n");
}

export function nodesToText(nodes) {
  return (nodes || [])
    .map((n) => (typeof n === "string" ? n : n.tag === "br" ? "\n" : nodesToText(n.children) + (/^(p|h3|h4|li|blockquote|pre)$/.test(n.tag) ? "\n" : "")))
    .join("");
}

const ESC = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const SAFE_URL = (u) => (/^(https?:|mailto:|tg:)/i.test(u || "") ? u : "#");

/** Render nodes to HTML for in-app preview (safe: only whitelisted tags/attrs). */
export function nodesToHtml(nodes) {
  const ALLOWED = new Set(["a", "aside", "b", "blockquote", "br", "code", "em", "figcaption", "figure", "h3", "h4", "hr", "i", "img", "li", "ol", "p", "pre", "s", "strong", "u", "ul"]);
  return (nodes || [])
    .map((n) => {
      if (typeof n === "string") return ESC(n);
      const tag = ALLOWED.has(n.tag) ? n.tag : "span";
      let attrs = "";
      if (tag === "a") attrs = ` href="${ESC(SAFE_URL(n.attrs?.href))}" target="_blank" rel="noopener"`;
      if (tag === "img") attrs = ` src="${ESC(SAFE_URL(n.attrs?.src))}" alt="${ESC(n.attrs?.alt || "")}"`;
      if (tag === "br" || tag === "hr" || tag === "img") return `<${tag}${attrs}>`;
      return `<${tag}${attrs}>${nodesToHtml(n.children)}</${tag}>`;
    })
    .join("");
}
