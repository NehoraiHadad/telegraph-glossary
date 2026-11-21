import { test } from "node:test";
import assert from "node:assert/strict";
import { addLinkEntities, stripGlossaryLinks, sameEntities } from "../core/entities.js";

const terms = [
  { term: "API", aliases: [], url: "https://telegra.ph/API-1" },
  { term: "פייתון", aliases: ["Python"], url: "https://telegra.ph/Py-1" },
];
const link = (offset, length, url) => ({ type: "text_link", offset, length, url });

test("adds links and keeps author formatting", () => {
  const text = "Hello API world";
  const bold = { type: "bold", offset: 0, length: 5 };
  const r = addLinkEntities(text, [bold], terms);
  assert.deepEqual(r.entities, [bold, link(6, 3, terms[0].url)]);
  assert.deepEqual(r.found, ["API"]);
});

test("UTF-16 offsets after emoji", () => {
  const text = "🚀🚀 API";
  const r = addLinkEntities(text, [], terms);
  assert.deepEqual(r.entities, [link(5, 3, terms[0].url)]);
});

test("link may nest inside bold", () => {
  const text = "about API here";
  const bold = { type: "bold", offset: 0, length: 14 };
  assert.equal(addLinkEntities(text, [bold], terms).entities.length, 2);
});

test("partial overlap with bold is skipped, next occurrence used", () => {
  // "xx API and API": bold covers "I and" (5..10), cutting through the first API (3..6)
  const bold = { type: "bold", offset: 5, length: 5 };
  const r = addLinkEntities("xx API and API", [bold], terms);
  assert.deepEqual(r.entities.filter((e) => e.type === "text_link"), [link(11, 3, terms[0].url)]);
});

test("never links inside code or an existing link", () => {
  const text = "use API and API";
  const code = { type: "code", offset: 4, length: 3 };
  const own = link(12, 3, "https://example.com");
  const r = addLinkEntities(text, [code, own], terms);
  assert.deepEqual(r.entities, [code, own]);
  assert.deepEqual(r.found, []);
});

test("hebrew prefix is not part of the link", () => {
  const r = addLinkEntities("כתבתי בפייתון", [], terms);
  assert.deepEqual(r.entities, [link(7, 6, terms[1].url)]);
});

test("strip + re-add is idempotent", () => {
  const text = "API and Python";
  const first = addLinkEntities(text, [], terms).entities;
  const isOurs = (u) => terms.some((t) => t.url === u);
  const again = addLinkEntities(text, stripGlossaryLinks(first, isOurs), terms).entities;
  assert.ok(sameEntities(first, again));
});
