import test from "node:test";
import assert from "node:assert/strict";

import {
  MATH_LEVELS,
  MATH_SYMBOLS,
  filterSymbolsByLevel,
  getAvailableCategories,
  groupSymbolsByCategory,
  normalizeMathLevel,
  wrapBareLatexForSending,
} from "../lib/math-symbols";

test("MATH_LEVELS is ordered elementary → full", () => {
  assert.deepEqual([...MATH_LEVELS], [
    "elementary",
    "middle",
    "high",
    "full",
  ]);
});

test("filterSymbolsByLevel is cumulative — each stage includes all prior stages", () => {
  const elem = filterSymbolsByLevel("elementary");
  const mid = filterSymbolsByLevel("middle");
  const high = filterSymbolsByLevel("high");
  const full = filterSymbolsByLevel("full");

  // Every elementary symbol appears in middle/high/full.
  for (const s of elem) {
    assert.ok(mid.includes(s), `middle missing elementary symbol ${s.label}`);
    assert.ok(high.includes(s), `high missing elementary symbol ${s.label}`);
    assert.ok(full.includes(s), `full missing elementary symbol ${s.label}`);
  }
  // Every middle symbol appears in high/full.
  for (const s of mid) assert.ok(high.includes(s));
  for (const s of mid) assert.ok(full.includes(s));
  // Every high symbol appears in full.
  for (const s of high) assert.ok(full.includes(s));

  // Strictly increasing counts.
  assert.ok(elem.length < mid.length);
  assert.ok(mid.length < high.length);
  assert.ok(high.length <= full.length);
});

test("filterSymbolsByLevel never leaks a higher-stage symbol into a lower stage", () => {
  const elemLabels = new Set(filterSymbolsByLevel("elementary").map((s) => s.label));
  for (const s of MATH_SYMBOLS) {
    if (s.level !== "elementary") {
      assert.ok(
        !elemLabels.has(s.label),
        `elementary leaked non-elementary symbol ${s.label}`,
      );
    }
  }
});

test("getAvailableCategories hides empty tabs — calculus absent at elementary", () => {
  const elemCats = getAvailableCategories("elementary");
  assert.ok(!elemCats.includes("calculus"));
  assert.ok(!elemCats.includes("sets"));
  assert.ok(!elemCats.includes("arrows"));

  const highCats = getAvailableCategories("high");
  assert.ok(highCats.includes("calculus"));
  assert.ok(highCats.includes("sets"));
});

test("getAvailableCategories returns a stable, hand-curated order", () => {
  const cats = getAvailableCategories("full");
  // operators should come before greek, greek before templates, etc.
  assert.ok(cats.indexOf("operators") < cats.indexOf("greek"));
  assert.ok(cats.indexOf("greek") < cats.indexOf("calculus"));
  assert.ok(cats.indexOf("calculus") < cats.indexOf("templates"));
});

test("groupSymbolsByCategory partitions symbols with no overlap or gap", () => {
  const grouped = groupSymbolsByCategory("high");
  const cats = getAvailableCategories("high");
  const flat = cats.flatMap((c) => grouped[c] ?? []);
  // Every grouped symbol is valid for high stage.
  for (const s of flat) assert.ok(MATH_LEVELS.indexOf(s.level) <= MATH_LEVELS.indexOf("high"));
  // Count matches the flat filter.
  assert.equal(flat.length, filterSymbolsByLevel("high").length);
});

test("normalizeMathLevel accepts valid stages and falls back on junk", () => {
  assert.equal(normalizeMathLevel("elementary"), "elementary");
  assert.equal(normalizeMathLevel("middle"), "middle");
  assert.equal(normalizeMathLevel("high"), "high");
  assert.equal(normalizeMathLevel("full"), "full");
  // Invalid values fall back to default (full).
  assert.equal(normalizeMathLevel("college"), "full");
  assert.equal(normalizeMathLevel(undefined), "full");
  assert.equal(normalizeMathLevel(null), "full");
  assert.equal(normalizeMathLevel(123), "full");
  // Custom fallback honored.
  assert.equal(normalizeMathLevel("nope", "middle"), "middle");
});

test("templates carry caretFromEnd so the caret lands inside the first {}", () => {
  const tpls = MATH_SYMBOLS.filter((s) => s.category === "templates");
  assert.ok(tpls.length > 0);
  for (const t of tpls) {
    assert.ok(
      typeof t.caretFromEnd === "number",
      `template ${t.label} missing caretFromEnd`,
    );
    // caretFromEnd should not exceed the latex length.
    assert.ok(t.caretFromEnd! <= t.latex.length);
  }
});

test("π is available from elementary (the one Greek letter young learners meet)", () => {
  const elem = filterSymbolsByLevel("elementary");
  assert.ok(elem.some((s) => s.latex === "\\pi"));
});

// ── wrapBareLatexForSending ─────────────────────────────────────────────

test("wrapBareLatexForSending leaves plain text untouched", () => {
  assert.equal(wrapBareLatexForSending("请讲解这个公式的因式分解"), "请讲解这个公式的因式分解");
  assert.equal(wrapBareLatexForSending("Explain the quadratic formula"), "Explain the quadratic formula");
  assert.equal(wrapBareLatexForSending("a + b = c"), "a + b = c");
});

test("wrapBareLatexForSending wraps a bare superscript run (perfect-square case)", () => {
  assert.equal(
    wrapBareLatexForSending("y=x^{2}+2xy+y^{2}"),
    "$y=x^{2}+2xy+y^{2}$",
  );
});

test("wrapBareLatexForSending wraps bare backslash commands", () => {
  assert.equal(
    wrapBareLatexForSending("化简 \\frac{1}{x^{2}+1}"),
    "化简 $\\frac{1}{x^{2}+1}$",
  );
  assert.equal(
    wrapBareLatexForSending("求 \\pi 的值"),
    "求 $\\pi$ 的值",
  );
  assert.equal(
    wrapBareLatexForSending("\\sqrt{2} 是无理数"),
    "$\\sqrt{2}$ 是无理数",
  );
});

test("wrapBareLatexForSending wraps subscript groups", () => {
  assert.equal(wrapBareLatexForSending("a_{1} + a_{2}"), "$a_{1} + a_{2}$");
});

test("wrapBareLatexForSending does not double-wrap already-delimited math", () => {
  assert.equal(
    wrapBareLatexForSending("已知 $a+b=1$，求 $\\frac{a}{b}$"),
    "已知 $a+b=1$，求 $\\frac{a}{b}$",
  );
  assert.equal(
    wrapBareLatexForSending("块级公式：\n$$x^{2}+y^{2}=z^{2}$$\n说明"),
    "块级公式：\n$$x^{2}+y^{2}=z^{2}$$\n说明",
  );
  assert.equal(
    wrapBareLatexForSending("行内 \\( \\frac{1}{2} \\) 保留"),
    "行内 \\( \\frac{1}{2} \\) 保留",
  );
});

test("wrapBareLatexForSending wraps only the math run inside mixed prose", () => {
  // Chinese text around the formula is not pulled into the math span.
  assert.equal(
    wrapBareLatexForSending("完全平方公式 y=x^{2}+2xy+y^{2} 很重要"),
    "完全平方公式 $y=x^{2}+2xy+y^{2}$ 很重要",
  );
});

test("wrapBareLatexForSending wraps multiple bare runs separately", () => {
  assert.equal(
    wrapBareLatexForSending("求 \\frac{1}{2} 和 \\frac{1}{3} 的和"),
    "求 $\\frac{1}{2}$ 和 $\\frac{1}{3}$ 的和",
  );
});

test("wrapBareLatexForSending ignores lone caret / backslash (no false positives)", () => {
  assert.equal(wrapBareLatexForSending("a^b"), "a^b");
  assert.equal(wrapBareLatexForSending("5% 和 10% 的差值"), "5% 和 10% 的差值");
  // A bare operator in prose still gets wrapped when it forms a real command.
  assert.equal(wrapBareLatexForSending("用 \\times 表示乘法"), "用 $\\times$ 表示乘法");
});
