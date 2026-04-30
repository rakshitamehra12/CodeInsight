from __future__ import annotations

import ast
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Generator, Literal

from flask import Flask, request, jsonify, Response
from flask_cors import CORS


Severity = Literal["error", "warning", "notice"]


@dataclass
class Diagnostic:
    severity: Severity
    code: str
    summary: str
    line: int | str
    detail: str
    remedy: str
    analogy: str = ""
    tip: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

_DB_PATH = "codehistory.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT    NOT NULL,
    diagnostics TEXT    NOT NULL,
    recorded_at TEXT    NOT NULL
);
"""


@contextmanager
def _db_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _bootstrap_db() -> None:
    with _db_conn() as conn:
        conn.executescript(_SCHEMA)


class AnalysisRepository:
    """Thin persistence facade; keeps SQL out of service logic."""

    @staticmethod
    def persist(source: str, diagnostics: list[Diagnostic]) -> None:
        payload = json.dumps([d.to_dict() for d in diagnostics])
        timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(datetime, 'UTC') else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with _db_conn() as cinn:
            conn.execute(
                "INSERT INTO analysis_runs (source_code, diagnostics, recorded_at) VALUES (?,?,?)",
                (source, payload, timestamp),
            )

    @staticmethod
    def fetch_recent(limit: int = 50) -> list[dict]:
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT source_code, recorded_at FROM analysis_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"source_code": r["source_code"], "recorded_at": r["recorded_at"]} for r in rows]


@dataclass
class LineContext:
    number: int
    raw: str
    stripped: str
    indent: int


def _build_line_contexts(source: str) -> list[LineContext]:
    contexts = []
    for i, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        contexts.append(LineContext(i, raw, stripped, indent))
    return contexts


class Rule:
    code: str = ""

    def evaluate(self, ctx: LineContext, prev: LineContext | None) -> Diagnostic | None:
        raise NotImplementedError


class MissingColonRule(Rule):
    code = "E101"
    _BLOCK_OPENERS = ("if ", "elif ", "else", "for ", "while ", "def ", "class ", "with ", "try", "except", "finally")

    def evaluate(self, ctx: LineContext, prev: LineContext | None) -> Diagnostic | None:
        if any(ctx.stripped.startswith(kw) for kw in self._BLOCK_OPENERS):
            if not ctx.stripped.endswith(":"):
                return Diagnostic(
                    severity="error",
                    code=self.code,
                    summary="Block opener missing colon",
                    line=ctx.number,
                    detail="Python delimits blocks with ':', not braces. Without it the interpreter treats everything below as continuation of the same expression.",
                    remedy="Append ':' at the end of this line.",
                )
        return None


class IndentationLeapRule(Rule):
    code = "W201"

    def evaluate(self, ctx: LineContext, prev: LineContext | None) -> Diagnostic | None:
        if prev and (ctx.indent - prev.indent) > 4:
            return Diagnostic(
                severity="warning",
                code=self.code,
                summary="Indentation jump is too large",
                line=ctx.number,
                detail=f"Jumped {ctx.indent - prev.indent} spaces in one step; standard Python uses 4 per level.",
                remedy="Reduce indentation to align with the enclosing block.",
            )
        return None


class BlockBodyRule(Rule):
    code = "E102"

    def evaluate(self, ctx: LineContext, prev: LineContext | None) -> Diagnostic | None:
        if prev and prev.stripped.endswith(":"):
            if ctx.indent <= prev.indent:
                return Diagnostic(
                    severity="error",
                    code=self.code,
                    summary="Expected indented block body",
                    line=ctx.number,
                    detail="A colon-terminated statement must be followed by at least one indented line.",
                    remedy="Indent this line by 4 spaces relative to the opener above.",
                )
        return None


class ElseAlignmentRule(Rule):
    code = "E103"

    def evaluate(self, ctx: LineContext, prev: LineContext | None) -> Diagnostic | None:
        if ctx.stripped.startswith(("elif", "else")) and prev:
            if ctx.indent != prev.indent:
                return Diagnostic(
                    severity="error",
                    code=self.code,
                    summary="elif/else misaligned with its if",
                    line=ctx.number,
                    detail="elif/else must share the exact indentation level of the matching 'if' to form a coherent branch.",
                    remedy="Adjust this line's indentation to match the 'if' statement.",
                )
        return None


class UnguardedInfiniteLoopRule(Rule):
    code = "W301"

    def evaluate(self, ctx: LineContext, prev: LineContext | None) -> Diagnostic | None:
        if ctx.stripped.startswith("while") and ("True" in ctx.stripped or "1 ==" in ctx.stripped or "== 1" in ctx.stripped):
            return Diagnostic(
                severity="warning",
                code=self.code,
                summary="while-True loop without visible exit guard",
                line=ctx.number,
                detail="The loop condition is always truthy. Without a 'break' or a mutating variable the loop runs forever.",
                remedy="Add a 'break', a sentinel variable, or a bounded condition.",
            )
        return None


class RulePipeline:
    _registry: list[Rule] = [
        MissingColonRule(),
        IndentationLeapRule(),
        BlockBodyRule(),
        ElseAlignmentRule(),
        UnguardedInfiniteLoopRule(),
    ]

    def run(self, source: str) -> list[Diagnostic]:
        contexts = _build_line_contexts(source)
        findings: list[Diagnostic] = []
        for i, ctx in enumerate(contexts):
            prev = contexts[i - 1] if i > 0 else None
            for rule in self._registry:
                result = rule.evaluate(ctx, prev)
                if result:
                    findings.append(result)
        return findings


_BUILTINS = frozenset(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__))


class _ASTInspector(ast.NodeVisitor):
    def __init__(self) -> None:
        self._assigned: dict[str, int] = {}
        self._used: set[str] = set()
        self.diagnostics: list[Diagnostic] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._assigned.setdefault(target.id, node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._assigned.setdefault(node.target.id, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._assigned.setdefault(node.target.id, node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._used.add(node.id)
            if node.id not in self._assigned and node.id not in _BUILTINS:
                self.diagnostics.append(Diagnostic(
                    severity="error",
                    code="E201",
                    summary=f"Name '{node.id}' referenced before assignment",
                    line=node.lineno,
                    detail="The interpreter has no value bound to this name at the point of use.",
                    remedy=f"Assign a value to '{node.id}' before this line.",
                ))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Div):
            if isinstance(node.right, (ast.Constant, ast.Num)):
                val = node.right.value if isinstance(node.right, ast.Constant) else node.right.n
                if val == 0:
                    self.diagnostics.append(Diagnostic(
                        severity="error",
                        code="E202",
                        summary="Division by the literal zero",
                        line=node.lineno,
                        detail="Dividing by zero is mathematically undefined and raises ZeroDivisionError at runtime.",
                        remedy="Replace the denominator with a non-zero value or guard with an if-check.",
                    ))
        self.generic_visit(node)

    def finalise(self) -> None:
        orphans = set(self._assigned) - self._used
        for name in sorted(orphans):
            self.diagnostics.append(Diagnostic(
                severity="warning",
                code="W401",
                summary=f"Variable '{name}' is assigned but never read",
                line=self._assigned[name],
                detail="The assignment consumes memory and adds noise without contributing to program output.",
                remedy=f"Either use '{name}' in subsequent logic, or remove the assignment entirely.",
            ))


class ASTInspectionService:
    def analyse(self, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        inspector = _ASTInspector()
        inspector.visit(tree)
        inspector.finalise()
        return inspector.diagnostics

class SyntaxCheckService:
    def analyse(self, source: str) -> list[Diagnostic]:
        try:
            compile(source, "<input>", "exec")
            return []
        except SyntaxError as exc:
            return [Diagnostic(
                severity="error",
                code="E001",
                summary="Syntax error — file cannot be compiled",
                line=exc.lineno or "?",
                detail=exc.msg or "The Python parser rejected this file.",
                remedy="Resolve the syntax issue at the indicated line before running the file.",
            )]


_ENRICHMENT_MAP: dict[str, tuple[str, str]] = {
    "E001": (
        "Think of it like handing someone an instruction sheet with a sentence that starts but never finishes — the reader simply cannot proceed.",
        "Fix syntax errors from top to bottom; a single early mistake can cascade into dozens of misleading secondary errors.",
    ),
    "E101": (
        "A colon at the end of a block opener is Python's equivalent of an opening brace in other languages — it signals 'what follows belongs inside me'.",
        "Many editors highlight missing colons in real time. If yours does not, consider enabling a linter plugin.",
    ),
    "E102": (
        "Opening a block and writing no body is like announcing a speech and walking off stage — the audience (interpreter) has nothing to process.",
        "Use 'pass' as a temporary placeholder body when you intend to fill in logic later.",
    ),
    "E103": (
        "Misaligned elif/else is like answering a question that belongs to a different conversation — Python links branches by column position, not proximity.",
        "If your editor supports column rulers or indent guides, enable them; misalignment becomes visually obvious.",
    ),
    "E201": (
        "Referencing an unassigned name is like citing a page number in a book you have not yet written — there is nothing to look up.",
        "Initialise variables at the top of their scope (x = 0 or x = None) so they always exist before conditional branches might use them.",
    ),
    "E202": (
        "Dividing by zero is the one arithmetic operation with no valid answer — mathematicians and computers alike refuse it.",
        "Guard divisions with 'if denominator != 0:' or use a try/except ZeroDivisionError block for resilient code.",
    ),
    "W201": (
        "An unexpected indentation leap is like skipping three steps on a staircase — structurally possible but disorienting to anyone following.",
        "Configure your editor to insert exactly 4 spaces per Tab key press; it eliminates accidental jumps.",
    ),
    "W301": (
        "An always-true loop condition is like a revolving door with no exit handle — movement happens endlessly but no one gets out.",
        "Ensure the variable driving the loop mutates each iteration (i += 1) or that a 'break' statement is reachable within the body.",
    ),
    "W401": (
        "An unused variable is a reserved seat that no guest fills — it occupies space in both memory and the reader's attention.",
        "Name intentionally discarded values '_' (single underscore) to signal that the value is deliberately ignored.",
    ),
}


class DiagnosticEnricher:
    def enrich(self, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
        for d in diagnostics:
            if d.code in _ENRICHMENT_MAP:
                d.analogy, d.tip = _ENRICHMENT_MAP[d.code]
        return diagnostics



class AnalysisOrchestrator:
    def __init__(self) -> None:
        self._rule_pipeline = RulePipeline()
        self._syntax_svc    = SyntaxCheckService()
        self._ast_svc       = ASTInspectionService()
        self._enricher      = DiagnosticEnricher()
        self._repo          = AnalysisRepository()

    def run(self, source: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []

        diagnostics.extend(self._syntax_svc.analyse(source))
        diagnostics.extend(self._rule_pipeline.run(source))
        diagnostics.extend(self._ast_svc.analyse(source))

        self._enricher.enrich(diagnostics)

        if not diagnostics:
            diagnostics.append(Diagnostic(
                severity="notice",
                code="I001",
                summary="No issues detected",
                line="—",
                detail="All automated checks passed. The code is structurally sound at the level of static analysis.",
                remedy="Consider running tests to validate runtime behaviour as well.",
            ))

        self._repo.persist(source, diagnostics)
        return diagnostics



class AIExplanationService:
    """
    Calls the LLM once per diagnostic to avoid the model copy-pasting
    the first explanation across all issues. Each call is isolated so
    the weak model only has to focus on one issue at a time.
    Intentionally kept separate from the core analysis pipeline —
    it never alters, reorders, or replaces the original findings.
    """

    _OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    _MODEL          = "google/gemma-3-4b-it:free"

    def _build_prompt(self, source: str, diagnostic: dict) -> str:
        trimmed = "\n".join(source.splitlines()[:50])
        return (
            "You are a Python mentor helping a beginner understand a single code issue.\n"
            "Given the source code and ONE diagnostic, write a friendly 2-3 sentence explanation.\n"
            "Return ONLY a JSON object with a single key 'explanation'. No preamble, no markdown fences.\n\n"
            f"SOURCE CODE:\n{trimmed}\n\n"
            f"DIAGNOSTIC: [{diagnostic['code']}] Line {diagnostic['line']}: {diagnostic['summary']}\n"
            f"Detail: {diagnostic['detail']}"
        )

    def _call_once(self, source: str, diagnostic: dict, api_key: str) -> str | None:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "model": self._MODEL,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": self._build_prompt(source, diagnostic)}],
        }).encode()

        req = urllib.request.Request(
            self._OPENROUTER_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter returned {exc.code}: {error_body}") from exc

        raw_text = body["choices"][0]["message"]["content"].strip()

        # Strip accidental markdown fences just in case
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            return json.loads(raw_text).get("explanation")
        except Exception:
            # Model returned something unparseable — skip this card silently
            return None

    def explain(self, source: str, diagnostics: list[dict]) -> list[dict]:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is not set.")

        results = []
        for d in diagnostics:
            try:
                explanation = self._call_once(source, d, api_key)
                if explanation:  # skip card silently if None
                    results.append({
                        "code": d["code"],
                        "line": d["line"],
                        "explanation": explanation,
                    })
            except RuntimeError:
                # Re-raise auth/network failures so the route can surface them
                raise
            except Exception:
                # Any other per-diagnostic failure — skip silently, continue
                continue

        return results


def create_app() -> Flask:
    _bootstrap_db()

    app = Flask(__name__)
    CORS(app)

    orchestrator  = AnalysisOrchestrator()
    repo          = AnalysisRepository()
    ai_explainer  = AIExplanationService()

    @app.route("/api/analyse", methods=["POST"])
    def analyse() -> tuple[Response, int] | Response:
        payload = request.get_json(silent=True) or {}
        source = payload.get("code", "").strip()

        if not source:
            return jsonify({"error": "Request body must contain a non-empty 'code' field."}), 400

        try:
            results = orchestrator.run(source)
            return jsonify({"diagnostics": [d.to_dict() for d in results]})
        except Exception as exc:
            return jsonify({"error": "Internal analysis failure.", "detail": str(exc)}), 500

    @app.route("/api/explain", methods=["POST"])
    def explain() -> tuple[Response, int] | Response:
        """
        Optional AI enhancement layer. Accepts the original source and the
        diagnostics already produced by /api/analyse, calls the LLM once per
        diagnostic so each card gets a unique explanation, then returns results
        without touching the canonical analysis.
        """
        payload = request.get_json(silent=True) or {}
        source      = payload.get("code", "").strip()
        diagnostics = payload.get("diagnostics", [])

        if not source:
            return jsonify({"error": "Missing 'code' field."}), 400
        if not diagnostics:
            return jsonify({"error": "Missing 'diagnostics' field."}), 400

        try:
            explanations = ai_explainer.explain(source, diagnostics)
            return jsonify({"explanations": explanations})
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return jsonify({"error": "AI explanation failed.", "detail": str(exc)}), 500

    @app.route("/api/history", methods=["GET"])
    def history() -> Response:
        return jsonify(repo.fetch_recent())

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
