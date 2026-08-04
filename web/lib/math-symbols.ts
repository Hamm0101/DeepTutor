/**
 * Math symbol palette data + level-based filtering.
 *
 * The chat composer surfaces a symbol palette whose contents shrink/grow
 * with the learner's stage (`math_input_level` in UI settings). Stages are
 * cumulative — choosing "middle" shows elementary + middle symbols, never
 * calculus. This keeps the palette uncluttered for younger learners while
 * staying a single setting (set once, remembered across sessions).
 *
 * Stages follow the CN curriculum:
 *   elementary → middle → high → full
 *
 * Data is intentionally framework-agnostic (pure functions + plain arrays)
 * so it can be unit-tested without React.
 */

export const MATH_LEVELS = [
  "elementary",
  "middle",
  "high",
  "full",
] as const;
export type MathLevel = (typeof MATH_LEVELS)[number];

export const MATH_LEVEL_LABELS: Record<
  MathLevel,
  { zh: string; en: string; emoji: string }
> = {
  elementary: { zh: "小学", en: "Elementary", emoji: "🧒" },
  middle: { zh: "初中", en: "Middle", emoji: "👦" },
  high: { zh: "高中", en: "High", emoji: "👨" },
  full: { zh: "全部", en: "All", emoji: "🎓" },
};

export type MathCategory =
  | "operators"
  | "greek"
  | "relations"
  | "arrows"
  | "calculus"
  | "sets"
  | "brackets"
  | "templates";

export const MATH_CATEGORY_LABELS: Record<
  MathCategory,
  { zh: string; en: string }
> = {
  operators: { zh: "运算符", en: "Operators" },
  greek: { zh: "希腊字母", en: "Greek" },
  relations: { zh: "关系符", en: "Relations" },
  arrows: { zh: "箭头", en: "Arrows" },
  calculus: { zh: "微积分", en: "Calculus" },
  sets: { zh: "集合", en: "Sets" },
  brackets: { zh: "括号", en: "Brackets" },
  templates: { zh: "模板", en: "Templates" },
};

export interface MathSymbol {
  /** What the button shows — a Unicode glyph or a short LaTeX verb. */
  label: string;
  /** LaTeX code inserted at the cursor (may contain {{}} placeholder). */
  latex: string;
  /** Lowest stage at which this symbol appears. */
  level: MathLevel;
  category: MathCategory;
  /** Chinese tooltip name. */
  descZh: string;
/**
 * If `caretFromEnd` is set, after inserting `latex` the caret is moved this
 * many chars from the end of the inserted text — used to drop the caret
 * inside the first `{}` of a template. 0 / undefined = caret at end.
 */
caretFromEnd?: number;
}

export const MATH_SYMBOLS: MathSymbol[] = [
  // ── Operators ────────────────────────────────────────────────────────
  { label: "+", latex: "+", level: "elementary", category: "operators", descZh: "加号" },
  { label: "−", latex: "-", level: "elementary", category: "operators", descZh: "减号" },
  { label: "×", latex: "\\times", level: "elementary", category: "operators", descZh: "乘号" },
  { label: "÷", latex: "\\div", level: "elementary", category: "operators", descZh: "除号" },
  { label: "=", latex: "=", level: "elementary", category: "operators", descZh: "等号" },
  { label: "≠", latex: "\\neq", level: "elementary", category: "operators", descZh: "不等号" },
  { label: "≈", latex: "\\approx", level: "elementary", category: "operators", descZh: "约等" },
  { label: ">", latex: ">", level: "elementary", category: "operators", descZh: "大于" },
  { label: "<", latex: "<", level: "elementary", category: "operators", descZh: "小于" },
  { label: "≥", latex: "\\geq", level: "elementary", category: "operators", descZh: "大于等于" },
  { label: "≤", latex: "\\leq", level: "elementary", category: "operators", descZh: "小于等于" },
  { label: "%", latex: "\\%", level: "elementary", category: "operators", descZh: "百分号" },
  { label: "°", latex: "^{\\circ}", level: "elementary", category: "operators", descZh: "度" },
  { label: "·", latex: "\\cdot", level: "middle", category: "operators", descZh: "点乘" },
  { label: "±", latex: "\\pm", level: "middle", category: "operators", descZh: "正负号" },
  { label: "∓", latex: "\\mp", level: "middle", category: "operators", descZh: "负正号" },
  { label: "√", latex: "\\sqrt{}", level: "middle", category: "operators", descZh: "平方根", caretFromEnd: 1 },
  { label: "∛", latex: "\\sqrt[3]{}", level: "middle", category: "operators", descZh: "立方根", caretFromEnd: 1 },
  { label: "×²", latex: "^{2}", level: "middle", category: "operators", descZh: "平方" },
  { label: "×³", latex: "^{3}", level: "middle", category: "operators", descZh: "立方" },
  { label: "∝", latex: "\\propto", level: "high", category: "operators", descZh: "正比于" },
  { label: "≡", latex: "\\equiv", level: "high", category: "operators", descZh: "恒等" },
  { label: "≅", latex: "\\cong", level: "high", category: "operators", descZh: "全等" },
  { label: "∼", latex: "\\sim", level: "middle", category: "operators", descZh: "相似" },
  { label: "log", latex: "\\log", level: "high", category: "operators", descZh: "对数" },
  { label: "ln", latex: "\\ln", level: "high", category: "operators", descZh: "自然对数" },
  { label: "mod", latex: "\\bmod", level: "full", category: "operators", descZh: "取模" },
  { label: "⊕", latex: "\\oplus", level: "full", category: "operators", descZh: "直和" },
  { label: "⊗", latex: "\\otimes", level: "full", category: "operators", descZh: "张量积" },

  // ── Greek letters ────────────────────────────────────────────────────
  { label: "π", latex: "\\pi", level: "elementary", category: "greek", descZh: "圆周率" },
  { label: "α", latex: "\\alpha", level: "middle", category: "greek", descZh: "阿尔法" },
  { label: "β", latex: "\\beta", level: "middle", category: "greek", descZh: "贝塔" },
  { label: "γ", latex: "\\gamma", level: "middle", category: "greek", descZh: "伽马" },
  { label: "δ", latex: "\\delta", level: "middle", category: "greek", descZh: "德尔塔" },
  { label: "ε", latex: "\\varepsilon", level: "middle", category: "greek", descZh: "艾普西龙" },
  { label: "θ", latex: "\\theta", level: "middle", category: "greek", descZh: "西塔" },
  { label: "λ", latex: "\\lambda", level: "middle", category: "greek", descZh: "拉姆达" },
  { label: "μ", latex: "\\mu", level: "middle", category: "greek", descZh: "缪" },
  { label: "ρ", latex: "\\rho", level: "middle", category: "greek", descZh: "柔" },
  { label: "σ", latex: "\\sigma", level: "middle", category: "greek", descZh: "西格马" },
  { label: "φ", latex: "\\varphi", level: "middle", category: "greek", descZh: "斐" },
  { label: "ω", latex: "\\omega", level: "middle", category: "greek", descZh: "欧米伽" },
  { label: "η", latex: "\\eta", level: "high", category: "greek", descZh: "伊塔" },
  { label: "κ", latex: "\\kappa", level: "high", category: "greek", descZh: "卡帕" },
  { label: "ν", latex: "\\nu", level: "high", category: "greek", descZh: "纽" },
  { label: "ξ", latex: "\\xi", level: "high", category: "greek", descZh: "克西" },
  { label: "τ", latex: "\\tau", level: "high", category: "greek", descZh: "陶" },
  { label: "χ", latex: "\\chi", level: "high", category: "greek", descZh: "希" },
  { label: "ψ", latex: "\\psi", level: "high", category: "greek", descZh: "普西" },
  { label: "ζ", latex: "\\zeta", level: "high", category: "greek", descZh: "泽塔" },
  { label: "ι", latex: "\\iota", level: "full", category: "greek", descZh: "约塔" },
  { label: "Γ", latex: "\\Gamma", level: "high", category: "greek", descZh: "大写伽马" },
  { label: "Δ", latex: "\\Delta", level: "high", category: "greek", descZh: "大写德尔塔" },
  { label: "Θ", latex: "\\Theta", level: "high", category: "greek", descZh: "大写西塔" },
  { label: "Λ", latex: "\\Lambda", level: "high", category: "greek", descZh: "大写拉姆达" },
  { label: "Ξ", latex: "\\Xi", level: "full", category: "greek", descZh: "大写克西" },
  { label: "Π", latex: "\\Pi", level: "full", category: "greek", descZh: "大写派" },
  { label: "Σ", latex: "\\Sigma", level: "full", category: "greek", descZh: "大写西格马" },
  { label: "Φ", latex: "\\Phi", level: "full", category: "greek", descZh: "大写斐" },
  { label: "Ψ", latex: "\\Psi", level: "full", category: "greek", descZh: "大写普西" },
  { label: "Ω", latex: "\\Omega", level: "full", category: "greek", descZh: "大写欧米伽" },

  // ── Relations ────────────────────────────────────────────────────────
  { label: "≪", latex: "\\ll", level: "high", category: "relations", descZh: "远小于" },
  { label: "≫", latex: "\\gg", level: "high", category: "relations", descZh: "远大于" },
  { label: "∥", latex: "\\parallel", level: "middle", category: "relations", descZh: "平行" },
  { label: "⟂", latex: "\\perp", level: "middle", category: "relations", descZh: "垂直" },
  { label: "∈", latex: "\\in", level: "middle", category: "sets", descZh: "属于" },
  { label: "∉", latex: "\\notin", level: "high", category: "sets", descZh: "不属于" },
  { label: "∋", latex: "\\ni", level: "high", category: "sets", descZh: "包含于(反向)" },
  { label: "⊂", latex: "\\subset", level: "high", category: "sets", descZh: "真子集" },
  { label: "⊃", latex: "\\supset", level: "high", category: "sets", descZh: "真包含" },
  { label: "⊆", latex: "\\subseteq", level: "high", category: "sets", descZh: "子集" },
  { label: "⊇", latex: "\\supseteq", level: "high", category: "sets", descZh: "包含" },
  { label: "∪", latex: "\\cup", level: "high", category: "sets", descZh: "并集" },
  { label: "∩", latex: "\\cap", level: "high", category: "sets", descZh: "交集" },
  { label: "∅", latex: "\\emptyset", level: "high", category: "sets", descZh: "空集" },
  { label: "∀", latex: "\\forall", level: "high", category: "sets", descZh: "任意" },
  { label: "∃", latex: "\\exists", level: "high", category: "sets", descZh: "存在" },
  { label: "ℕ", latex: "\\mathbb{N}", level: "high", category: "sets", descZh: "自然数集" },
  { label: "ℤ", latex: "\\mathbb{Z}", level: "high", category: "sets", descZh: "整数集" },
  { label: "ℚ", latex: "\\mathbb{Q}", level: "high", category: "sets", descZh: "有理数集" },
  { label: "ℝ", latex: "\\mathbb{R}", level: "high", category: "sets", descZh: "实数集" },
  { label: "ℂ", latex: "\\mathbb{C}", level: "high", category: "sets", descZh: "复数集" },
  { label: "∁", latex: "\\complement", level: "full", category: "sets", descZh: "补集" },

  // ── Arrows ───────────────────────────────────────────────────────────
  { label: "→", latex: "\\to", level: "middle", category: "arrows", descZh: "趋于" },
  { label: "←", latex: "\\leftarrow", level: "high", category: "arrows", descZh: "左箭头" },
  { label: "↔", latex: "\\leftrightarrow", level: "high", category: "arrows", descZh: "双向箭头" },
  { label: "⇒", latex: "\\Rightarrow", level: "high", category: "arrows", descZh: "推出" },
  { label: "⇐", latex: "\\Leftarrow", level: "high", category: "arrows", descZh: "左双箭头" },
  { label: "⇔", latex: "\\Leftrightarrow", level: "high", category: "arrows", descZh: "等价" },
  { label: "↑", latex: "\\uparrow", level: "high", category: "arrows", descZh: "上箭头" },
  { label: "↓", latex: "\\downarrow", level: "high", category: "arrows", descZh: "下箭头" },
  { label: "↦", latex: "\\mapsto", level: "full", category: "arrows", descZh: "映射到" },
  { label: "⟶", latex: "\\longrightarrow", level: "full", category: "arrows", descZh: "长右箭头" },

  // ── Calculus ─────────────────────────────────────────────────────────
  { label: "∞", latex: "\\infty", level: "high", category: "calculus", descZh: "无穷" },
  { label: "lim", latex: "\\lim_{x \\to }", level: "high", category: "calculus", descZh: "极限", caretFromEnd: 1 },
  { label: "∂", latex: "\\partial", level: "high", category: "calculus", descZh: "偏导" },
  { label: "∇", latex: "\\nabla", level: "high", category: "calculus", descZh: "梯度算子" },
  { label: "∫", latex: "\\int", level: "high", category: "calculus", descZh: "积分" },
  { label: "sup", latex: "\\sup", level: "high", category: "calculus", descZh: "上确界" },
  { label: "inf", latex: "\\inf", level: "high", category: "calculus", descZh: "下确界" },
  { label: "∑", latex: "\\sum", level: "high", category: "calculus", descZh: "求和" },
  { label: "∏", latex: "\\prod", level: "high", category: "calculus", descZh: "求积" },
  { label: "∬", latex: "\\iint", level: "full", category: "calculus", descZh: "二重积分" },
  { label: "∭", latex: "\\iiint", level: "full", category: "calculus", descZh: "三重积分" },
  { label: "∮", latex: "\\oint", level: "full", category: "calculus", descZh: "环路积分" },
  { label: "∯", latex: "\\oiint", level: "full", category: "calculus", descZh: "闭合面积分" },
  { label: "∰", latex: "\\oiiint", level: "full", category: "calculus", descZh: "闭合体积分" },

  // ── Brackets ─────────────────────────────────────────────────────────
  { label: "⟨⟩", latex: "\\langle \\rangle", level: "high", category: "brackets", descZh: "尖括号" },
  { label: "⌈⌉", latex: "\\lceil \\rceil", level: "full", category: "brackets", descZh: "上取整" },
  { label: "⌊⌋", latex: "\\lfloor \\rfloor", level: "full", category: "brackets", descZh: "下取整" },

  // ── Templates ────────────────────────────────────────────────────────
  { label: "frac", latex: "\\frac{}{}", level: "elementary", category: "templates", descZh: "分数", caretFromEnd: 3 },
  { label: "√", latex: "\\sqrt{}", level: "middle", category: "templates", descZh: "根式", caretFromEnd: 1 },
  { label: "x²", latex: "^{2}", level: "middle", category: "templates", descZh: "上标平方", caretFromEnd: 0 },
  { label: "xₙ", latex: "_{}", level: "middle", category: "templates", descZh: "下标", caretFromEnd: 1 },
  { label: "x^n", latex: "^{}", level: "middle", category: "templates", descZh: "上标", caretFromEnd: 1 },
  { label: "vec", latex: "\\vec{}", level: "high", category: "templates", descZh: "向量", caretFromEnd: 1 },
  { label: "hat", latex: "\\hat{}", level: "high", category: "templates", descZh: "帽子", caretFromEnd: 1 },
  { label: "bar", latex: "\\bar{}", level: "high", category: "templates", descZh: "上划线", caretFromEnd: 1 },
  { label: "abs", latex: "\\left| \\right|", level: "high", category: "templates", descZh: "绝对值", caretFromEnd: 8 },
  { label: "int", latex: "\\int_{}^{}", level: "high", category: "templates", descZh: "定积分", caretFromEnd: 3 },
  { label: "sum", latex: "\\sum_{}^{}", level: "high", category: "templates", descZh: "求和", caretFromEnd: 3 },
  { label: "lim", latex: "\\lim_{n \\to }", level: "high", category: "templates", descZh: "极限", caretFromEnd: 1 },
  { label: "pmat", latex: "\\begin{pmatrix} & \\\\ & \\end{pmatrix}", level: "high", category: "templates", descZh: "矩阵", caretFromEnd: 26 },
  { label: "cases", latex: "\\begin{cases} \\\\ \\end{cases}", level: "full", category: "templates", descZh: "分段函数", caretFromEnd: 14 },
  { label: "bmat", latex: "\\begin{bmatrix} & \\\\ & \\end{bmatrix}", level: "full", category: "templates", descZh: "方括号矩阵", caretFromEnd: 27 },
];

/**
 * Symbols visible at a given stage (cumulative: a stage includes all symbols
 * whose `level` is at or below it).
 */
export function filterSymbolsByLevel(level: MathLevel): MathSymbol[] {
  const idx = MATH_LEVELS.indexOf(level);
  return MATH_SYMBOLS.filter((s) => MATH_LEVELS.indexOf(s.level) <= idx);
}

/**
 * Categories that have at least one symbol at the given stage — used to hide
 * empty tabs (e.g. "Calculus" disappears for elementary learners).
 */
export function getAvailableCategories(level: MathLevel): MathCategory[] {
  const order: MathCategory[] = [
    "operators",
    "greek",
    "relations",
    "sets",
    "arrows",
    "calculus",
    "brackets",
    "templates",
  ];
  const present = new Set(filterSymbolsByLevel(level).map((s) => s.category));
  return order.filter((c) => present.has(c));
}

/**
 * Group symbols by category for a given stage. Returns a stable-order map
 * suitable for rendering tabbed grids.
 */
export function groupSymbolsByCategory(
  level: MathLevel,
): Record<MathCategory, MathSymbol[]> {
  const cats = getAvailableCategories(level);
  const out = {} as Record<MathCategory, MathSymbol[]>;
  for (const c of cats) {
    out[c] = filterSymbolsByLevel(level).filter((s) => s.category === c);
  }
  return out;
}

/**
 * Coerce an arbitrary stored value into a valid MathLevel, falling back to
 * the provided default (or "full") when missing/invalid. Defends against
 * legacy settings files or hand-edited JSON.
 */
export function normalizeMathLevel(
  value: unknown,
  fallback: MathLevel = "full",
): MathLevel {
  if (typeof value === "string" && (MATH_LEVELS as readonly string[]).includes(value)) {
    return value as MathLevel;
  }
  return fallback;
}

// ── Bare-LaTeX wrapping for sending ─────────────────────────────────────

/**
 * Wrap bare LaTeX fragments (as inserted by the math symbol palette) in
 * inline math delimiters (`$...$`) so the MarkdownRenderer can detect and
 * render them.
 *
 * The palette inserts *bare* LaTeX — e.g. `x^{2}`, `\frac{}{}`, `\times` —
 * with no `$` delimiters. Plain-text user bubbles (and even the markdown
 * renderer) cannot know those tokens are math, so before sending we upgrade
 * fragments that contain a LaTeX "signal" into properly delimited math.
 *
 * Rules (intentionally conservative, to avoid mangling ordinary prose):
 *  - Segments already inside `$...$`, `$$...$$`, `\(...\)` or `\[...\]` are
 *    left untouched.
 *  - A segment is wrapped only if it contains a real LaTeX signal:
 *      * a backslash command (`\times`, `\frac`, `\pi`, …), or
 *      * a superscript/subscript group (`^{...}` / `_{...}`).
 *  - The wrapped span is the maximal run of "math-safe" characters
 *    (letters, digits, common operators, braces, `^`, `_`, backslash, space)
 *    that contains the signal — so surrounding Chinese/prose text is not
 *    accidentally pulled into the formula.
 *  - Lone backslashes or carets that aren't part of a command/group pass
 *    through untouched.
 */
export function wrapBareLatexForSending(text: string): string {
  // Split into already-delimited math spans (odd indices) and everything
  // else (even indices). Only transform the non-math segments.
  const mathSpan =
    /(\$\$[\s\S]*?\$\$|\$[^$\n]+\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])/g;
  const segments = text.split(mathSpan);

  const latexSignal = /(?:\\[a-zA-Z]+|[\^_]\{)/;
  const safeChar = /[A-Za-z0-9\s+\-*/=<>().,{}^_\\]/;

  // Shrink a math-safe run so leading/trailing whitespace stays outside the
  // `$...$` delimiters (e.g. `化简 \frac{1}{2}` → `化简 $\frac{1}{2}$`,
  // not `化简$ \frac{1}{2} $`).
  const trimEdges = (seg: string, start: number, end: number): [number, number] => {
    while (start < end && /\s/.test(seg[start])) start++;
    while (end > start && /\s/.test(seg[end - 1])) end--;
    return [start, end];
  };

  return segments
    .map((seg, i) => {
      // Odd indices are the matched already-delimited math spans — keep.
      if (i % 2 === 1) return seg;
      if (!latexSignal.test(seg)) return seg;

      // Locate every signal in the *original* string, expand each to its
      // contiguous math-safe run, drop runs fully inside a larger one, then
      // insert `$` from the end backwards so earlier indices stay valid (the
      // string mutates as we wrap).
      const runs: Array<[number, number]> = [];
      const signalRe = new RegExp(latexSignal.source, "g");
      let m: RegExpExecArray | null;
      while ((m = signalRe.exec(seg)) !== null) {
        const idx = m.index;
        let start = idx;
        while (start > 0 && safeChar.test(seg[start - 1])) start--;
        let end = idx + m[0].length;
        while (end < seg.length && safeChar.test(seg[end])) end++;
        [start, end] = trimEdges(seg, start, end);
        if (start >= end) continue;
        if (runs.some(([s, e]) => start >= s && end <= e)) continue; // nested
        runs.push([start, end]);
      }
      let out = seg;
      for (let k = runs.length - 1; k >= 0; k--) {
        const [start, end] = runs[k];
        out =
          out.slice(0, start) +
          "$" +
          out.slice(start, end) +
          "$" +
          out.slice(end);
      }
      return out;
    })
    .join("");
}
