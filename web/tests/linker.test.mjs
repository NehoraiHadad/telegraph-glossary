import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { linkText } from "../core/linker.js";

const spec = JSON.parse(readFileSync(new URL("../../spec/linker-cases.json", import.meta.url)));
for (const c of spec.cases) {
  test(c.name, () => {
    const r = linkText(c.text, spec.terms, c.options || {});
    assert.equal(r.html, c.expected_html);
    assert.deepEqual(r.found, c.expected_found);
  });
}

test("dotless i neither crashes nor matches", () => {
  const r = linkText("\u0131 test", [{ term: "i", aliases: [], url: "https://telegra.ph/I-1" }]);
  assert.equal(r.html, "\u0131 test");
  assert.deepEqual(r.found, []);
});

test("first registered wins among case-equivalent forms", () => {
  const terms = [
    { term: "Silk", aliases: [], url: "https://telegra.ph/A" },
    { term: "silk", aliases: ["\u017Filk"], url: "https://telegra.ph/B" },
  ];
  const r = linkText("\u017FILK", terms);
  assert.equal(r.html, '<a href="https://telegra.ph/A">\u017FILK</a>');
  assert.deepEqual(r.found, ["Silk"]);
});
