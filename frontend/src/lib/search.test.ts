import test from "node:test";
import assert from "node:assert/strict";
import { toSearchBody, fmtPrice, isHttpsUrl, passwordProblem } from "./search.ts";

const base = { name: "n", category: null, location: "Holon", min_price: null, max_price: 5500, required_keywords: [], excluded_keywords: ["תיווך"], min_score: 60 };
test("toSearchBody uses parsed category or fallback", () => {
  assert.equal(toSearchBody({ ...base, category: "real_estate" }).category, "real_estate");
  assert.equal(toSearchBody(base, "vehicles").category, "vehicles");
});
test("toSearchBody rejects a missing category", () => { assert.throws(() => toSearchBody(base)); });
test("toSearchBody keeps prices and exclusions", () => {
  const b = toSearchBody({ ...base, category: "real_estate" });
  assert.equal(b.max_price, 5500); assert.deepEqual(b.excluded_keywords, ["תיווך"]);
});
test("fmtPrice", () => { assert.equal(fmtPrice(null), "?"); assert.match(fmtPrice(5200), /5,200 ₪/); });
test("isHttpsUrl", () => { assert.ok(isHttpsUrl("https://a.com/x")); assert.ok(!isHttpsUrl("javascript:alert(1)")); assert.ok(!isHttpsUrl("abc")); });
test("passwordProblem", () => { assert.ok(passwordProblem("short")); assert.equal(passwordProblem("correct-horse-1"), null); });
