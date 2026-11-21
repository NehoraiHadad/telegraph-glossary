import { test } from "node:test";
import assert from "node:assert/strict";
import { Glossary, buildIndex, parseIndex } from "../core/glossary.js";

test("updateIndex keeps a term another writer added between read and write", async () => {
  let page = buildIndex([{ term: "A", aliases: [], path: "A-1" }]);
  let reads = 0, writes = 0;
  const fakeFetch = async (url, { body }) => {
    const method = url.split("/").pop();
    if (method === "getPage") {
      reads++;
      const out = { ok: true, result: { title: "G", content: page } };
      if (reads === 1) page = buildIndex([{ term: "A", aliases: [], path: "A-1" }, { term: "B", aliases: [], path: "B-1" }]); // someone else writes
      return { json: async () => out };
    }
    if (method === "editPage") { writes++; page = JSON.parse(body.get("content")); return { json: async () => ({ ok: true, result: {} }) }; }
    throw new Error(method);
  };
  const g = new Glossary("tok", fakeFetch);
  g.indexPath = "Idx"; g.account = { author_name: "a" };
  await g.updateIndex((terms) => [...terms, { term: "C", aliases: [], path: "C-1" }]);
  assert.deepEqual(parseIndex(page).map((t) => t.term).sort(), ["A", "B", "C"]);
  assert.equal(writes, 1);
});
