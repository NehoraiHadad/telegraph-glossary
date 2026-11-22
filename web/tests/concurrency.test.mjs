import { test } from "node:test";
import assert from "node:assert/strict";
import { Glossary, buildIndex, parseIndex } from "../core/glossary.js";

test("a stale concurrent write that drops our term is repaired; a no-op does not write", async () => {
  let page = buildIndex([{ term: "A", aliases: [], path: "A-1" }]);
  let writes = 0, staleWritePending = true;
  const fakeFetch = async (url, { body }) => {
    const method = url.split("/").pop();
    if (method === "getPage") return { json: async () => ({ ok: true, result: { title: "G", content: page } }) };
    if (method === "editPage") {
      writes++;
      page = JSON.parse(body.get("content"));
      if (staleWritePending) { // another writer read before our write and saves its copy right after
        staleWritePending = false;
        page = buildIndex([{ term: "A", aliases: [], path: "A-1" }, { term: "B", aliases: [], path: "B-1" }]);
      }
      return { json: async () => ({ ok: true, result: {} }) };
    }
    throw new Error(method);
  };
  const g = new Glossary("tok", fakeFetch);
  g.indexPath = "Idx"; g.account = { author_name: "a" }; g.settleMs = 0;
  const addC = (terms) => [...terms.filter((t) => t.path !== "C-1"), { term: "C", aliases: [], path: "C-1" }];
  await g.updateIndex(addC);
  assert.deepEqual(parseIndex(page).map((t) => t.term).sort(), ["A", "B", "C"]);
  writes = 0;
  await g.updateIndex(addC);
  assert.equal(writes, 0);
});

// The real race: two writers read the same index, then both write. Telegraph has no
// compare-and-swap, so the later write drops the earlier term unless each writer checks
// after writing that its change survived, and re-applies it on top of the latest index.
test("two writers adding at the same moment both keep their term", async () => {
  let page = buildIndex([{ term: "A", aliases: [], path: "A-1" }]);
  const fakeFetch = async (url, { body }) => {
    const method = url.split("/").pop();
    if (method === "getPage") return { json: async () => ({ ok: true, result: { title: "G", content: page } }) };
    if (method === "editPage") {
      const content = JSON.parse(body.get("content"));
      await new Promise((r) => setTimeout(r, 10)); // both writers have read before either write lands
      page = content;
      return { json: async () => ({ ok: true, result: {} }) };
    }
    throw new Error(method);
  };
  const writer = () => {
    const g = new Glossary("tok", fakeFetch);
    g.indexPath = "Idx"; g.account = { author_name: "a" }; g.settleMs = 40;
    return g;
  };
  await Promise.all([
    writer().updateIndex((terms) => [...terms.filter((t) => t.path !== "B-1"), { term: "B", aliases: [], path: "B-1" }]),
    writer().updateIndex((terms) => [...terms.filter((t) => t.path !== "C-1"), { term: "C", aliases: [], path: "C-1" }]),
  ]);
  assert.deepEqual(parseIndex(page).map((t) => t.term).sort(), ["A", "B", "C"]);
});
