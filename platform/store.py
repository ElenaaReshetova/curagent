"""JSON file store for AI Agent Platform Control/Runtime entities."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.platform.contracts.models import ArtifactContract
from src.platform.domain.models import (
    ActivityItem,
    Agent,
    ArtifactBlueprint,
    AuditEvent,
    CapabilityDef,
    ControlPack,
    Execution,
    ExecutionContractTemplate,
    ExecutionSummary,
    KnowledgeSpace,
    MCPIntegrationSummary,
    ModelProfile,
    OperatorDefinition,
    OverviewPayload,
    PlatformEvent,
    PlatformUser,
    PolicyPack,
    QueueItem,
    RuleSet,
    RuntimeProfile,
    SkillImplementation,
    SkillInterface,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "config" / "platform"


def get_platform_dir() -> Path:
    env = os.environ.get("PLATFORM_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_DIR


def _path(name: str) -> Path:
    return get_platform_dir() / name


def _read_list(name: str) -> list[dict]:
    path = _path(name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return []
    if isinstance(data, dict):
        for key in ("items", "operators", "playbooks", "blueprints", "policies",
                    "templates", "integrations", "models", "users", "events",
                    "executions", "activity", "queue", "audit", "agents", "flows",
                    "skill_interfaces", "skills", "rules", "controls",
                    "knowledge_spaces", "capabilities", "runtime_profiles"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # Fallback: first list value in object
        for value in data.values():
            if isinstance(value, list):
                return value
        return []
    return data if isinstance(data, list) else []


def _write_list(name: str, key: str, items: list[BaseModel]) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: [i.model_dump(mode="json") for i in items]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse(items: list[dict], model: type[T]) -> list[T]:
    out: list[T] = []
    for raw in items:
        try:
            out.append(model.model_validate(raw))
        except Exception as e:
            logger.warning("Skip invalid %s: %s", model.__name__, e)
    return out


def ensure_seeded() -> None:
    """Create config/platform/*.json from seed catalog if missing."""
    root = get_platform_dir()
    root.mkdir(parents=True, exist_ok=True)
    marker = root / ".seeded"
    if not marker.exists() or not _path("operators.json").exists():
        from src.platform.seed.catalog import (
            OPERATOR_CATALOG,
            build_activity,
            build_blueprints,
            build_contract_templates,
            build_events,
            build_integrations,
            build_models,
            build_policies,
            build_queue,
            build_users,
            seed_audit_events,
        )

        _write_list("operators.json", "operators", list(OPERATOR_CATALOG))
        _write_list("blueprints.json", "blueprints", build_blueprints())
        _write_list("policies.json", "policies", build_policies())
        _write_list("contracts.json", "templates", build_contract_templates())
        _write_list("integrations.json", "integrations", build_integrations())
        _write_list("models.json", "models", build_models())
        _write_list("users.json", "users", build_users())
        _write_list("activity.json", "activity", build_activity())
        _write_list("queue.json", "queue", build_queue())
        _write_list("events.json", "events", build_events())
        _write_list("audit.json", "audit", seed_audit_events())
        marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")

    governed_marker = root / ".seeded_governed_v1"
    governed_files = (
        "agents.json", "skill_interfaces.json",
        "skills.json", "rules.json", "controls.json", "knowledge_spaces.json",
        "capabilities_platform.json",
    )
    if not (governed_marker.exists() and all(_path(name).exists() for name in governed_files)):
        from src.platform.seed.governed_catalog import (
            build_agents,
            build_capabilities,
            build_controls,
            build_executions,
            build_knowledge_spaces,
            build_rules,
            build_skill_interfaces,
            build_skills,
        )

        _write_list("agents.json", "agents", build_agents())
        _write_list("skill_interfaces.json", "skill_interfaces", build_skill_interfaces())
        _write_list("skills.json", "skills", build_skills())
        _write_list("rules.json", "rules", build_rules())
        _write_list("controls.json", "controls", build_controls())
        _write_list("knowledge_spaces.json", "knowledge_spaces", build_knowledge_spaces())
        _write_list("capabilities_platform.json", "capabilities", build_capabilities())
        _write_list("executions.json", "executions", build_executions())
        governed_marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
        logger.info("Platform store seeded at %s", root)

    # V2: Runtime Profiles (migrate from Agents without wiping other seeds)
    v2_marker = root / ".seeded_v2_runtime_profiles"
    if not v2_marker.exists() or not _path("runtime_profiles.json").exists():
        from src.platform.seed.governed_catalog import build_runtime_profiles

        _write_list("runtime_profiles.json", "runtime_profiles", build_runtime_profiles())
        v2_marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
        logger.info("Runtime profiles seeded at %s", root)

    artifact_marker = root / ".seeded_artifact_contracts_v1"
    if not artifact_marker.exists() or not _path("artifact_contracts.json").exists():
        from src.platform.contracts.seed import build_artifact_contracts

        _write_list("artifact_contracts.json", "contracts", build_artifact_contracts())
        artifact_marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
        logger.info("Artifact contracts seeded at %s", root)

    from src.platform.graphs.service import ensure_graphs_seeded
    from src.platform.skills.service import ensure_skills_seeded
    from src.platform.rules.service import ensure_rules_seeded
    from src.platform.knowledge.service import ensure_knowledge_seeded
    from src.platform.runtime_profiles.service import ensure_runtime_profiles_seeded
    from src.platform.executions.service import ensure_executions_seeded
    from src.platform.human_checkpoints.service import ensure_human_checkpoints_seeded
    from src.platform.controls.service import ensure_controls_seeded
    from src.platform.integrations.service import ensure_integrations_seeded

    ensure_graphs_seeded()
    ensure_skills_seeded()
    ensure_rules_seeded()
    ensure_knowledge_seeded()
    ensure_runtime_profiles_seeded()
    ensure_executions_seeded()
    ensure_human_checkpoints_seeded()
    ensure_controls_seeded()
    ensure_integrations_seeded()


def append_audit(
    action: str,
    entity_type: str,
    entity_id: str = "",
    summary: str = "",
    actor: str = "admin",
    details: dict | None = None,
) -> AuditEvent:
    ensure_seeded()
    events = list_audit()
    evt = AuditEvent(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=details or {},
    )
    events.insert(0, evt)
    _write_list("audit.json", "audit", events[:500])
    return evt


# ── Generic CRUD helpers ───────────────────────────────────────

def _save_collection(
    filename: str,
    key: str,
    items: list[T],
) -> list[T]:
    _write_list(filename, key, items)
    return items


def _upsert(items: list[T], entity: T, id_attr: str = "id") -> list[T]:
    eid = str(getattr(entity, id_attr))
    out: list[T] = []
    found = False
    for item in items:
        if str(getattr(item, id_attr)) == eid:
            out.append(entity)
            found = True
        else:
            out.append(item)
    if not found:
        out.append(entity)
    return out


def _delete(items: list[T], entity_id: str, id_attr: str = "id") -> list[T]:
    return [i for i in items if str(getattr(i, id_attr)) != entity_id]


def _find(items: list[T], entity_id: str, id_attr: str = "id") -> T | None:
    for item in items:
        if str(getattr(item, id_attr)) == entity_id:
            return item
    return None


def _find_by_key(items: list[T], key: str) -> T | None:
    for item in items:
        if getattr(item, "key", None) == key:
            return item
    return None


# ── Operators ──────────────────────────────────────────────────

def list_operators() -> list[OperatorDefinition]:
    ensure_seeded()
    return _parse(_read_list("operators.json"), OperatorDefinition)


def get_operator(operator_id: str) -> OperatorDefinition | None:
    return _find(list_operators(), operator_id) or _find_by_key(list_operators(), operator_id)


def save_operator(op: OperatorDefinition) -> OperatorDefinition:
    op.updated_at = datetime.utcnow()
    items = _upsert(list_operators(), op)
    _save_collection("operators.json", "operators", items)
    append_audit("save", "operator", str(op.id), f"Saved operator {op.key}")
    return op


def delete_operator(operator_id: str) -> bool:
    items = list_operators()
    target = _find(items, operator_id) or _find_by_key(items, operator_id)
    if not target:
        return False
    _save_collection("operators.json", "operators", _delete(items, str(target.id)))
    append_audit("delete", "operator", str(target.id), f"Deleted operator {target.key}")
    return True


# ── Governed configuration entities ────────────────────────────

def _list_entities(filename: str, model: type[T]) -> list[T]:
    ensure_seeded()
    return _parse(_read_list(filename), model)


def _get_entity(filename: str, model: type[T], entity_id: str) -> T | None:
    items = _list_entities(filename, model)
    return _find(items, entity_id) or _find_by_key(items, entity_id)


def _save_entity(filename: str, collection_key: str, entity_type: str, entity: T) -> T:
    if hasattr(entity, "updated_at"):
        entity.updated_at = datetime.utcnow()  # type: ignore[attr-defined]
    items = _upsert(_list_entities(filename, type(entity)), entity)
    _save_collection(filename, collection_key, items)
    append_audit("save", entity_type, str(entity.id), f"Saved {entity_type} {getattr(entity, 'key', entity.id)}")
    return entity


def _delete_entity(filename: str, collection_key: str, model: type[T], entity_type: str, entity_id: str) -> bool:
    items = _list_entities(filename, model)
    target = _find(items, entity_id) or _find_by_key(items, entity_id)
    if not target:
        return False
    _save_collection(filename, collection_key, _delete(items, str(target.id)))
    append_audit("delete", entity_type, str(target.id), f"Deleted {entity_type} {getattr(target, 'key', target.id)}")
    return True


def list_agents() -> list[Agent]:
    return _list_entities("agents.json", Agent)


def get_agent(entity_id: str) -> Agent | None:
    return _get_entity("agents.json", Agent, entity_id)


def save_agent(entity: Agent) -> Agent:
    return _save_entity("agents.json", "agents", "agent", entity)


def delete_agent(entity_id: str) -> bool:
    return _delete_entity("agents.json", "agents", Agent, "agent", entity_id)


def list_runtime_profiles() -> list[RuntimeProfile]:
    ensure_seeded()
    return _list_entities("runtime_profiles.json", RuntimeProfile)


def get_runtime_profile(entity_id: str) -> RuntimeProfile | None:
    ensure_seeded()
    return _get_entity("runtime_profiles.json", RuntimeProfile, entity_id)


def save_runtime_profile(entity: RuntimeProfile) -> RuntimeProfile:
    ensure_seeded()
    return _save_entity("runtime_profiles.json", "runtime_profiles", "runtime_profile", entity)


def delete_runtime_profile(entity_id: str) -> bool:
    ensure_seeded()
    return _delete_entity(
        "runtime_profiles.json", "runtime_profiles", RuntimeProfile, "runtime_profile", entity_id
    )


def list_skill_interfaces() -> list[SkillInterface]:
    return _list_entities("skill_interfaces.json", SkillInterface)


def get_skill_interface(entity_id: str) -> SkillInterface | None:
    return _get_entity("skill_interfaces.json", SkillInterface, entity_id)


def save_skill_interface(entity: SkillInterface) -> SkillInterface:
    return _save_entity("skill_interfaces.json", "skill_interfaces", "skill_interface", entity)


def delete_skill_interface(entity_id: str) -> bool:
    return _delete_entity("skill_interfaces.json", "skill_interfaces", SkillInterface, "skill_interface", entity_id)


def list_skills() -> list[SkillImplementation]:
    return _list_entities("skills.json", SkillImplementation)


def get_skill(entity_id: str) -> SkillImplementation | None:
    return _get_entity("skills.json", SkillImplementation, entity_id)


def save_skill(entity: SkillImplementation) -> SkillImplementation:
    return _save_entity("skills.json", "skills", "skill", entity)


def delete_skill(entity_id: str) -> bool:
    return _delete_entity("skills.json", "skills", SkillImplementation, "skill", entity_id)


def list_rules() -> list[RuleSet]:
    return _list_entities("rules.json", RuleSet)


def get_rule(entity_id: str) -> RuleSet | None:
    return _get_entity("rules.json", RuleSet, entity_id)


def save_rule(entity: RuleSet) -> RuleSet:
    return _save_entity("rules.json", "rules", "rule", entity)


def delete_rule(entity_id: str) -> bool:
    return _delete_entity("rules.json", "rules", RuleSet, "rule", entity_id)


def list_controls() -> list[ControlPack]:
    return _list_entities("controls.json", ControlPack)


def get_control(entity_id: str) -> ControlPack | None:
    return _get_entity("controls.json", ControlPack, entity_id)


def save_control(entity: ControlPack) -> ControlPack:
    return _save_entity("controls.json", "controls", "control", entity)


def delete_control(entity_id: str) -> bool:
    return _delete_entity("controls.json", "controls", ControlPack, "control", entity_id)


def list_knowledge_spaces() -> list[KnowledgeSpace]:
    return _list_entities("knowledge_spaces.json", KnowledgeSpace)


def get_knowledge_space(entity_id: str) -> KnowledgeSpace | None:
    return _get_entity("knowledge_spaces.json", KnowledgeSpace, entity_id)


def save_knowledge_space(entity: KnowledgeSpace) -> KnowledgeSpace:
    return _save_entity("knowledge_spaces.json", "knowledge_spaces", "knowledge_space", entity)


def delete_knowledge_space(entity_id: str) -> bool:
    return _delete_entity("knowledge_spaces.json", "knowledge_spaces", KnowledgeSpace, "knowledge_space", entity_id)


def list_capabilities() -> list[CapabilityDef]:
    return _list_entities("capabilities_platform.json", CapabilityDef)


def get_capability(entity_id: str) -> CapabilityDef | None:
    return _get_entity("capabilities_platform.json", CapabilityDef, entity_id)


def save_capability(entity: CapabilityDef) -> CapabilityDef:
    return _save_entity("capabilities_platform.json", "capabilities", "capability", entity)


def delete_capability(entity_id: str) -> bool:
    return _delete_entity("capabilities_platform.json", "capabilities", CapabilityDef, "capability", entity_id)


# ── Blueprints ─────────────────────────────────────────────────

def list_blueprints() -> list[ArtifactBlueprint]:
    ensure_seeded()
    return _parse(_read_list("blueprints.json"), ArtifactBlueprint)


def get_blueprint(blueprint_id: str) -> ArtifactBlueprint | None:
    items = list_blueprints()
    return _find(items, blueprint_id) or _find_by_key(items, blueprint_id)


def save_blueprint(bp: ArtifactBlueprint) -> ArtifactBlueprint:
    bp.updated_at = datetime.utcnow()
    items = _upsert(list_blueprints(), bp)
    _save_collection("blueprints.json", "blueprints", items)
    append_audit("save", "blueprint", str(bp.id), f"Saved blueprint {bp.key}")
    return bp


def delete_blueprint(blueprint_id: str) -> bool:
    items = list_blueprints()
    target = _find(items, blueprint_id) or _find_by_key(items, blueprint_id)
    if not target:
        return False
    _save_collection("blueprints.json", "blueprints", _delete(items, str(target.id)))
    append_audit("delete", "blueprint", str(target.id), f"Deleted blueprint {target.key}")
    return True


# ── Policies ───────────────────────────────────────────────────

def list_policies() -> list[PolicyPack]:
    ensure_seeded()
    return _parse(_read_list("policies.json"), PolicyPack)


def get_policy(policy_id: str) -> PolicyPack | None:
    items = list_policies()
    return _find(items, policy_id) or _find_by_key(items, policy_id)


def save_policy(pol: PolicyPack) -> PolicyPack:
    pol.updated_at = datetime.utcnow()
    items = _upsert(list_policies(), pol)
    _save_collection("policies.json", "policies", items)
    append_audit("save", "policy", str(pol.id), f"Saved policy {pol.key}")
    return pol


def delete_policy(policy_id: str) -> bool:
    items = list_policies()
    target = _find(items, policy_id) or _find_by_key(items, policy_id)
    if not target:
        return False
    _save_collection("policies.json", "policies", _delete(items, str(target.id)))
    append_audit("delete", "policy", str(target.id), f"Deleted policy {target.key}")
    return True


# ── Contracts ──────────────────────────────────────────────────

def list_contracts() -> list[ExecutionContractTemplate]:
    ensure_seeded()
    return _parse(_read_list("contracts.json"), ExecutionContractTemplate)


def get_contract(contract_id: str) -> ExecutionContractTemplate | None:
    items = list_contracts()
    return _find(items, contract_id) or _find_by_key(items, contract_id)


def save_contract(ct: ExecutionContractTemplate) -> ExecutionContractTemplate:
    ct.updated_at = datetime.utcnow()
    items = _upsert(list_contracts(), ct)
    _save_collection("contracts.json", "templates", items)
    append_audit("save", "contract_template", str(ct.id), f"Saved contract {ct.key}")
    return ct


def delete_contract(contract_id: str) -> bool:
    items = list_contracts()
    target = _find(items, contract_id) or _find_by_key(items, contract_id)
    if not target:
        return False
    _save_collection("contracts.json", "templates", _delete(items, str(target.id)))
    append_audit("delete", "contract_template", str(target.id), f"Deleted contract {target.key}")
    return True


# ── Artifact contracts (skill/graph I/O types) ─────────────

def list_artifact_contracts() -> list[ArtifactContract]:
    ensure_seeded()
    return _parse(_read_list("artifact_contracts.json"), ArtifactContract)


def get_artifact_contract(contract_key: str) -> ArtifactContract | None:
    items = list_artifact_contracts()
    return _find_by_key(items, contract_key)


# ── Integrations / Models / Users / Audit / Runtime ────────────

def list_integrations() -> list[MCPIntegrationSummary]:
    ensure_seeded()
    return _parse(_read_list("integrations.json"), MCPIntegrationSummary)


def save_integration(item: MCPIntegrationSummary) -> MCPIntegrationSummary:
    items = list_integrations()
    out = []
    found = False
    for it in items:
        if it.key == item.key:
            out.append(item)
            found = True
        else:
            out.append(it)
    if not found:
        out.append(item)
    _save_collection("integrations.json", "integrations", out)
    append_audit("save", "integration", item.key, f"Saved integration {item.name}")
    return item


def list_models() -> list[ModelProfile]:
    ensure_seeded()
    return _parse(_read_list("models.json"), ModelProfile)


def get_model(model_id: str) -> ModelProfile | None:
    items = list_models()
    return _find(items, model_id) or _find_by_key(items, model_id)


def save_model(m: ModelProfile) -> ModelProfile:
    m.updated_at = datetime.utcnow()
    items = _upsert(list_models(), m)
    _save_collection("models.json", "models", items)
    append_audit("save", "model", str(m.id), f"Saved model {m.key}")
    return m


def delete_model(model_id: str) -> bool:
    items = list_models()
    target = _find(items, model_id) or _find_by_key(items, model_id)
    if not target:
        return False
    _save_collection("models.json", "models", _delete(items, str(target.id)))
    append_audit("delete", "model", str(target.id), f"Deleted model {target.key}")
    return True


def list_users() -> list[PlatformUser]:
    ensure_seeded()
    return _parse(_read_list("users.json"), PlatformUser)


def get_user(user_id: str) -> PlatformUser | None:
    return _find(list_users(), user_id)


def save_user(u: PlatformUser) -> PlatformUser:
    u.updated_at = datetime.utcnow()
    items = _upsert(list_users(), u)
    _save_collection("users.json", "users", items)
    append_audit("save", "user", str(u.id), f"Saved user {u.username}")
    return u


def delete_user(user_id: str) -> bool:
    items = list_users()
    if not _find(items, user_id):
        return False
    _save_collection("users.json", "users", _delete(items, user_id))
    append_audit("delete", "user", user_id, "Deleted user")
    return True


def list_audit() -> list[AuditEvent]:
    ensure_seeded()
    return _parse(_read_list("audit.json"), AuditEvent)


def list_executions() -> list[Execution]:
    ensure_seeded()
    return _parse(_read_list("executions.json"), Execution)


def get_execution(execution_id: str) -> Execution | None:
    return _find(list_executions(), execution_id)


def save_execution(ex: Execution) -> Execution:
    ex.updated_at = datetime.utcnow()
    items = _upsert(list_executions(), ex)
    _save_collection("executions.json", "executions", items)
    append_audit("save", "execution", ex.id, f"Updated execution {ex.id}")
    return ex


def list_activity() -> list[ActivityItem]:
    ensure_seeded()
    return _parse(_read_list("activity.json"), ActivityItem)


def list_queue() -> list[QueueItem]:
    ensure_seeded()
    return _parse(_read_list("queue.json"), QueueItem)


def list_events() -> list[PlatformEvent]:
    ensure_seeded()
    return _parse(_read_list("events.json"), PlatformEvent)


def _overview_skills() -> list[dict]:
    from src.platform.skills import service as skills_svc

    items: list[dict] = []
    for c in skills_svc.catalog_items():
        status = "active" if str(c.status).lower() in {"published", "active"} else (
            "draft" if str(c.status).lower() == "draft" else str(c.status).lower()
        )
        iface = (c.interfaces[0] if c.interfaces else "") or ""
        items.append({
            "id": c.id,
            "key": c.key,
            "name": c.name,
            "description": c.description,
            "status": status,
            "version": c.version or "1",
            "interface_key": iface,
            "implements": iface,
            "skill_type": c.skill_type,
            "immutable": c.immutable,
        })
    return items


def build_overview_from_store() -> OverviewPayload:
    from src.platform.executions import service as executions_svc

    ensure_seeded()
    status_map = {
        "RUNNING": "running",
        "WAITING_FOR_HUMAN": "waiting_approval",
        "PAUSED": "blocked",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
        "QUEUED": "received",
        "STARTING": "compiling",
    }
    recent: list[ExecutionSummary] = []
    try:
        for item in executions_svc.catalog_items()[:8]:
            rec = executions_svc.get_record(item.id)
            recent.append(
                ExecutionSummary(
                    id=item.id,
                    external_source=(item.source.split()[0].lower() if item.source else "platform"),
                    external_work_item_id=item.source,
                    playbook_name=item.flow_name,
                    status=status_map.get(item.status, "running"),  # type: ignore[arg-type]
                    started_at=rec.started_at if rec else datetime.utcnow(),
                    current_operator_key=item.current_stage,
                )
            )
    except Exception:
        executions = list_executions()
        recent = [
            ExecutionSummary(
                id=e.id,
                external_source=e.external_source,
                external_work_item_id=e.external_work_item_id,
                playbook_name=e.playbook_name,
                status=e.status,
                started_at=e.started_at,
                current_operator_key=e.current_operator_key,
            )
            for e in sorted(executions, key=lambda x: x.started_at, reverse=True)[:8]
        ]
    waiting = 0
    try:
        waiting = executions_svc.metrics().waiting_human
    except Exception:
        waiting = sum(
            1 for execution in list_executions() for approval in execution.approvals
            if approval.status == "pending"
        )
    return OverviewPayload(
        agents=list_agents(),
        runtime_profiles=list_runtime_profiles(),
        playbooks=[],
        skills=_overview_skills(),
        controls=list_controls(),
        knowledge_spaces=list_knowledge_spaces(),
        flows=[],
        operators=list_operators(),
        blueprints=list_blueprints(),
        policies=list_policies(),
        contract_templates=list_contracts(),
        integrations=list_integrations(),
        recent_executions=recent,
        waiting_approvals_count=waiting,
    )
