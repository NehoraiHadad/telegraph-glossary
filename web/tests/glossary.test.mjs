import { test } from "node:test";
import assert from "node:assert/strict";
import { Glossary, buildIndex, parseIndex } from "../core/glossary.js";

const LIMIT = 64 * 1024; // Telegraph's page content limit, measured as the JSON sent, in UTF-8 bytes
const sentBytes = (nodes) => new TextEncoder().encode(JSON.stringify(nodes)).length;

// In-memory Telegraph: pages by path, the content limit enforced, and an index write that can fail.
function memTelegraph(terms) {
  const pages = { Idx: { title: "G", content: buildIndex(terms) } };
  for (const t of terms) pages[t.path] = { title: t.term, content: [{ tag: "p", children: [`about ${t.term}`] }] };
  // failPage: editPage of this path fails (onFail runs then); lostPage: it is applied, but the answer is an error.
  const state = { pages, failIndexWrite: false, failPage: null, onFail: null, lostPage: null, indexWrites: 0 };
  const ok = (result) => ({ json: async () => ({ ok: true, result }) });
  const fail = (error) => ({ json: async () => ({ ok: false, error }) });
  const fetchImpl = async (url, { body }) => {
    const method = url.split("/").pop();
    const p = Object.fromEntries(body);
    if (method === "getPage") return ok(pages[p.path]);
    const content = JSON.parse(p.content);
    if (new TextEncoder().encode(p.content).length > LIMIT) return fail("CONTENT_TOO_BIG");
    if (method === "createPage") {
      const path = `${p.title}-${Object.keys(pages).length}`;
      pages[path] = { title: p.title, content };
      return ok({ path });
    }
    if (method === "editPage") {
      if (p.path === state.failPage) { state.onFail?.(); return fail("network down"); }
      if (p.path === "Idx") {
        if (state.failIndexWrite) return fail("index write failed");
        state.indexWrites++;
      }
      pages[p.path] = { title: p.title, content };
      return p.path === state.lostPage ? fail("network down") : ok({});
    }
    throw new Error(method);
  };
  const g = new Glossary("tok", fetchImpl);
  g.indexPath = "Idx"; g.account = { author_name: "a" }; g.settleMs = 0;
  return { g, state };
}

test("removing a term keeps its definition when the index write fails", async () => {
  const { g, state } = memTelegraph([{ term: "API", aliases: [], path: "API-1" }]);
  state.failIndexWrite = true;
  await assert.rejects(g.removeTerm("API"), /index write failed/);
  assert.deepEqual(state.pages["API-1"].content, [{ tag: "p", children: ["about API"] }]);
  state.failIndexWrite = false;
  assert.equal(await g.removeTerm("API"), true);
  assert.deepEqual(parseIndex(state.pages.Idx.content), []);
  assert.deepEqual(state.pages["API-1"].content, [{ tag: "p", children: ["—"] }]);
});

test("adding to a full glossary fails before any page is written", async () => {
  let terms = [];
  for (;;) {
    const i = String(terms.length).padStart(4, "0");
    const more = [...terms, { term: `Term ${i}`, aliases: ["x".repeat(40)], path: `Term-${i}-11-22` }];
    if (sentBytes(buildIndex(more)) > LIMIT) break;
    terms = more;
  }
  const { g, state } = memTelegraph(terms);
  const before = JSON.stringify(state.pages);
  await assert.rejects(g.saveTerm({ term: "A new term with a long enough name", definition: "def" }), /The glossary is full/);
  assert.equal(JSON.stringify(state.pages), before);
  assert.equal(state.indexWrites, 0);
  // an update that fits still works
  await g.saveTerm({ term: "Term 0000", aliases: ["x".repeat(40)], definition: "changed" }, "Term 0000");
  assert.deepEqual(state.pages["Term-0000-11-22"].content, [{ tag: "p", children: ["changed"] }]);
});

test("removing a term lists it again when blanking its page fails", async () => {
  const { g, state } = memTelegraph([{ term: "API", aliases: [], path: "API-1" }]);
  state.failPage = "API-1";
  await assert.rejects(g.removeTerm("API"), /network down/);
  assert.deepEqual(parseIndex(state.pages.Idx.content).map((t) => t.term), ["API"]);
  state.failPage = null;
  assert.equal(await g.removeTerm("API"), true);
  assert.deepEqual(parseIndex(state.pages.Idx.content), []);
});

test("removing a term whose page was blanked although the answer was lost does not list it again", async () => {
  const { g, state } = memTelegraph([{ term: "API", aliases: [], path: "API-1" }]);
  state.lostPage = "API-1";
  assert.equal(await g.removeTerm("API"), true);
  assert.deepEqual(parseIndex(state.pages.Idx.content), []);
  assert.deepEqual(state.pages["API-1"].content, [{ tag: "p", children: ["—"] }]);
});

test("removing a term: if listing it again fails too, the error keeps the cause and names the unlisted page", async () => {
  const { g, state } = memTelegraph([{ term: "API", aliases: [], path: "API-1" }]);
  state.failPage = "API-1";
  state.onFail = () => { state.failIndexWrite = true; };
  const err = await g.removeTerm("API").then(() => null, (e) => e);
  assert.ok(err);
  assert.match(err.message, /"API"/);
  assert.match(err.message, /https:\/\/telegra\.ph\/API-1/);
  assert.match(err.message, /no longer listed/);
  assert.match(err.message, /network down/); // the original cause
  assert.match(err.message, /index write failed/);
  assert.match(err.cause?.message || "", /network down/);
  assert.deepEqual(state.pages["API-1"].content, [{ tag: "p", children: ["about API"] }]);
});
