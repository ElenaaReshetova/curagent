"""Structural validation rules for playbook graphs."""

from __future__ import annotations

from collections import defaultdict, deque

from src.orchestrator.workflow_config.models import (
    StepType,
    WorkflowTemplate,
    is_gateway,
    is_gateway_and,
    is_gateway_or,
)
from src.orchestrator.workflow_config.skeleton import (
    SHELL_CLASSIFY_ID,
    SHELL_COMPRESS_ID,
    SHELL_END_PLAYBOOK_ID,
    SHELL_EVIDENCE_ID,
    SHELL_START_PLAYBOOK_ID,
    find_end_playbook,
    find_start_playbook,
    is_shell_type,
    playbook_body_step_ids,
)


def _enabled_steps(template: WorkflowTemplate) -> list:
    return [s for s in template.steps if s.enabled]


def _adj_maps(template: WorkflowTemplate, enabled_ids: set[str]):
    outs: dict[str, list] = defaultdict(list)
    inns: dict[str, list] = defaultdict(list)
    for edge in template.edges:
        if edge.from_step not in enabled_ids or edge.to_step not in enabled_ids:
            continue
        outs[edge.from_step].append(edge)
        inns[edge.to_step].append(edge)
    return outs, inns


def _reachable_from(start_id: str, outs: dict[str, list]) -> set[str]:
    seen = {start_id}
    q = deque([start_id])
    while q:
        cur = q.popleft()
        for e in outs.get(cur, []):
            if e.to_step not in seen:
                seen.add(e.to_step)
                q.append(e.to_step)
    return seen


def _has_edge(outs: dict, from_id: str, to_id: str) -> bool:
    return any(e.to_step == to_id for e in outs.get(from_id, []))


def _validate_process_shell(template: WorkflowTemplate, enabled: list, outs: dict, errors: list[str]) -> None:
    """Require fixed preamble and start_playbook / end_playbook markers."""
    start_pbs = [s for s in enabled if s.type == StepType.START_PLAYBOOK]
    end_pbs = [s for s in enabled if s.type == StepType.END_PLAYBOOK]
    if len(start_pbs) != 1:
        errors.append(f"Нужен ровно один Start Playbook (сейчас: {len(start_pbs)})")
    if len(end_pbs) != 1:
        errors.append(f"Нужен ровно один End Playbook (сейчас: {len(end_pbs)})")

    by_id = {s.id: s for s in enabled}

    # Preferred canonical ids; also accept role-based match if ids renamed
    evidence = by_id.get(SHELL_EVIDENCE_ID) or next(
        (s for s in enabled if s.type == StepType.SCRIPT and (s.script_id or "") == "collect_evidence"),
        None,
    )
    compress = by_id.get(SHELL_COMPRESS_ID) or next(
        (s for s in enabled if s.type == StepType.SCRIPT and (s.script_id or "") == "compress_context"),
        None,
    )
    classify = by_id.get(SHELL_CLASSIFY_ID) or next(
        (
            s for s in enabled
            if (s.type == StepType.SKILL and (s.skill_id or "") in ("classify", "classify-task"))
            or s.type == StepType.CLASSIFY
        ),
        None,
    )

    if not evidence:
        errors.append("В преамбуле нужен шаг Collect evidence (script collect_evidence) до Start Playbook")
    if not compress:
        errors.append("В преамбуле нужен шаг Compress context (script compress_context) до Start Playbook")
    if not classify:
        errors.append("В преамбуле нужен шаг Classify (skill classify) до Start Playbook")

    starts = [s for s in enabled if s.type == StepType.START]
    if len(starts) == 1 and evidence and compress and classify and start_pbs:
        chain = [
            (starts[0].id, evidence.id, "Start → Collect evidence"),
            (evidence.id, compress.id, "Collect evidence → Compress context"),
            (compress.id, classify.id, "Compress context → Classify"),
            (classify.id, start_pbs[0].id, "Classify → Start Playbook"),
        ]
        for frm, to, label in chain:
            if not _has_edge(outs, frm, to):
                errors.append(f"Оболочка процесса: ожидается связь {label}")

    if start_pbs and end_pbs:
        body = playbook_body_step_ids(template)
        shell_ids = {
            s.id for s in enabled
            if is_shell_type(s.type)
            or s.id in {getattr(evidence, "id", None), getattr(compress, "id", None), getattr(classify, "id", None)}
        }
        # Steps after end_playbook before End are allowed only if locked (epilogue)
        end_pb = end_pbs[0]
        reachable_after = _reachable_from(end_pb.id, outs)
        for s in enabled:
            if s.id in shell_ids or s.id in body:
                continue
            if s.id in reachable_after and s.locked:
                continue
            if s.type == StepType.END:
                continue
            errors.append(
                f"Шаг '{s.label}' ({s.id}) вне зоны Start Playbook…End Playbook — "
                f"пользовательский сценарий настраивается только внутри маркеров"
            )

        # Markers themselves must be locked
        for s in start_pbs + end_pbs:
            if not s.locked:
                errors.append(f"'{s.label}' ({s.id}) должен быть locked")

        # Preamble steps should be locked
        for s in (evidence, compress, classify):
            if s and not s.locked:
                errors.append(f"Преамбула '{s.label}' ({s.id}) должна быть locked")


def collect_graph_errors(template: WorkflowTemplate) -> list[str]:
    """Return hard validation errors (empty list ⇒ graph is structurally valid)."""
    errors: list[str] = []
    enabled = _enabled_steps(template)
    if not enabled:
        return ["Нет включённых шагов"]

    enabled_ids = {s.id for s in enabled}

    starts = [s for s in enabled if s.type == StepType.START]
    ends = [s for s in enabled if s.type == StepType.END]
    if len(starts) != 1:
        errors.append(f"Нужен ровно один Start (сейчас: {len(starts)})")
    if len(ends) < 1:
        errors.append("Нужен хотя бы один End")
    if len(ends) > 1:
        errors.append(f"Допустим только один End (сейчас: {len(ends)})")

    step_ids = {s.id for s in template.steps}
    for edge in template.edges:
        if edge.from_step not in step_ids or edge.to_step not in step_ids:
            errors.append(f"Стрелка '{edge.id}' ссылается на неизвестный шаг")
        elif edge.from_step not in enabled_ids or edge.to_step not in enabled_ids:
            errors.append(
                f"Стрелка '{edge.id}' связана с отключённым шагом "
                f"({edge.from_step} → {edge.to_step})"
            )

    outs, inns = _adj_maps(template, enabled_ids)

    for s in enabled:
        out_edges = outs.get(s.id, [])
        in_edges = inns.get(s.id, [])

        if s.type == StepType.END:
            if out_edges:
                errors.append(
                    f"End '{s.label}' ({s.id}) не должен иметь исходящих стрелок"
                )
            if not in_edges:
                errors.append(f"End '{s.label}' ({s.id}) не имеет входящих стрелок")
            continue

        if s.type == StepType.START:
            if in_edges:
                errors.append(
                    f"Start '{s.label}' ({s.id}) не должен иметь входящих стрелок"
                )
            if not out_edges:
                errors.append(f"Start '{s.label}' ({s.id}) не имеет исходящих стрелок")
            continue

        if s.type == StepType.START_PLAYBOOK:
            if not out_edges:
                errors.append(
                    f"Start Playbook '{s.label}' ({s.id}) не имеет исходящих стрелок"
                )
            if not in_edges:
                errors.append(
                    f"Start Playbook '{s.label}' ({s.id}) недостижим: нет входящих стрелок"
                )
            continue

        if s.type == StepType.END_PLAYBOOK:
            if not out_edges:
                errors.append(
                    f"End Playbook '{s.label}' ({s.id}) должен вести дальше (обычно к End)"
                )
            if not in_edges:
                errors.append(
                    f"End Playbook '{s.label}' ({s.id}) недостижим: нет входящих стрелок"
                )
            continue

        if not out_edges:
            kind = "Gateway" if is_gateway(s.type) else "Шаг"
            errors.append(
                f"{kind} '{s.label}' ({s.id}) является тупиком: нет исходящих стрелок "
                f"(конечной точкой может быть только End)"
            )

        if not in_edges:
            errors.append(f"Шаг '{s.label}' ({s.id}) недостижим: нет входящих стрелок")

        if is_gateway_or(s.type):
            if len(out_edges) < 2:
                errors.append(
                    f"Gateway ИЛИ '{s.label}' ({s.id}) должен иметь минимум 2 исходящих "
                    f"ветки (сейчас: {len(out_edges)})"
                )
            labels = {(e.label or "").strip().lower() for e in out_edges}
            labels.discard("")
            route_mode = str(s.config.get("mode", "")).lower() in (
                "route_skill",
                "route_by_skill",
                "classify",
            )
            if route_mode:
                if len(out_edges) >= 2 and not labels:
                    errors.append(
                        f"Gateway ИЛИ '{s.label}' ({s.id}): mode=route_skill — задайте метки "
                        f"веток (skill id), например business-requirements / system-requirements"
                    )
            else:
                missing = [x for x in ("yes", "no") if x not in labels]
                if missing and len(out_edges) >= 2:
                    errors.append(
                        f"Gateway ИЛИ '{s.label}' ({s.id}): задайте метки веток yes/no "
                        f"(не хватает: {', '.join(missing)})"
                    )

        if is_gateway_and(s.type):
            if len(out_edges) < 2 and len(in_edges) < 2:
                errors.append(
                    f"Gateway И '{s.label}' ({s.id}): нужен fork (≥2 исходящих) "
                    f"или join (≥2 входящих)"
                )

        if s.type == StepType.SKILL and not s.skill_id:
            errors.append(f"Шаг '{s.label}' ({s.id}): не выбран skill_id")
        if s.type == StepType.SCRIPT and not (s.script_id or s.system_handler):
            errors.append(f"Шаг '{s.label}' ({s.id}): не выбран script_id")

        if (
            s.type == StepType.SKILL
            and (s.skill_id or "") in ("classify", "classify-task")
            and len(out_edges) >= 2
        ):
            labeled = [e for e in out_edges if (e.label or "").strip()]
            if labeled and len(labeled) < 2 and not any(not (e.label or "").strip() for e in out_edges):
                errors.append(
                    f"Classify '{s.label}' ({s.id}): при нескольких исходящих рёбрах "
                    f"задайте метки skill id или одно default/непомеченное ребро"
                )

    _validate_process_shell(template, enabled, outs, errors)

    if len(starts) == 1:
        reachable = _reachable_from(starts[0].id, outs)
        for s in enabled:
            if s.id not in reachable:
                errors.append(
                    f"Шаг '{s.label}' ({s.id}) недостижим из Start"
                )
        if ends and all(e.id not in reachable for e in ends):
            errors.append("End недостижим из Start")
        start_pb = find_start_playbook(template)
        end_pb = find_end_playbook(template)
        if start_pb and start_pb.id not in reachable:
            errors.append("Start Playbook недостижим из Start")
        if end_pb and start_pb:
            body_reach = _reachable_from(start_pb.id, outs)
            if end_pb.id not in body_reach:
                errors.append("End Playbook недостижим из Start Playbook")

    return errors
