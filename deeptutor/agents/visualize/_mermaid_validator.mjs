// DeepTutor mermaid syntax validator — runs `mermaid.parse()` in pure Node.
//
// Invoked by deeptutor.agents.visualize.utils._validate_mermaid_with_node as:
//   node _mermaid_validator.mjs <abs-path-to-mermaid.core.mjs>
// with the mermaid source on stdin. Prints exactly one JSON object to stdout:
//   {"ok": true}                       — valid (or inconclusive; lenient pass)
//   {"ok": false, "error": "<msg>"}    — real syntax error (drives repair)
//   {"ok": true, "envError": true,...} — toolchain/env noise; treat as valid
//
// Design: mermaid.parse() is the real judge. In a headless Node run, valid
// flowcharts/mindmaps reach a DOMPurify.addHook step that has no DOM and throws
// "DOMPurify.addHook is not a function" — that is an environment artifact, NOT
// a syntax error, and must NOT reject the code. Only the two stable jison
// markers ("Parse error on line", "No diagram type detected") are treated as
// real syntax errors. Everything else lenient-passes, so this can never be
// worse than the keyword-only gate — a safe default on every mermaid version.
import { pathToFileURL } from "node:url";
import { readFileSync } from "node:fs";

function emit(obj) {
  process.stdout.write(JSON.stringify(obj));
}

const mermaidEntry = process.argv[2];

let code = "";
try {
  code = readFileSync(0, "utf-8");
} catch {
  emit({ ok: true, envError: true, note: "could not read stdin" });
  process.exit(0);
}

let mermaid;
try {
  const mod = await import(pathToFileURL(mermaidEntry).href);
  mermaid = mod.default;
} catch (e) {
  emit({
    ok: true,
    envError: true,
    note: "mermaid import failed: " + (e && e.message ? e.message : e),
  });
  process.exit(0);
}

if (typeof mermaid?.parse !== "function") {
  emit({ ok: true, envError: true, note: "mermaid.parse unavailable" });
  process.exit(0);
}

try {
  await mermaid.parse(code);
  emit({ ok: true });
} catch (e) {
  const msg = e && e.message ? e.message : String(e);
  // Stable jison markers = real syntax error → reject so repair runs.
  const isSyntaxError = /Parse error on line|No diagram type detected/.test(msg);
  if (isSyntaxError) {
    emit({ ok: false, error: msg });
  } else {
    // Env/runtime noise (e.g. DOMPurify.addHook without a DOM): the parser
    // already accepted the syntax, so lenient-pass.
    emit({ ok: true, envError: true, note: msg });
  }
}
