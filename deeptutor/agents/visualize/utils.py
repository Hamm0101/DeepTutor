"""Utility helpers for the visualize pipeline."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import defusedxml.ElementTree as ET

from deeptutor.agents._shared.json_output import extract_json_object

_MERMAID_KEYWORDS = (
    "graph",
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram-v2",
    "stateDiagram",
    "erDiagram",
    "gantt",
    "mindmap",
    "pie",
    "journey",
    "gitGraph",
    "timeline",
    "quadrantChart",
    "requirementDiagram",
    "sankey-beta",
    "xychart-beta",
    "block-beta",
    "C4Context",
)


def extract_code_block(text: str, language: str = "") -> str:
    """Extract a fenced code block from LLM output.

    If *language* is given the block must start with that tag;
    otherwise any triple-backtick fence is accepted.
    """
    # Closing fence may sit on the same line as the last content line.
    if language:
        pattern = rf"```{re.escape(language)}\s*\n([\s\S]*?)\n?```"
    else:
        pattern = r"```[A-Za-z]*\s*\n([\s\S]*?)\n?```"
    match = re.search(pattern, text or "", re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return (text or "").strip()


def is_valid_html_document(html: str) -> bool:
    """Heuristic check that *html* looks like a renderable HTML fragment."""
    if not html:
        return False
    lowered = html.lower()
    return "<html" in lowered or "<!doctype" in lowered or "<body" in lowered or "<div" in lowered


def build_fallback_html(*, title: str, summary: str = "", note: str = "") -> str:
    """Build a minimal, self-contained fallback HTML page.

    Used when the model fails to produce a renderable HTML document, so the
    user still gets *something* shown in the iframe instead of a blank panel.
    """
    safe_title = (title or "Visualization").strip() or "Visualization"
    safe_summary = (summary or "").replace("\n", "<br>") or (
        "The model did not return a renderable HTML document."
    )
    safe_note = (note or "").replace("\n", "<br>")

    note_block = (
        f'<div class="note"><strong>Note:</strong><br>{safe_note}</div>' if safe_note else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:linear-gradient(135deg,#F8FAFC 0%,#EFF6FF 100%);
       min-height:100vh;padding:2rem;color:#1E293B;}}
  .card{{max-width:760px;margin:0 auto;background:#fff;border-radius:16px;
        padding:1.75rem 2rem;box-shadow:0 4px 6px -1px rgba(0,0,0,.08);}}
  h1{{color:#1E40AF;font-size:1.4rem;margin-bottom:1rem;}}
  .summary{{line-height:1.7;color:#475569;}}
  .note{{margin-top:1rem;padding:0.9rem 1rem;background:#FEF3C7;
        border-left:4px solid #F59E0B;border-radius:0 8px 8px 0;color:#92400E;}}
</style>
</head>
<body>
  <div class="card">
    <h1>{safe_title}</h1>
    <div class="summary">{safe_summary}</div>
    {note_block}
  </div>
</body>
</html>"""


def _strip_outer_fence(text: str) -> str:
    """Drop a single wrapping triple-backtick fence, if present."""
    stripped = (text or "").strip()
    match = re.match(r"^```[A-Za-z]*\s*\n?([\s\S]*?)\n?```$", stripped)
    return match.group(1).strip() if match else stripped


# --- Mermaid real-syntax validation (opportunistic, zero new deps) ----------
_MERMAID_VALIDATOR_SCRIPT = Path(__file__).parent / "_mermaid_validator.mjs"

# Cache for the (node, mermaid_entry) probe so repeated validations don't
# re-stat. Empty list = not yet probed; one element = probed (may be None).
_MERMAID_TOOLCHAIN_CACHE: list[tuple[str, Path] | None] = []


def _find_mermaid_entry() -> Path | None:
    """Locate the mermaid ESM bundle to import in Node, or ``None``.

    Reuses the frontend's installed mermaid (same version the browser renders,
    so parse semantics match). Checked in priority order: an explicit operator
    override (``DEEPTUTOR_MERMAID_PATH``), then the source-checkout
    ``web/node_modules``. Absent in pip-only installs → ``None`` (lenient).
    """
    override = os.environ.get("DEEPTUTOR_MERMAID_PATH")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
    # utils.py lives at <repo>/deeptutor/agents/visualize/utils.py in a source
    # checkout → parents[3] is the repo root holding web/node_modules.
    candidate = (
        Path(__file__).resolve().parents[3]
        / "web"
        / "node_modules"
        / "mermaid"
        / "dist"
        / "mermaid.core.mjs"
    )
    if candidate.is_file():
        return candidate
    return None


def _mermaid_toolchain() -> tuple[str, Path] | None:
    """Return ``(node_path, mermaid_entry)`` if usable, else ``None`` (cached)."""
    if _MERMAID_TOOLCHAIN_CACHE:
        return _MERMAID_TOOLCHAIN_CACHE[0]
    node = shutil.which("node")
    entry = _find_mermaid_entry() if node else None
    result: tuple[str, Path] | None = (
        (node, entry)
        if (node and entry and _MERMAID_VALIDATOR_SCRIPT.is_file())
        else None
    )
    _MERMAID_TOOLCHAIN_CACHE.append(result)
    return result


def _validate_mermaid_with_node(code: str) -> tuple[bool, str] | None:
    """Run a real ``mermaid.parse()`` check via Node.

    Returns ``(ok, error)`` from the parser, or ``None`` when the Node/mermaid
    toolchain is unavailable, crashed, or timed out — in which case the caller
    falls back to the lenient keyword-only gate (never worse than today).

    Only stable jison markers ("Parse error on line", "No diagram type
    detected") count as real syntax errors; DOMPurify/headless noise is treated
    as valid (see ``_mermaid_validator.mjs``).
    """
    toolchain = _mermaid_toolchain()
    if not toolchain:
        return None
    node, entry = toolchain
    try:
        proc = subprocess.run(
            [node, str(_MERMAID_VALIDATOR_SCRIPT), str(entry)],
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if payload.get("ok"):
        return True, ""
    return False, str(payload.get("error") or "Mermaid syntax error.")


def _validate_mermaid_mindmap_static(text: str) -> tuple[bool, str] | None:
    """Static heuristic check for mindmap bare-line / formula-label errors.

    headless ``mermaid.parse()`` is unreliable for mindmap: every mindmap
    (valid or not) aborts at the DOMPurify step with
    "DOMPurify.addHook is not a function" before jison syntax errors surface,
    so the Node-backed validator lenient-passes broken mindmaps (verified by
    repro: a bare-formula mindmap and a valid mindmap return the *same*
    DOMPurify-noise payload). This pure-Python check catches the two failure
    modes LLMs hit most:

      1. bare text/formula lines — no node ID, no shape delimiter — which
         throw jison ``Expecting 'SPACELINE', 'NL', 'EOF', got 'NODE_DSTART'``
         at browser render time;
      2. node labels containing ``=`` (formulas/equations) — these reliably
         break mindmap parsing regardless of escaping, so they are rejected
         outright with a prompt to switch to flowchart or html.

    Returns ``(ok, error)`` for the first offending line, or ``None`` when the
    source is not a mindmap diagram (so the caller falls back to the keyword
    gate + Node parse path for other diagram types).
    """
    lines = text.splitlines()
    # find the mindmap block: the first non-empty line must be the keyword.
    start: int | None = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            continue
        if s == "mindmap" or s.startswith("mindmap "):
            start = i + 1
            break
        # first non-empty line is a different diagram keyword → not mindmap
        return None
    if start is None:
        return None

    keywords_lower = {k.lower() for k in _MERMAID_KEYWORDS}
    for j in range(start, len(lines)):
        raw = lines[j]
        stripped = raw.strip()
        if not stripped:
            continue
        # a new diagram keyword ends the mindmap block
        if stripped.lower() in keywords_lower:
            break
        # skip comments and class/icon annotations
        if stripped.startswith("%%") or stripped.startswith("::"):
            continue
        # A valid mindmap node line (after stripping indentation) must be
        # `id[label]` / `id(label)` / `id((label))` / ... — an optional ID
        # followed by a shape delimiter. A bare text/formula line like
        # `a² - b² = (a + b)(a - b)  applies: ...` has no ID and no shape
        # delimiter and is the documented NODE_DSTART failure.
        m = re.match(r"^([A-Za-z][\w-]*)?\s*([\[\(\{])", stripped)
        if not m:
            return False, (
                f"mindmap line {j + 1} is a bare text/formula line — every "
                "mindmap node must be `id[label]` (or a shape variant like "
                "`id(label)` / `id((label))`). For formulas/equations use "
                "flowchart or html, not mindmap."
            )
        # The shape-delimited content (label area) must not contain `=`:
        # formulas/equations in mindmap labels reliably break mermaid
        # parsing regardless of quoting/escaping. IDs cannot contain `=`,
        # so any `=` here lives inside the label.
        content = stripped[m.start(2):]
        if "=" in content:
            return False, (
                f"mindmap line {j + 1} label contains '=' (formula/equation). "
                "Formulas in mindmap labels reliably break mermaid parsing. "
                "Use flowchart (e.g. `id1[\"a²-b²=(a+b)(a-b)\"]`) or html "
                "(KaTeX) for formula content."
            )
    return True, ""


def validate_visualization(code: str, render_type: str) -> tuple[bool, str]:
    """Cheap, deterministic, local render-ability check.

    Returns ``(ok, error)``. When ``ok`` is False, ``error`` is a short,
    LLM-actionable message used to drive a single repair pass — none of these
    failures need an LLM call to *discover*. This replaces the generic LLM
    review for the text render types: only when local validation fails do we
    spend a model call (a targeted repair, not an open-ended review).
    """
    text = (code or "").strip()
    if not text:
        return False, "Generated code is empty."

    if render_type == "svg":
        if "<svg" not in text.lower():
            return False, "SVG must contain a root <svg> element."
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            return False, f"SVG is not well-formed XML: {exc}"
        tag = root.tag.split("}")[-1].lower()
        if tag != "svg":
            return False, f"Root element must be <svg>, found <{tag}>."
        # Case-sensitive: SVG only honors the camelCase ``viewBox``; a
        # lowercase ``viewbox`` is ignored by the browser and collapses the
        # figure, so it must NOT pass validation.
        if "viewBox" not in root.attrib:
            return False, (
                "SVG root is missing a viewBox attribute (must be camelCase "
                "`viewBox`, required for responsive scaling)."
            )
        return True, ""

    if render_type == "chartjs":
        candidate = _strip_outer_fence(text)
        try:
            config = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            return False, (
                "Chart.js config must be strict JSON: double-quoted keys, no "
                "function callbacks, no comments, no trailing commas."
            )
        if not isinstance(config, dict):
            return False, "Chart.js config must be a JSON object."
        missing = [field for field in ("type", "data") if field not in config]
        if missing:
            return False, f"Chart.js config is missing required field(s): {', '.join(missing)}."
        return True, ""

    if render_type == "mermaid":
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        # `---` front-matter and `%%{init}` directives are valid lead-ins.
        if not (
            first_line.startswith(_MERMAID_KEYWORDS)
            or first_line.startswith("%%")
            or first_line.startswith("---")
        ):
            return False, (
                "Mermaid code must start with a valid diagram keyword (graph, "
                "flowchart, sequenceDiagram, classDiagram, stateDiagram-v2, "
                "erDiagram, gantt, mindmap, ...)."
            )
        # mindmap-specific static check: headless mermaid.parse() is
        # unreliable for mindmap — DOMPurify noise masks jison errors
        # (verified by repro: a bare-formula mindmap and a valid mindmap
        # both return the same DOMPurify-noise payload), so validate
        # mindmap structure here in pure Python. The static gate catches
        # the known failure modes (bare lines, formula labels); on pass we
        # trust it because Node parse would only lenient-pass anyway.
        mindmap_check = _validate_mermaid_mindmap_static(text)
        if mindmap_check is not None:
            ok, error = mindmap_check
            return (True, "") if ok else (False, error)
        # Keyword gate passed. Opportunistically run a REAL ``mermaid.parse()``
        # check via Node when the toolchain is available: this catches the
        # syntax errors LLMs most often make (unescaped special chars in labels,
        # unclosed brackets, reserved words as node IDs) with a precise,
        # line-numbered message that drives the single repair pass. If Node or
        # the mermaid bundle isn't present, or the check is inconclusive
        # (mermaid's DOMPurify step can't run headless), we lenient-pass — never
        # worse than the keyword-only gate. See ``_mermaid_validator.mjs``.
        deep = _validate_mermaid_with_node(text)
        if deep is None:
            return True, ""
        ok, error = deep
        return (True, "") if ok else (False, error)

    if render_type == "html":
        if is_valid_html_document(text):
            return True, ""
        return False, "Output does not look like a renderable HTML document."

    # Unknown render types are not gated.
    return True, ""


__all__ = [
    "build_fallback_html",
    "extract_code_block",
    "extract_json_object",
    "is_valid_html_document",
    "validate_visualization",
]
