"""Deterministic branch expression helpers (no eval / no I/O).

Supported subset (intentionally small):
  - paths: input.x, outputs.node.y, approvals.node.decision, vars.key
  - literals: true/false/null, numbers, "strings"
  - compare: == != > >= < <=
  - logic: and or not
  - grouping: ( ... )
  - truthiness of a bare path

Edge conditions may also be simple handle labels (yes/no/...) — those are
matched separately by the interpreter.
"""

from __future__ import annotations

import re
from typing import Any, Optional


_TOKEN = re.compile(
    r"""
    \s*
    (
        \b(?:and|or|not|in)\b
      | ==|!=|>=|<=|>|<
      | \[ | \] | ,
      | \( | \)
      | \b(?:true|false|null)\b
      | -?\d+(?:\.\d+)?
      | "(?:[^"\\]|\\.)*"
      | '(?:[^'\\]|\\.)*'
      | [A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*
    )
    """,
    re.VERBOSE,
)


def build_eval_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Flatten interpreter ctx into expression roots."""
    return {
        "input": ctx.get("input") or {},
        "outputs": ctx.get("outputs") or {},
        "approvals": ctx.get("approvals") or {},
        "vars": {
            **(ctx.get("input") or {}),
            **(ctx.get("outputs") or {}),
        },
    }


def resolve_path(path: str, env: dict[str, Any]) -> Any:
    cur: Any = env
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def eval_expression(expr: str, ctx: dict[str, Any]) -> bool:
    """Evaluate a boolean expression against interpreter context."""
    text = (expr or "").strip()
    if not text:
        return True
    env = build_eval_context(ctx)
    tokens = _tokenize(text)
    if not tokens:
        return True
    value, idx = _parse_or(tokens, 0, env)
    if idx != len(tokens):
        # Trailing junk → fail closed (take false / no-match)
        return False
    return bool(value)


def pick_branch_target(
    edges: list[dict[str, Any]],
    ctx: dict[str, Any],
    *,
    node_expression: Optional[str] = None,
) -> Optional[str]:
    """Choose next target for a branch node.

    Precedence:
      1. Per-edge `condition` expression that evaluates true
      2. Node-level expression → yes/true vs no/false handles
      3. Happy-path handle labels (yes/pass/...)
      4. First edge
    """
    if not edges:
        return None
    if len(edges) == 1 and not (edges[0].get("condition") or node_expression):
        return edges[0].get("target")

    # 1) Explicit edge conditions
    for e in edges:
        cond = (e.get("condition") or "").strip()
        handle = (e.get("sourceHandle") or "").strip()
        # Skip pure handle labels that are not expressions
        if cond and _looks_like_expression(cond):
            try:
                if eval_expression(cond, ctx):
                    return e.get("target")
            except Exception:
                continue
        if handle and _looks_like_expression(handle):
            try:
                if eval_expression(handle, ctx):
                    return e.get("target")
            except Exception:
                continue

    # 2) Node-level expression → binary handles
    if node_expression and _looks_like_expression(node_expression):
        try:
            ok = eval_expression(node_expression, ctx)
        except Exception:
            ok = False
        wanted = {"yes", "true", "pass", "ok", "success"} if ok else {"no", "false", "fail", "error"}
        for e in edges:
            handle = (e.get("sourceHandle") or e.get("condition") or "").strip().lower()
            if handle in wanted:
                return e.get("target")
        # Fallback: first edge if true, second if false when unlabeled
        if ok:
            return edges[0].get("target")
        if len(edges) > 1:
            return edges[1].get("target")
        return edges[0].get("target")

    # 3) Happy-path labels
    for e in edges:
        handle = (e.get("sourceHandle") or e.get("condition") or "").strip().lower()
        if handle in ("", "yes", "pass", "true", "ok", "success", "approve", "out"):
            return e.get("target")
    return edges[0].get("target")


def pick_condition_outlet(
    outlets: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> Optional[str]:
    """CONDITION: first matching outlet.expression → edge with that sourceHandle."""
    by_handle: dict[str, str] = {}
    fallback: Optional[str] = None
    for e in edges:
        handle = (e.get("sourceHandle") or e.get("condition") or "").strip()
        if e.get("fallback") or handle.lower() in {"fallback", "default", "else"}:
            fallback = e.get("target")
            continue
        if handle:
            by_handle[handle] = e.get("target")
            by_handle[handle.lower()] = e.get("target")

    for outlet in outlets or []:
        oid = str(outlet.get("identifier") or "").strip()
        expr = str(outlet.get("expression") or "").strip()
        if not oid:
            continue
        matched = False
        if expr:
            # JQ often looks like `.outputs.trigger.x == "y"` — normalize leading dot
            norm = expr.lstrip(".")
            if not norm.startswith(("input", "outputs", "approvals", "vars")):
                # treat `.outputs...` → `outputs...`
                if expr.startswith("."):
                    norm = expr[1:]
                else:
                    norm = expr
            try:
                matched = eval_expression(norm, ctx) if _looks_like_expression(norm) else bool(norm)
            except Exception:
                matched = False
        if matched:
            return by_handle.get(oid) or by_handle.get(oid.lower())

    if fallback:
        return fallback
    # No outlet matched — try unlabeled / first edge
    return pick_branch_target(edges, ctx, node_expression=None)


def _looks_like_expression(text: str) -> bool:
    t = text.strip().lower()
    if t in {
        "", "yes", "no", "true", "false", "pass", "fail", "ok", "success",
        "approve", "reject", "changes", "out", "error",
    }:
        return False
    return any(ch in t for ch in (" ", ".", "=", "!", ">", "<", "(", ")", "[", "]")) or t.startswith(
        ("input", "outputs", "approvals", "vars", "not ")
    ) or " in " in f" {t} "


def _tokenize(text: str) -> list[str]:
    pos = 0
    out: list[str] = []
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"invalid expression near: {text[pos:pos+20]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


def _parse_or(tokens: list[str], i: int, env: dict[str, Any]) -> tuple[Any, int]:
    left, i = _parse_and(tokens, i, env)
    while i < len(tokens) and tokens[i] == "or":
        right, i = _parse_and(tokens, i + 1, env)
        left = bool(left) or bool(right)
    return left, i


def _parse_and(tokens: list[str], i: int, env: dict[str, Any]) -> tuple[Any, int]:
    left, i = _parse_not(tokens, i, env)
    while i < len(tokens) and tokens[i] == "and":
        right, i = _parse_not(tokens, i + 1, env)
        left = bool(left) and bool(right)
    return left, i


def _parse_not(tokens: list[str], i: int, env: dict[str, Any]) -> tuple[Any, int]:
    if i < len(tokens) and tokens[i] == "not":
        val, i = _parse_not(tokens, i + 1, env)
        return (not bool(val)), i
    return _parse_cmp(tokens, i, env)


def _parse_cmp(tokens: list[str], i: int, env: dict[str, Any]) -> tuple[Any, int]:
    left, i = _parse_primary(tokens, i, env)
    if i < len(tokens) and tokens[i] == "in":
        right, i = _parse_primary(tokens, i + 1, env)
        return _in_op(left, right), i
    if i < len(tokens) and tokens[i] in {"==", "!=", ">", ">=", "<", "<="}:
        op = tokens[i]
        right, i = _parse_primary(tokens, i + 1, env)
        return _compare(op, left, right), i
    return left, i


def _parse_primary(tokens: list[str], i: int, env: dict[str, Any]) -> tuple[Any, int]:
    if i >= len(tokens):
        raise ValueError("unexpected end of expression")
    tok = tokens[i]
    if tok == "(":
        val, i = _parse_or(tokens, i + 1, env)
        if i >= len(tokens) or tokens[i] != ")":
            raise ValueError("missing )")
        return val, i + 1
    if tok == "[":
        items: list[Any] = []
        i += 1
        if i < len(tokens) and tokens[i] == "]":
            return items, i + 1
        while True:
            item, i = _parse_or(tokens, i, env)
            items.append(item)
            if i >= len(tokens):
                raise ValueError("missing ]")
            if tokens[i] == "]":
                return items, i + 1
            if tokens[i] != ",":
                raise ValueError("expected , or ] in list")
            i += 1
    if tok == "true":
        return True, i + 1
    if tok == "false":
        return False, i + 1
    if tok == "null":
        return None, i + 1
    if tok[0] in "\"'":
        return _unescape(tok[1:-1]), i + 1
    if re.fullmatch(r"-?\d+(?:\.\d+)?", tok):
        return (float(tok) if "." in tok else int(tok)), i + 1
    # path
    return resolve_path(tok, env), i + 1


def _unescape(s: str) -> str:
    return s.replace("\\\\", "\\").replace('\\"', '"').replace("\\'", "'")


def _in_op(left: Any, right: Any) -> bool:
    if isinstance(right, (list, tuple, set)):
        return left in right
    if isinstance(right, str):
        return str(left) in right
    if isinstance(right, dict):
        return left in right
    return False


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    # Numeric-ish comparisons; fail closed on TypeError
    try:
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
    except TypeError:
        return False
    return False
