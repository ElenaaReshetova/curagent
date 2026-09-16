"""Minimal JSON policy DSL evaluator (MVP)."""

from __future__ import annotations

from typing import Any


OPS = {"eq", "neq", "in", "contains", "exists", "all", "any", "not", "gt", "gte", "lt", "lte"}


def _resolve(path: str, ctx: dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate_rule(rule: Any, ctx: dict[str, Any]) -> bool:
    if rule is True:
        return True
    if rule is False or rule is None:
        return False
    if not isinstance(rule, dict) or len(rule) != 1:
        return False
    op, args = next(iter(rule.items()))
    if op == "eq":
        left, right = args
        lv = _resolve(left, ctx) if isinstance(left, str) else left
        return lv == right
    if op == "neq":
        left, right = args
        lv = _resolve(left, ctx) if isinstance(left, str) else left
        return lv != right
    if op == "in":
        left, right = args
        lv = _resolve(left, ctx) if isinstance(left, str) else left
        return lv in (right or [])
    if op == "contains":
        left, right = args
        lv = _resolve(left, ctx) if isinstance(left, str) else left
        return right in (lv or [])
    if op == "exists":
        path = args if isinstance(args, str) else args[0]
        return _resolve(path, ctx) is not None
    if op == "all":
        return all(evaluate_rule(r, ctx) for r in args)
    if op == "any":
        return any(evaluate_rule(r, ctx) for r in args)
    if op == "not":
        return not evaluate_rule(args, ctx)
    if op in {"gt", "gte", "lt", "lte"}:
        left, right = args
        lv = _resolve(left, ctx) if isinstance(left, str) else left
        if lv is None:
            return False
        if op == "gt":
            return lv > right
        if op == "gte":
            return lv >= right
        if op == "lt":
            return lv < right
        return lv <= right
    return False


def validate_policy_pack(rules: list[dict[str, Any]], sample_ctx: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    ctx = sample_ctx or {
        "operator": {"side_effects": "publish", "key": "publish_result"},
        "tool": {"status": "approved"},
    }
    for i, rule in enumerate(rules):
        if "when" in rule:
            try:
                evaluate_rule(rule["when"], ctx)
            except Exception as e:
                errors.append(f"rule[{i}].when: {e}")
        if "then" not in rule and "when" not in rule:
            errors.append(f"rule[{i}]: expected when/then")
    return errors
