"""Scan graphs for skill / control / rule consumers."""

from __future__ import annotations

from typing import Any, Iterable

from src.platform.graphs.models import GraphRecord, GraphVersion


def _nodes_of(dsl: Any) -> list[dict[str, Any]]:
    if not isinstance(dsl, dict):
        return []
    nodes = dsl.get("nodes") or []
    return [n for n in nodes if isinstance(n, dict)]


def _policies(dsl: Any) -> dict[str, Any]:
    if not isinstance(dsl, dict):
        return {}
    raw = dsl.get("policies")
    return raw if isinstance(raw, dict) else {}


def _cfg(node: dict[str, Any]) -> dict[str, Any]:
    raw = node.get("config") or node.get("data") or {}
    return raw if isinstance(raw, dict) else {}


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("identifier") or node.get("id") or node.get("key") or "")


def node_skill_keys(node: dict[str, Any]) -> set[str]:
    cfg = _cfg(node)
    keys: set[str] = set()
    for source in (cfg, node):
        for field in ("agentIdentifier", "skill_key", "interface_key"):
            value = str(source.get(field) or "").strip()
            if value:
                keys.add(value)
    return keys


def node_rule_keys(node: dict[str, Any]) -> list[str]:
    cfg = _cfg(node)
    keys: list[str] = []
    raw = cfg.get("rule_keys") or node.get("rule_keys") or []
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, list):
        keys.extend(str(k).strip() for k in raw if str(k).strip())
    bindings = cfg.get("rule_bindings") or node.get("rule_bindings") or []
    if isinstance(bindings, list):
        for item in bindings:
            if isinstance(item, dict):
                key = str(item.get("rule_key") or item.get("key") or "").strip()
                if key:
                    keys.append(key)
    return keys


def node_control_keys(node: dict[str, Any]) -> list[str]:
    cfg = _cfg(node)
    keys: list[str] = []
    for field in ("control_pack_key", "control_source"):
        value = str(cfg.get(field) or node.get(field) or "").strip()
        if value:
            keys.append(value.split("@", 1)[0])
    packs = cfg.get("packs") or cfg.get("control_packs") or []
    if isinstance(packs, list):
        for item in packs:
            if isinstance(item, dict):
                key = str(item.get("key") or item.get("control_pack_key") or "").strip()
            else:
                key = str(item).strip()
            if key:
                keys.append(key.split("@", 1)[0])
    return keys


def _policy_rule_keys(policies: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in policies.get("rule_bindings") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("rule_key") or item.get("key") or "").strip()
        step = str(item.get("step_key") or item.get("node_id") or "").strip()
        if key:
            out.append((key, step))
    return out


def _policy_control_keys(policies: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for item in policies.get("control_bindings") or []:
        if isinstance(item, dict):
            key = str(item.get("control_pack_key") or item.get("key") or "").strip()
        else:
            key = str(item).strip()
        if key:
            keys.append(key.split("@", 1)[0])
    return keys


def iter_graph_docs() -> Iterable[tuple[GraphRecord, GraphVersion, dict[str, Any]]]:
    from src.platform.graphs.service import list_graphs, list_all_versions

    records = {str(r.id): r for r in list_graphs()}
    for ver in list_all_versions():
        rec = records.get(str(ver.graph_id))
        if not rec:
            continue
        dsl = ver.dsl if isinstance(ver.dsl, dict) else {}
        yield rec, ver, dsl


def graphs_using_skill(skill_key: str) -> list[str]:
    want = str(skill_key or "").strip()
    if not want:
        return []
    found: list[str] = []
    for rec, _ver, dsl in iter_graph_docs():
        if rec.key in found:
            continue
        for node in _nodes_of(dsl):
            if want in node_skill_keys(node):
                found.append(rec.key)
                break
    return found


def graphs_using_control(control_key: str) -> list[str]:
    want = str(control_key or "").strip().split("@", 1)[0]
    if not want:
        return []
    found: list[str] = []
    for rec, _ver, dsl in iter_graph_docs():
        if rec.key in found:
            continue
        policies = _policies(dsl)
        if want in _policy_control_keys(policies):
            found.append(rec.key)
            continue
        for node in _nodes_of(dsl):
            if want in node_control_keys(node):
                found.append(rec.key)
                break
    return found


def bound_rule_keys_for_skill(skill_key: str, graph_key: str | None = None) -> list[str]:
    want = str(skill_key or "").strip()
    if not want:
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for rec, _ver, dsl in iter_graph_docs():
        if graph_key and rec.key != graph_key:
            continue
        policies = _policies(dsl)
        for rule_key, step in _policy_rule_keys(policies):
            if rule_key in seen:
                continue
            if not step or step == want:
                seen.add(rule_key)
                keys.append(rule_key)
        for node in _nodes_of(dsl):
            if want not in node_skill_keys(node) and _node_id(node) != want:
                continue
            for rule_key in node_rule_keys(node):
                if rule_key not in seen:
                    seen.add(rule_key)
                    keys.append(rule_key)
    return keys


def rule_usages(rule_key: str) -> list[dict[str, Any]]:
    want = str(rule_key or "").strip()
    if not want:
        return []
    usages: list[dict[str, Any]] = []
    for rec, ver, dsl in iter_graph_docs():
        policies = _policies(dsl)
        for key, step in _policy_rule_keys(policies):
            if key != want:
                continue
            usages.append({
                "flow_id": str(rec.id),
                "flow_key": rec.key,
                "flow_name": rec.name,
                "graph_id": str(rec.id),
                "graph_key": rec.key,
                "step_key": step or None,
                "semantic_version": ver.semantic_version,
                "status": ver.status,
            })
        for node in _nodes_of(dsl):
            if want not in node_rule_keys(node):
                continue
            usages.append({
                "flow_id": str(rec.id),
                "flow_key": rec.key,
                "flow_name": rec.name,
                "graph_id": str(rec.id),
                "graph_key": rec.key,
                "step_key": _node_id(node) or None,
                "semantic_version": ver.semantic_version,
                "status": ver.status,
            })
    return usages
