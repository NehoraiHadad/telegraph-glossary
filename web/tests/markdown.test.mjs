import { test } from "node:test";
import assert from "node:assert/strict";
import { markdownToNodes, nodesToMarkdown } from "../core/markdown.js";
import { buildIndex, parseIndex } from "../core/glossary.js";
import { pathFromUrl } from "../core/telegraph.js";

const MD = `## Title

**Bold** and *italic* with [a link](https://example.com) and \`code\`.
second line

- one
- two

1. first
2. second

> quoted

\`\`\`
x = 1
\`\`\`

![caption](https://example.com/a.png)

---`;

test("markdown round trip", () => assert.equal(nodesToMarkdown(markdownToNodes(MD)), MD));

test("index round trip", () => {
  const terms = [{ term: "פייתון", path: "פייתון-11-21", aliases: ["Python"] }, { term: "API", path: "API-11-21", aliases: [] }];
  const parsed = parseIndex(buildIndex(terms)).map((t) => [t.term, t.path, t.aliases]);
  assert.deepEqual(parsed, [["API", "API-11-21", []], ["פייתון", "פייתון-11-21", ["Python"]]]);
});

test("relative and encoded paths", () => {
  assert.equal(pathFromUrl("/%D7%A4%D7%99-11-21"), "פי-11-21");
  assert.equal(pathFromUrl("https://telegra.ph/API-11-21"), "API-11-21");
  assert.equal(pathFromUrl("https://example.com/x"), null);
});
