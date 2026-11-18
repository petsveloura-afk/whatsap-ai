import { test } from "node:test";
import assert from "node:assert/strict";
import { passwordIssues, passwordStrength, strengthLabel, emailProblem, friendlyError, resolveApiBase } from "./auth.ts";
test("good password has no issues", () => assert.deepEqual(passwordIssues("Correct-horse-42", "a@b.com"), []));
test("short, common, sequential and email-based passwords are flagged", () => {
  assert.ok(passwordIssues("abc1").some(x => x.includes("10")));
  assert.ok(passwordIssues("password123").some(x => x.includes("נפוצה")));
  assert.ok(passwordIssues("mnopqrstuv12").some(x => x.includes("רצף")));
  assert.ok(passwordIssues("danielcohen-77", "danielcohen@x.com").some(x => x.includes("אימייל")));
  assert.ok(passwordIssues("aaaaaaaaaaaa").length > 0);
});
test("too long in bytes is flagged (hebrew counts double)", () => assert.ok(passwordIssues("א1".repeat(30)).some(x => x.includes("72"))));
test("strength grows with variety and length", () => {
  assert.equal(passwordStrength(""), 0);
  assert.ok(passwordStrength("Abcd-1234-Xyz!") > passwordStrength("abcdefg"));
  assert.equal(strengthLabel(10).level, 0); assert.equal(strengthLabel(95).level, 3);
});
test("email check", () => { assert.equal(emailProblem("a@b.co"), null); assert.ok(emailProblem("nope")); assert.ok(emailProblem("")); });
test("friendly errors", () => {
  assert.match(friendlyError(null, null, true), /חיבור לשרת/);
  assert.match(friendlyError(401, "Invalid credentials"), /שגויים/);
  assert.equal(friendlyError(422, "הסיסמה נפוצה מדי"), "הסיסמה נפוצה מדי");
  assert.match(friendlyError(422, [{ msg: "value is not a valid email address" }]), /אימייל/);
  assert.match(friendlyError(429, "Too many"), /ניסיונות/);
  assert.match(friendlyError(409, "Email already registered"), /רשומה/);
});
test("api base resolution", () => {
  assert.equal(resolveApiBase("https://api.x.app/", undefined), "https://api.x.app");
  assert.equal(resolveApiBase("", "https://rt.x.app//"), "https://rt.x.app");
  assert.equal(resolveApiBase(undefined, undefined), "");
});
