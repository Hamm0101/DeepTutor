"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { useMathInputLevel } from "@/hooks/useMathInputLevel";
import {
  MATH_CATEGORY_LABELS,
  MATH_LEVEL_LABELS,
  MATH_LEVELS,
  getAvailableCategories,
  groupSymbolsByCategory,
  type MathCategory,
  type MathLevel,
  type MathSymbol,
} from "@/lib/math-symbols";

interface MathSymbolPaletteProps {
  /**
   * Called with the LaTeX to insert and (for templates) how many chars from
   * the end of that LaTeX the caret should land. The parent owns the
   * textarea, so it performs the actual insertion.
   */
  onInsert: (latex: string, caretFromEnd?: number) => void;
}

/**
 * Popover panel for the chat composer's math symbol picker.
 *
 * The visible symbol set is filtered by the user's learning stage
 * (`math_input_level`), which is persisted in UI settings — changing the
 * stage here writes through immediately and is remembered across sessions.
 * Categories with no symbols at the current stage are hidden so the palette
 * stays uncluttered for younger learners.
 */
export default function MathSymbolPalette({ onInsert }: MathSymbolPaletteProps) {
  const { t, i18n } = useTranslation();
  const { level, setLevel } = useMathInputLevel();
  const isZh = i18n.language?.startsWith("zh");

  const categories = useMemo(
    () => getAvailableCategories(level as MathLevel),
    [level],
  );
  const grouped = useMemo(
    () => groupSymbolsByCategory(level as MathLevel),
    [level],
  );

  // Track the selected tab. If the stage changes and the selected tab no
  // longer exists (e.g. dropping from "high" to "elementary" removes the
  // "calculus" tab), fall back to the first available category at render time
  // without an effect round-trip.
  const [activeCat, setActiveCat] = useState<MathCategory>(categories[0]);
  const effectiveActiveCat = categories.includes(activeCat)
    ? activeCat
    : categories[0];

  const symbols: MathSymbol[] = grouped[effectiveActiveCat] ?? [];

  const labelForLevel = (lv: MathLevel) => {
    const meta = MATH_LEVEL_LABELS[lv];
    return isZh ? meta.zh : meta.en;
  };
  const labelForCat = (c: MathCategory) => {
    const meta = MATH_CATEGORY_LABELS[c];
    return isZh ? meta.zh : meta.en;
  };

  return (
    <div
      role="dialog"
      aria-label={t("Math symbols")}
      className="w-[340px] overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--popover)] shadow-lg backdrop-blur-md"
    >
      {/* Stage selector — persisted to UI settings on click. */}
      <div className="flex items-center gap-1 border-b border-[var(--border)]/60 px-2 py-1.5">
        {MATH_LEVELS.map((lv) => {
          const active = lv === level;
          return (
            <button
              key={lv}
              type="button"
              onClick={() => setLevel(lv)}
              className={`flex-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                active
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/55 hover:text-[var(--foreground)]"
              }`}
            >
              <span className="mr-1">{MATH_LEVEL_LABELS[lv].emoji}</span>
              {labelForLevel(lv)}
            </button>
          );
        })}
      </div>

      {/* Category tabs — only those with symbols at this stage. */}
      <div className="flex items-center gap-0.5 overflow-x-auto border-b border-[var(--border)]/60 px-1.5 py-1">
        {categories.map((c) => {
          const active = c === effectiveActiveCat;
          return (
            <button
              key={c}
              type="button"
              onClick={() => setActiveCat(c)}
              className={`shrink-0 rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                active
                  ? "bg-[var(--muted)] text-[var(--foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/40 hover:text-[var(--foreground)]"
              }`}
            >
              {labelForCat(c)}
            </button>
          );
        })}
      </div>

      {/* Symbol grid. */}
      <div className="max-h-[260px] overflow-y-auto p-2">
        <div className="grid grid-cols-8 gap-1">
          {symbols.map((sym, idx) => (
            <button
              key={`${sym.latex}-${idx}`}
              type="button"
              title={sym.descZh}
              onClick={() => onInsert(sym.latex, sym.caretFromEnd)}
              className="flex h-9 items-center justify-center rounded-md border border-transparent text-[15px] leading-none text-[var(--foreground)] transition-colors hover:border-[var(--border)] hover:bg-[var(--muted)]/55 active:scale-95"
            >
              {/* Templates show a verb (frac/vec…) rather than a glyph so
                  they're distinguishable from raw operators. */}
              {sym.category === "templates" ? (
                <span className="text-[11px] font-medium text-[var(--muted-foreground)]">
                  {sym.label}
                </span>
              ) : (
                sym.label
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Footer hint. */}
      <div className="border-t border-[var(--border)]/60 px-3 py-1.5 text-[10px] text-[var(--muted-foreground)]">
        {isZh
          ? "点击插入 · Ctrl+Shift+M 行内公式 · Ctrl+Shift+D 块级公式"
          : "Click to insert · Ctrl+Shift+M inline · Ctrl+Shift+D block"}
      </div>
    </div>
  );
}
