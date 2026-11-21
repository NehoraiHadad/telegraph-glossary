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
