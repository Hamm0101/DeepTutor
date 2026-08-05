"""Regression tests for deeptutor.agents.visualize.utils.validate_visualization.

Covers the deterministic local validators (svg / chartjs / html / mermaid) and
the opportunistic Node-based mermaid syntax check added to catch LLM syntax
mistakes before they are baked into a book figure.
"""

from __future__ import annotations

import pytest

from deeptutor.agents.visualize import utils as viz_utils
from deeptutor.agents.visualize.utils import validate_visualization


@pytest.fixture(autouse=True)
def _clear_mermaid_cache() -> None:
    """Reset the mermaid toolchain probe cache between tests."""
    viz_utils._MERMAID_TOOLCHAIN_CACHE.clear()


# Real Node + mermaid is only present in source checkouts (web/node_modules).
# The deep-parse tests skip gracefully everywhere else.
_HAS_NODE_MERMAID = viz_utils._mermaid_toolchain() is not None


# --- SVG --------------------------------------------------------------------
def test_svg_valid() -> None:
    ok, err = validate_visualization(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>', "svg"
    )
    assert ok and err == ""


def test_svg_missing_root_tag() -> None:
    ok, _ = validate_visualization("<div></div>", "svg")
    assert not ok


def test_svg_malformed_xml() -> None:
    ok, err = validate_visualization("<svg><rect></svg>", "svg")
    assert not ok
    assert "well-formed" in err


def test_svg_missing_viewbox() -> None:
    ok, err = validate_visualization(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>', "svg"
    )
    assert not ok
    assert "viewBox" in err


# --- Chart.js ---------------------------------------------------------------
def test_chartjs_valid() -> None:
    ok, _ = validate_visualization('{"type":"bar","data":{"labels":[]}}', "chartjs")
    assert ok


def test_chartjs_not_strict_json() -> None:
    ok, _ = validate_visualization("{type: 'bar'}", "chartjs")
    assert not ok


def test_chartjs_missing_required_fields() -> None:
    ok, _ = validate_visualization('{"type":"bar"}', "chartjs")
    assert not ok


# --- HTML -------------------------------------------------------------------
def test_html_valid() -> None:
    ok, _ = validate_visualization("<html><body>hi</body></html>", "html")
    assert ok


def test_html_invalid() -> None:
    ok, _ = validate_visualization("just plain text", "html")
    assert not ok


# --- Mermaid keyword gate (no Node required for the FAIL path) --------------
def test_mermaid_empty_fails() -> None:
    ok, _ = validate_visualization("   ", "mermaid")
    assert not ok


def test_mermaid_bad_first_line_fails() -> None:
    ok, _ = validate_visualization("hello world\nA-->B", "mermaid")
    assert not ok


# --- Mermaid lenient when Node / mermaid unavailable ------------------------
def test_mermaid_lenient_pass_when_toolchain_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    # No Node available → the real parser can't run. A keyword-valid but
    # syntactically broken diagram MUST lenient-pass (never worse than the
    # keyword-only gate) instead of false-rejecting and failing the figure.
    monkeypatch.setattr(viz_utils, "_mermaid_toolchain", lambda: None)
    ok, _ = validate_visualization("flowchart TD\nA[foo(bar)] --> B[End]", "mermaid")
    assert ok


def test_mermaid_frontmatter_passes_keyword_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(viz_utils, "_mermaid_toolchain", lambda: None)
    ok, _ = validate_visualization(
        "---\ntitle: t\n---\nflowchart TD\nA-->B", "mermaid"
    )
    assert ok


# --- Mermaid real parse via Node (integration; skipped without toolchain) ---
@pytest.mark.skipif(not _HAS_NODE_MERMAID, reason="Node + mermaid not installed")
def test_mermaid_real_parse_catches_unescaped_parens() -> None:
    ok, err = validate_visualization("flowchart TD\nA[foo(bar)] --> B[End]", "mermaid")
    assert not ok
    assert "Parse error" in err


@pytest.mark.skipif(not _HAS_NODE_MERMAID, reason="Node + mermaid not installed")
def test_mermaid_real_parse_catches_reserved_word_as_id() -> None:
    ok, _ = validate_visualization("flowchart TD\nend --> A[X]", "mermaid")
    assert not ok


@pytest.mark.skipif(not _HAS_NODE_MERMAID, reason="Node + mermaid not installed")
def test_mermaid_real_parse_catches_unclosed_bracket() -> None:
    ok, _ = validate_visualization("flowchart TD\nA[Start --> B[End]", "mermaid")
    assert not ok


@pytest.mark.skipif(not _HAS_NODE_MERMAID, reason="Node + mermaid not installed")
def test_mermaid_real_parse_accepts_valid_sequence() -> None:
    ok, _ = validate_visualization(
        "sequenceDiagram\nAlice->>Bob: Hello\nBob-->>Alice: Hi", "mermaid"
    )
    assert ok


@pytest.mark.skipif(not _HAS_NODE_MERMAID, reason="Node + mermaid not installed")
def test_mermaid_real_parse_lenient_on_valid_flowchart() -> None:
    # A valid flowchart reaches mermaid's headless DOMPurify step, which throws
    # an environment error (no DOM). That is NOT a syntax error and MUST
    # lenient-pass — this is the spike-confirmed gotcha we must not regress:
    # a valid diagram can never be false-rejected.
    ok, _ = validate_visualization(
        "flowchart TD\nA[Start] --> B{Decision}\nB -->|Yes| C[Do it]", "mermaid"
    )
    assert ok
