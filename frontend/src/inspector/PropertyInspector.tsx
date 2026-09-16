/**
 * Scenario inspector: trigger / action / condition / input.
 */
import { useEffect, useState } from "react";
import type { GraphKind, NodeRegistryEntry, NodeType, WorkflowGraph, WorkflowNode } from "../types";
import { createApi } from "../api/client";
import { nextPortId } from "../canvas/ports";
import {
  ARTIFACT_TYPES,
  artifactLabel,
  artifactLabels,
  isGovernanceNode,
} from "../governance";

const ACTION_TYPES: { type: NodeType; label: string }[] = [
  { type: "webhook", label: "Webhook" },
  { type: "ai_agent", label: "AI Agent" },
  { type: "ai", label: "AI" },
  { type: "upsert_entity", label: "Upsert entity" },
  { type: "kafka", label: "Kafka" },
  { type: "integration_action", label: "Integration action" },
  { type: "internal_service", label: "Internal service" },
  { type: "subflow", label: "Subflow" },
];

/** Trigger types from AGSW-485 table: Self-Service / Event / Schedule. */
const TRIGGER_TYPES: { value: string; label: string }[] = [
  { value: "SELF_SERVE_TRIGGER", label: "Self-Service Trigger" },
  { value: "EVENT_TRIGGER", label: "Event trigger" },
  { value: "SCHEDULE_TRIGGER", label: "Schedule trigger" },
];

const EVENT_TYPES: { value: string; label: string }[] = [
  { value: "ENTITY_CREATED", label: "ENTITY_CREATED — создание сущности" },
  { value: "ENTITY_UPDATED", label: "ENTITY_UPDATED — обновление сущности" },
  { value: "ENTITY_DELETED", label: "ENTITY_DELETED — удаление сущности" },
  { value: "ANY_ENTITY_CHANGE", label: "ANY_ENTITY_CHANGE — любое изменение" },
  { value: "TIMER_EXPIRED", label: "TIMER_EXPIRED — истечение таймера" },
];

function normalizeTriggerType(raw: string): string {
  const t = raw.trim().toUpperCase();
  if (t === "SELF_SERVICE" || t === "SELF_SERVE" || t === "HUMAN_FORM") return "SELF_SERVE_TRIGGER";
  if (t === "EVENT" || t === "CATALOG_EVENT" || t === "AUTOMATION") return "EVENT_TRIGGER";
  if (t === "SCHEDULE" || t === "CRON") return "SCHEDULE_TRIGGER";
  return t || "SELF_SERVE_TRIGGER";
}

type Props = {
  node: WorkflowNode | null;
  entry: NodeRegistryEntry | undefined;
  kind: GraphKind;
  graph: WorkflowGraph;
  issues?: { code: string; message: string; severity?: string }[];
  checklist?: { kind: string; message: string; severity?: string; node_id?: string; label?: string }[];
  onChange: (node: WorkflowNode) => void;
  onChangeType?: (nodeId: string, nextType: NodeType, config: Record<string, unknown>, label?: string) => void;
  onChangeGraphMeta?: (patch: Partial<WorkflowGraph>) => void;
  onDeleteNode?: (nodeId: string) => void;
  apiBase?: string;
  onSavePreset?: (node: WorkflowNode) => Promise<void> | void;
};

export function PropertyInspector(props: Props) {
  const { node, kind, graph, issues = [], checklist = [], onChange, onChangeType, onChangeGraphMeta, onDeleteNode } = props;

  if (!node) {
    const fromSteps = (graph.nodes || [])
      .filter((n) => !isGovernanceNode(n) && n.config?.produces)
      .map((n) => ({ id: n.id, label: n.label, type: String(n.config?.produces || "") }))
      .filter((n) => n.type);
    return (
      <div className="ginspector">
        <h3>Сценарий</h3>
        <p className="muted">
          Это свойства всего сценария. Клик по шагу открывает его настройки.
        </p>
        <label className="gfield">
          <span>Название</span>
          <input value={graph.name || ""} onChange={(e) => onChangeGraphMeta?.({ name: e.target.value })} />
        </label>
        <label className="gfield">
          <span>Описание</span>
          <textarea
            rows={3}
            value={graph.description || ""}
            onChange={(e) => onChangeGraphMeta?.({ description: e.target.value })}
          />
        </label>
        <div className="gfield">
          <span>Артефакты по веткам</span>
          <p className="muted">
            Gate один на параллельную ветку: достаточно, чтобы тип артефакта стоял
            хотя бы на одном шаге пути. Если на ветке типа нет, при сохранении
            подставится общий. Промежуточные агенты (сжатие треда, извлечение фактов)
            тип ставить не обязаны.
          </p>
          {fromSteps.length ? (
            <ul className="gready gready--ok" style={{ listStyle: "none", padding: "8px 10px", margin: 0 }}>
              {fromSteps.map((s) => (
                <li key={s.id} className="gready__row">
                  {s.label || s.id} → {artifactLabel(s.type)}
                </li>
              ))}
            </ul>
          ) : (
            <div className="gready gready--wait">
              <div className="gready__row">
                На любой шаг ветки поставьте тип или навык каталога — gate встанет в конце пути, перед слиянием.
              </div>
            </div>
          )}
        </div>
        {(checklist.length > 0 || issues.length > 0) && (
          <div className="gchecklist">
            <h4 className="ginspector__sub">Проблемы</h4>
            {checklist.slice(0, 8).map((c, i) => (
              <div key={i} className={`gissue ${c.severity || "error"}`}>{c.message}</div>
            ))}
            {issues.slice(0, 6).map((i, idx) => (
              <div key={`v${idx}`} className={`gissue ${i.severity || "error"}`}>{i.message || i.code}</div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const cfg = { ...(node.config || {}) };
  const locked = isGovernanceNode(node);
  const family = familyOf(node.type);
  const produceHint = artifactLabels(
    Array.isArray(cfg.produces)
      ? (cfg.produces as string[])
      : (cfg.produces ? [String(cfg.produces)] : []),
  );
  const producerId = String(cfg.producer || "");

  const setCfg = (key: string, value: unknown) => onChange({ ...node, config: { ...cfg, [key]: value } });
  const setCfgMany = (patch: Record<string, unknown>) => onChange({ ...node, config: { ...cfg, ...patch } });

  return (
    <div className="ginspector">
      <div className="ginspector__head">
        <div>
          <h3>
            {locked
              ? "Обязательные проверки"
              : family === "trigger"
                ? "Trigger"
                : family === "action"
                  ? "Action"
                  : family === "flow"
                    ? "Condition"
                    : family === "input"
                      ? "Input"
                      : node.type}
          </h3>
          <p className="muted">ID: <code>{node.id}</code></p>
        </div>
      </div>

      <label className="gfield">
        <span>Название (title)</span>
        <input value={node.label} disabled={locked && node.id === "start"} onChange={(e) => onChange({ ...node, label: e.target.value })} />
      </label>
      <label className="gfield">
        <span>Описание (description)</span>
        <textarea rows={2} value={String(cfg.description || "")} onChange={(e) => setCfg("description", e.target.value)} />
      </label>
      {locked && (
        <div className="gfield">
          <span>Применённые controls</span>
          <ul className="gchecklist">
            {((cfg.packs as { key?: string; name?: string; enforcement?: string }[]) || []).map((p) => (
              <li key={String(p.key || p.name)} className="gissue">
                {p.name || p.key} · {p.enforcement || "BLOCK"}
              </li>
            ))}
          </ul>
          <p className="muted">
            {producerId
              ? `Проверяет артефакт ветки (шаг «${producerId}»${produceHint ? `, ${produceHint}` : ""}). У другой параллельной ветки свой gate.`
              : produceHint
                ? `Пакеты для типа: ${produceHint}.`
                : "Пакеты зависят от типов артефактов на этой ветке."}
            {" "}С холста его не удаляют: уберите шаги ветки — gate снимется. При сохранении компилятор пересоберёт проверки заново.
          </p>
        </div>
      )}

      {family !== "trigger" && !locked && (
        <label className="gfield">
          <span>icon</span>
          <input value={String(cfg.icon || "")} placeholder="optional" onChange={(e) => setCfg("icon", e.target.value)} />
        </label>
      )}

      {family === "trigger" && (
        <TriggerForm cfg={cfg} setCfg={setCfg} setCfgMany={setCfgMany} />
      )}

      {family === "input" && (
        <InputFields cfg={cfg} setCfg={setCfg} setCfgMany={setCfgMany} locked={locked} nodeId={node.id} />
      )}

      {family === "action" && !locked && (
        <>
          <label className="gfield">
            <span>Тип action</span>
            <select
              value={node.type}
              disabled={locked}
              onChange={(e) => {
                const t = e.target.value as NodeType;
                onChangeType?.(node.id, t, defaultConfigFor(t), ACTION_TYPES.find((a) => a.type === t)?.label);
              }}
            >
              {ACTION_TYPES.map((a) => (
                <option key={a.type} value={a.type}>{a.label}</option>
              ))}
            </select>
          </label>
          <ActionFields
            type={node.type}
            cfg={cfg}
            setCfg={setCfg}
            setCfgMany={setCfgMany}
            kind={kind}
            apiBase={props.apiBase}
            currentGraphId={graph.graphId}
            onTitle={(label: string) => onChange({ ...node, label })}
          />
          <CommonActionFields cfg={cfg} setCfg={setCfg} />
        </>
      )}

      {family === "flow" && (
        <>
          {(node.type === "condition" || node.type === "branch") && (
            <OutletsEditor
              outlets={readConditionOptions(node)}
              onChange={(options) => setCfgMany({ type: "CONDITION", options })}
            />
          )}
        </>
      )}

      <details className="gadvanced" open={false}>
        <summary>Data out (testOutputs)</summary>
        <p className="muted">Для Test run: JSON вместо реального исполнения.</p>
        <textarea
          rows={4}
          value={stringifyJson(cfg.testOutputs ?? "")}
          placeholder='{"response":{"ok":true}}'
          onChange={(e) => {
            const t = e.target.value.trim();
            if (!t) {
              const next = { ...cfg };
              delete next.testOutputs;
              onChange({ ...node, config: next });
              return;
            }
            setCfg("testOutputs", parseJson(t, cfg.testOutputs));
          }}
        />
      </details>

      <DataFlowHelp nodeId={node.id} />

      {locked && <p className="gwarn">Это проверка ветки. Удалите шаги самой ветки — gate снимется сам. С холста его вырезать нельзя.</p>}
      {!locked && (
        <button
          type="button"
          className="gbtn"
          onClick={() => props.onSavePreset?.(node)}
        >
          Сохранить как шаблон
        </button>
      )}
      {!locked && node.type !== "trigger" && (
        <button type="button" className="gbtn gbtn--danger" onClick={() => onDeleteNode?.(node.id)}>Удалить шаг</button>
      )}
    </div>
  );
}

function TriggerForm({ cfg, setCfg, setCfgMany }: any) {
  const tt = normalizeTriggerType(String(cfg.triggerType || cfg.type || "SELF_SERVE_TRIGGER"));
  const event = (cfg.event || {}) as Record<string, unknown>;
  const condition = (cfg.condition || {}) as Record<string, unknown>;
  const expressions = Array.isArray(condition.expressions) ? condition.expressions.map(String) : [];
  const eventType = String(event.type || "ENTITY_UPDATED");
  return (
    <>
      <label className="gfield">
        <span>Тип</span>
        <select
          value={TRIGGER_TYPES.some((x) => x.value === tt) ? tt : "SELF_SERVE_TRIGGER"}
          onChange={(e) => {
            const next = e.target.value;
            const patch: Record<string, unknown> = { triggerType: next, type: next };
            if (next === "EVENT_TRIGGER" && !cfg.event) {
              patch.event = { type: "ENTITY_UPDATED", blueprintIdentifier: "" };
            }
            if (next === "SCHEDULE_TRIGGER" && !cfg.cron) patch.cron = "0 9 * * 1-5";
            if (next === "SELF_SERVE_TRIGGER" && !cfg.userInputs) {
              patch.userInputs = { properties: {}, required: [] };
            }
            setCfgMany(patch);
          }}
        >
          {TRIGGER_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </label>
      <p className="muted">
        {tt === "SELF_SERVE_TRIGGER" && "Ручной запуск из UI. Входы задаются в userInputs."}
        {tt === "EVENT_TRIGGER" && "Автозапуск при изменении сущности в каталоге."}
        {tt === "SCHEDULE_TRIGGER" && "Автозапуск по повторяющемуся cron-правилу."}
      </p>
      <label className="gfield">
        <span>published</span>
        <select value={cfg.published === false ? "false" : "true"} onChange={(e) => setCfg("published", e.target.value === "true")}>
          <option value="true">true — триггер активен</option>
          <option value="false">false — скрыт, запустить нельзя</option>
        </select>
      </label>
      {tt === "SELF_SERVE_TRIGGER" && (
        <UserInputsEditor value={cfg.userInputs || { properties: {}, required: [] }} onChange={(v: any) => setCfg("userInputs", v)} />
      )}
      {tt === "SCHEDULE_TRIGGER" && (
        <label className="gfield">
          <span>cron</span>
          <input value={String(cfg.cron || "")} placeholder="0 9 * * 1-5" onChange={(e) => setCfg("cron", e.target.value)} />
        </label>
      )}
      {tt === "EVENT_TRIGGER" && (
        <>
          <label className="gfield">
            <span>Тип события</span>
            <select
              value={EVENT_TYPES.some((x) => x.value === eventType) ? eventType : "ENTITY_UPDATED"}
              onChange={(e) => setCfg("event", { ...event, type: e.target.value })}
            >
              {EVENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>
          <label className="gfield">
            <span>event.blueprintIdentifier</span>
            <input
              value={String(event.blueprintIdentifier || "")}
              onChange={(e) => setCfg("event", { ...event, blueprintIdentifier: e.target.value })}
            />
          </label>
          {eventType === "TIMER_EXPIRED" && (
            <label className="gfield">
              <span>event.propertyIdentifier</span>
              <input
                value={String(event.propertyIdentifier || "")}
                placeholder="ttl"
                onChange={(e) => setCfg("event", { ...event, propertyIdentifier: e.target.value })}
              />
            </label>
          )}
          <label className="gfield">
            <span>condition.type</span>
            <input value="JQ" disabled />
          </label>
          <label className="gfield">
            <span>condition.combinator</span>
            <select
              value={String(condition.combinator || "and")}
              onChange={(e) => setCfg("condition", { type: "JQ", combinator: e.target.value, expressions })}
            >
              <option value="and">and</option>
              <option value="or">or</option>
            </select>
          </label>
          <label className="gfield">
            <span>condition.expressions (JQ, по одному на строку)</span>
            <textarea
              rows={3}
              placeholder={'.diff.after.status == "active"'}
              value={expressions.join("\n")}
              onChange={(e) =>
                setCfg("condition", {
                  type: "JQ",
                  combinator: condition.combinator || "and",
                  expressions: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                })
              }
            />
          </label>
        </>
      )}
    </>
  );
}

function CommonActionFields({ cfg, setCfg }: { cfg: Record<string, unknown>; setCfg: (k: string, v: unknown) => void }) {
  const links = Array.isArray(cfg.links) ? (cfg.links as string[]) : [];
  return (
    <details className="gadvanced">
      <summary>Общие поля action (variables, links, verbose)</summary>
      <label className="gfield">
        <span>verbose</span>
        <select value={cfg.verbose ? "true" : "false"} onChange={(e) => setCfg("verbose", e.target.value === "true")}>
          <option value="false">false</option>
          <option value="true">true</option>
        </select>
      </label>
      <label className="gfield">
        <span>variables (JSON object)</span>
        <textarea rows={3} value={stringifyJson(cfg.variables || {})} onChange={(e) => setCfg("variables", parseJson(e.target.value, {}))} />
      </label>
      <label className="gfield">
        <span>links (до 3 URL, по одному на строку)</span>
        <textarea
          rows={3}
          value={links.join("\n")}
          onChange={(e) => setCfg("links", e.target.value.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 3))}
        />
      </label>
    </details>
  );
}

function ActionFields({ type, cfg, setCfg, setCfgMany, kind, apiBase, currentGraphId, onTitle }: any) {
  if (type === "webhook" || type === "tool") {
    return (
      <>
        <label className="gfield"><span>url</span>
          <input value={String(cfg.url || "")} onChange={(e) => setCfgMany({ url: e.target.value, type: "WEBHOOK" })} /></label>
        <label className="gfield"><span>method</span>
          <select value={String(cfg.method || "POST")} onChange={(e) => setCfg("method", e.target.value)}>
            {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => <option key={m}>{m}</option>)}
          </select></label>
        <label className="gfield"><span>agent</span>
          <select value={cfg.agent ? "true" : "false"} onChange={(e) => setCfg("agent", e.target.value === "true")}>
            <option value="false">false</option>
            <option value="true">true</option>
          </select></label>
        <label className="gfield"><span>headers (JSON)</span>
          <textarea rows={2} value={stringifyJson(cfg.headers || {})} onChange={(e) => setCfg("headers", parseJson(e.target.value, {}))} /></label>
        <label className="gfield"><span>body (JSON)</span>
          <textarea rows={3} value={stringifyJson(cfg.body ?? {})} onChange={(e) => setCfg("body", parseJson(e.target.value, {}))} /></label>
        <label className="gfield"><span>synchronized</span>
          <select value={cfg.synchronized === false ? "false" : "true"} onChange={(e) => setCfg("synchronized", e.target.value === "true")}>
            <option value="true">true</option>
            <option value="false">false</option>
          </select></label>
        <label className="gfield"><span>onTimeout</span>
          <select value={String(cfg.onTimeout || "fail")} onChange={(e) => setCfg("onTimeout", e.target.value)}>
            <option value="fail">fail</option>
            <option value="continue">continue</option>
          </select></label>
        <label className="gfield"><span>onFailure</span>
          <select value={String(cfg.onFailure || "terminate")} onChange={(e) => setCfg("onFailure", e.target.value)}>
            <option value="terminate">terminate</option>
            <option value="continue">continue</option>
          </select></label>
      </>
    );
  }
  if (type === "ai_agent" || type === "agent") {
    return (
      <>
        <SkillsPicker cfg={cfg} setCfgMany={setCfgMany} apiBase={apiBase} />
        <label className="gfield"><span>agentIdentifier</span>
          <input
            value={String(cfg.agentIdentifier || "")}
            placeholder="incident-response-agent"
            onChange={(e) => setCfgMany({ agentIdentifier: e.target.value, type: "AI_AGENT" })}
          /></label>
        <label className="gfield"><span>userPrompt (опционально)</span>
          <textarea
            rows={3}
            placeholder="Необязательно, если выбран навык — SKILL.md задаёт поведение"
            value={String(cfg.userPrompt || "")}
            onChange={(e) => setCfgMany({ userPrompt: e.target.value, type: "AI_AGENT" })}
          /></label>
        <p className="muted">
          При возврате с Human Input комментарий доработки подставится автоматически.
          Можно явно: <code>{"{{feedback}}"}</code>.
        </p>
        <label className="gfield"><span>outputSchema (JSON)</span>
          <textarea rows={3} value={stringifyJson(cfg.outputSchema || "")} onChange={(e) => setCfg("outputSchema", parseJson(e.target.value, null))} /></label>
        <label className="gfield">
          <span>Тип артефакта</span>
          <select
            value={String(cfg.produces || "")}
            onChange={(e) => setCfgMany({ produces: e.target.value || undefined, type: "AI_AGENT" })}
          >
            <option value="">из навыка, если это генератор BRD/SRD/…</option>
            <option value="NONE">промежуточный шаг — артефакт не выпускает</option>
            {ARTIFACT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <p className="muted">
            Достаточно типа на любом шаге этой ветки — gate встанет в конце пути.
            Промежуточные преобразования можно оставить без типа или «не выпускает».
          </p>
        </label>
      </>
    );
  }
  if (type === "ai") {
    return (
      <>
        <label className="gfield"><span>userPrompt</span>
          <textarea rows={3} value={String(cfg.userPrompt || "")} onChange={(e) => setCfgMany({ userPrompt: e.target.value, type: "AI" })} /></label>
        <label className="gfield"><span>systemPrompt</span>
          <textarea rows={2} value={String(cfg.systemPrompt || "")} onChange={(e) => setCfg("systemPrompt", e.target.value)} /></label>
        <label className="gfield"><span>tools (через запятую)</span>
          <input
            value={Array.isArray(cfg.tools) ? (cfg.tools as string[]).join(", ") : ""}
            placeholder="list_blueprints, list_entities"
            onChange={(e) => setCfg("tools", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
          /></label>
        <label className="gfield"><span>provider</span>
          <input value={String(cfg.provider || "")} onChange={(e) => setCfg("provider", e.target.value)} /></label>
        <label className="gfield"><span>model</span>
          <input value={String(cfg.model || "")} onChange={(e) => setCfg("model", e.target.value)} /></label>
        <label className="gfield"><span>outputSchema (JSON)</span>
          <textarea rows={3} value={stringifyJson(cfg.outputSchema || "")} onChange={(e) => setCfg("outputSchema", parseJson(e.target.value, null))} /></label>
        <label className="gfield"><span>mcpServers (JSON array, до 5)</span>
          <textarea rows={2} value={stringifyJson(cfg.mcpServers || "")} onChange={(e) => setCfg("mcpServers", parseJson(e.target.value, []))} /></label>
      </>
    );
  }
  if (type === "upsert_entity") {
    return (
      <>
        <label className="gfield"><span>blueprintIdentifier</span>
          <input value={String(cfg.blueprintIdentifier || "")} onChange={(e) => setCfgMany({ blueprintIdentifier: e.target.value, type: "UPSERT_ENTITY" })} /></label>
        <label className="gfield"><span>mapping (JSON)</span>
          <textarea rows={5} value={stringifyJson(cfg.mapping || {})} onChange={(e) => setCfg("mapping", parseJson(e.target.value, {}))} /></label>
      </>
    );
  }
  if (type === "kafka") {
    return (
      <>
        <label className="gfield"><span>payload (JSON)</span>
          <textarea rows={4} value={stringifyJson(cfg.payload ?? {})} onChange={(e) => setCfgMany({ payload: parseJson(e.target.value, {}), type: "KAFKA" })} /></label>
        <label className="gfield"><span>onFailure</span>
          <select value={String(cfg.onFailure || "terminate")} onChange={(e) => setCfg("onFailure", e.target.value)}>
            <option value="terminate">terminate</option>
            <option value="continue">continue</option>
          </select></label>
      </>
    );
  }
  if (type === "integration_action") {
    return (
      <>
        <label className="gfield"><span>integrationProvider</span>
          <input value={String(cfg.integrationProvider || "github-ocean")} onChange={(e) => setCfgMany({ integrationProvider: e.target.value, type: "INTEGRATION_ACTION" })} /></label>
        <label className="gfield"><span>repo</span>
          <input value={String(cfg.repo || "")} onChange={(e) => setCfg("repo", e.target.value)} /></label>
        <label className="gfield"><span>workflow</span>
          <input value={String(cfg.workflow || "")} onChange={(e) => setCfg("workflow", e.target.value)} /></label>
        <label className="gfield"><span>workflowInputs (JSON)</span>
          <textarea rows={3} value={stringifyJson(cfg.workflowInputs || {})} onChange={(e) => setCfg("workflowInputs", parseJson(e.target.value, {}))} /></label>
      </>
    );
  }
  if (type === "subflow") {
    return (
      <SubflowPicker
        cfg={cfg}
        setCfgMany={setCfgMany}
        apiBase={apiBase}
        currentGraphId={currentGraphId}
        onTitle={onTitle}
      />
    );
  }
  if (type === "internal_service") {
    return (
      <>
        <label className="gfield"><span>service</span>
          <input value={String(cfg.service || "")} onChange={(e) => setCfgMany({ service: e.target.value, type: "INTERNAL_SERVICE" })} /></label>
        <label className="gfield"><span>parameter (JSON)</span>
          <textarea rows={3} value={stringifyJson(cfg.parameter || {})} onChange={(e) => setCfg("parameter", parseJson(e.target.value, {}))} /></label>
        <label className="gfield"><span>onTimeout</span>
          <select value={String(cfg.onTimeout || "fail")} onChange={(e) => setCfg("onTimeout", e.target.value)}>
            <option value="fail">fail</option>
            <option value="continue">continue</option>
          </select></label>
        <label className="gfield"><span>onFailure</span>
          <select value={String(cfg.onFailure || "terminate")} onChange={(e) => setCfg("onFailure", e.target.value)}>
            <option value="terminate">terminate</option>
            <option value="continue">continue</option>
          </select></label>
      </>
    );
  }
  return null;
}

type GraphOpt = { id: string; key: string; name: string; kind: string; status?: string };

function SubflowPicker({ cfg, setCfgMany, apiBase, currentGraphId, onTitle }: any) {
  const [graphs, setGraphs] = useState<GraphOpt[]>([]);
  const [err, setErr] = useState("");
  const selectedId = String(cfg.graph_id || "");
  const selectedKey = String(cfg.graph_key || cfg.flow_key || cfg.playbook_key || "");

  useEffect(() => {
    let cancelled = false;
    createApi(apiBase)
      .listGraphs()
      .then((d) => {
        if (cancelled) return;
        setGraphs(
          (d.graphs || []).map((g: any) => ({
            id: String(g.id),
            key: String(g.key),
            name: String(g.name || g.key),
            kind: String(g.kind || "e2e"),
            status: g.status,
          })),
        );
        setErr("");
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e.message || e));
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const usable = graphs.filter((g) => g.id !== currentGraphId && g.key !== currentGraphId);
  const scenarios = usable.filter((g) => g.kind === "e2e");
  const stages = usable.filter((g) => g.kind === "stage");
  const selected = usable.find((g) => g.id === selectedId || g.key === selectedKey);
  const selectValue = selected ? selected.id : "";

  return (
    <>
      <label className="gfield">
        <span>Целевой сценарий</span>
        <select
          value={selectValue}
          onChange={(e) => {
            const g = graphs.find((x) => x.id === e.target.value);
            if (!g) {
              setCfgMany({ type: "SUBFLOW", graph_id: "", graph_key: "", graph_kind: "", flow_key: "", playbook_key: "" });
              return;
            }
            setCfgMany({
              type: "SUBFLOW",
              graph_id: g.id,
              graph_key: g.key,
              graph_kind: g.kind,
              flow_key: g.kind === "e2e" ? g.key : "",
              playbook_key: g.kind === "stage" ? g.key : "",
            });
            onTitle?.(g.name);
          }}
        >
          <option value="">— выбрать из каталога —</option>
          <optgroup label="Сценарии">
            {scenarios.length === 0 ? <option disabled value="__none_e2e">нет сценариев</option> : null}
            {scenarios.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} ({g.key}){g.status ? ` · ${g.status}` : ""}
              </option>
            ))}
          </optgroup>
          <optgroup label="Другие графы">
            {stages.length === 0 ? <option disabled value="__none_stage">нет графов</option> : null}
            {stages.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} ({g.key}){g.status ? ` · ${g.status}` : ""}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      {selected ? (
        <p className="muted">
          {selected.kind === "stage" ? "Граф" : "Сценарий"}: <code>{selected.key}</code>
        </p>
      ) : null}
      <label className="gfield">
        <span>input (JSON в дочерний запуск)</span>
        <textarea
          rows={3}
          value={stringifyJson(cfg.input || cfg.parameter || {})}
          onChange={(e) => setCfgMany({ type: "SUBFLOW", input: parseJson(e.target.value, {}) })}
        />
      </label>
      {err ? <p className="gwarn">Не удалось загрузить каталог: {err}</p> : null}
    </>
  );
}

type SkillOpt = { id: string; key: string; name: string; status?: string };

function readSkillKeys(cfg: Record<string, unknown>): string[] {
  const raw = cfg.skill_keys;
  if (Array.isArray(raw) && raw.length) {
    return raw.map((k) => String(k).trim()).filter(Boolean);
  }
  const single = String(cfg.agentIdentifier || cfg.skill_key || "").trim();
  return single ? [single] : [];
}

function SkillsPicker({ cfg, setCfgMany, apiBase }: any) {
  const [skills, setSkills] = useState<SkillOpt[]>([]);
  const [query, setQuery] = useState("");
  const [err, setErr] = useState("");
  const selected = readSkillKeys(cfg);

  useEffect(() => {
    let cancelled = false;
    createApi(apiBase)
      .listSkills()
      .then((d) => {
        if (cancelled) return;
        setSkills(
          (d.skills || []).map((s: any) => ({
            id: String(s.id),
            key: String(s.key),
            name: String(s.name || s.key),
            status: s.status,
          })),
        );
        setErr("");
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e.message || e));
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const sync = (keys: string[]) => {
    const primary = keys[0] || "";
    setCfgMany({
      type: "AI_AGENT",
      skill_keys: keys,
      skill_key: primary,
      agentIdentifier: primary,
    });
  };

  const filtered = skills.filter((s) => {
    if (!query.trim()) return true;
    const q = query.trim().toLowerCase();
    return s.name.toLowerCase().includes(q) || s.key.toLowerCase().includes(q);
  });

  const selectedMeta = selected.map((key) => skills.find((s) => s.key === key) || { id: key, key, name: key });

  return (
    <div className="goutcomes">
      <div className="goutcomes__title">Навыки</div>
      <p className="muted">Выберите один или несколько skills из каталога.</p>
      {selectedMeta.length > 0 && (
        <div className="gskills__selected">
          {selectedMeta.map((s) => (
            <span key={s.key} className="gskills__tag">
              <span>{s.name}</span>
              <button
                type="button"
                className="gskills__tag-x"
                title="Убрать навык"
                onClick={() => sync(selected.filter((k) => k !== s.key))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <label className="gfield">
        <span>Поиск</span>
        <input value={query} placeholder="имя или ключ…" onChange={(e) => setQuery(e.target.value)} />
      </label>
      <label className="gfield">
        <span>Добавить навык</span>
        <select
          value=""
          onChange={(e) => {
            const key = e.target.value;
            if (!key || selected.includes(key)) return;
            sync([...selected, key]);
          }}
        >
          <option value="">— выбрать из БД —</option>
          {filtered
            .filter((s) => !selected.includes(s.key))
            .map((s) => (
              <option key={s.id} value={s.key}>
                {s.name} ({s.key}){s.status ? ` · ${s.status}` : ""}
              </option>
            ))}
        </select>
      </label>
      {err ? <p className="gwarn">Не удалось загрузить skills: {err}</p> : null}
      {!err && skills.length === 0 ? <p className="muted">Каталог skills пуст.</p> : null}
    </div>
  );
}

/** Human-in-the-loop INPUT: form fields, buttons, outlets. */
function InputFields({ cfg, setCfg, setCfgMany, locked, nodeId }: any) {
  const ui = (cfg.userInputs || {}) as Record<string, any>;
  const properties = (ui.properties || {}) as Record<string, any>;
  const required: string[] = Array.isArray(ui.required) ? ui.required.map(String) : [];
  const buttons: any[] = Array.isArray(ui.buttons) && ui.buttons.length
    ? ui.buttons
    : [
        { identifier: "approve", label: "Approve", variant: "PRIMARY" },
        { identifier: "decline", label: "Decline", variant: "DANGER" },
      ];
  const outlets: any[] = Array.isArray(cfg.outlets) && cfg.outlets.length
    ? cfg.outlets
    : buttons.map((b) => ({
        evaluationMethod: "button",
        identifier: b.identifier,
        title: b.label,
        numOfResponders: 1,
      }));

  const patchUserInputs = (nextUi: Record<string, any>, nextOutlets?: any[]) => {
    setCfgMany({
      type: "INPUT",
      userInputs: nextUi,
      outlets: nextOutlets || outlets,
    });
  };

  const syncButtons = (nextButtons: any[]) => {
    const nextOutlets = nextButtons.map((b) => {
      const prev = outlets.find((o) => o.identifier === b.identifier);
      return {
        evaluationMethod: "button",
        identifier: b.identifier,
        title: prev?.title || b.label,
        numOfResponders: Number(prev?.numOfResponders) > 0 ? Number(prev.numOfResponders) : 1,
      };
    });
    patchUserInputs({ ...ui, properties, required, buttons: nextButtons }, nextOutlets);
  };

  const applyApproveDecline = () => {
    const nextButtons = [
      { identifier: "approve", label: "Approve", variant: "PRIMARY" },
      { identifier: "decline", label: "Decline", variant: "DANGER" },
    ];
    setCfgMany({
      type: "INPUT",
      description: cfg.description || "Approve or decline.",
      userInputs: {
        properties: {
          reason: {
            type: "string",
            title: "Reason",
            description: "The reason for the approve/decline.",
          },
        },
        required: [],
        buttons: nextButtons,
      },
      outlets: [
        { evaluationMethod: "button", identifier: "approve", title: "Approve", numOfResponders: 1 },
        { evaluationMethod: "button", identifier: "decline", title: "Decline", numOfResponders: 1 },
      ],
    });
  };

  const propKeys = Object.keys(properties);

  return (
    <>
      <div className="ghelp-box">
        <strong>INPUT — пауза для человека</strong>
        <p className="muted" style={{ margin: "6px 0 0" }}>
          Кнопки Approve / Decline — это не отдельный UI Slack. Это <b>выходы узла</b>: те же точки
          справа на блоке и стрелки с холста. На Test run, когда сценарий доходит сюда, в панели
          появятся эти кнопки. В живом Slack-запуске решение приходит сигналом в тот же outlet.
        </p>
        <div className="goutcomes__presets">
          <button type="button" className="gchip" disabled={locked} onClick={applyApproveDecline}>
            Approve / Decline
          </button>
        </div>
      </div>

      <label className="gfield">
        <span>description</span>
        <textarea
          rows={2}
          disabled={locked}
          placeholder="Approve or decline the production deployment."
          value={String(cfg.description || "")}
          onChange={(e) => setCfgMany({ description: e.target.value, type: "INPUT" })}
        />
      </label>

      <details className="gdetails">
        <summary>Уведомления и responders</summary>
        <label className="gfield">
          <span>responders.users (emails, через запятую)</span>
          <input
            disabled={locked}
            value={Array.isArray(cfg.responders?.users) ? cfg.responders.users.join(", ") : ""}
            onChange={(e) =>
              setCfg("responders", {
                users: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean),
              })
            }
          />
        </label>
        <label className="gfield">
          <span>notifications (JSON array, напр. Slack chat.postMessage)</span>
          <textarea
            rows={3}
            disabled={locked}
            placeholder='[{"type":"webhook","url":"https://slack.com/api/chat.postMessage"}]'
            value={stringifyJson(cfg.notifications || "")}
            onChange={(e) => setCfg("notifications", parseJson(e.target.value, []))}
          />
        </label>
      </details>

      <div className="goutcomes">
        <div className="goutcomes__title">userInputs.properties (форма)</div>
        {propKeys.map((key) => {
          const p = properties[key] || {};
          const enumStr = Array.isArray(p.enum) ? p.enum.join(", ") : "";
          return (
            <div key={key} className="goutcomes__col">
              <div className="goutcomes__row">
                <input
                  disabled={locked}
                  title="field key"
                  value={key}
                  onChange={(e) => {
                    const nextKey = e.target.value.trim() || key;
                    const next = { ...properties };
                    delete next[key];
                    next[nextKey] = p;
                    const nextReq = required.map((r) => (r === key ? nextKey : r));
                    patchUserInputs({ ...ui, properties: next, required: nextReq, buttons });
                  }}
                />
                <select
                  disabled={locked}
                  value={String(p.type || "string")}
                  onChange={(e) => {
                    patchUserInputs({
                      ...ui,
                      properties: { ...properties, [key]: { ...p, type: e.target.value } },
                      required,
                      buttons,
                    });
                  }}
                >
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="boolean">boolean</option>
                </select>
                <label className="gchip" title="required">
                  <input
                    type="checkbox"
                    disabled={locked}
                    checked={required.includes(key)}
                    onChange={(e) => {
                      const nextReq = e.target.checked
                        ? [...required.filter((r) => r !== key), key]
                        : required.filter((r) => r !== key);
                      patchUserInputs({ ...ui, properties, required: nextReq, buttons });
                    }}
                  />{" "}
                  req
                </label>
                <button
                  type="button"
                  className="gchip gchip--danger"
                  disabled={locked}
                  onClick={() => {
                    const next = { ...properties };
                    delete next[key];
                    patchUserInputs({
                      ...ui,
                      properties: next,
                      required: required.filter((r) => r !== key),
                      buttons,
                    });
                  }}
                >
                  ×
                </button>
              </div>
              <input
                disabled={locked}
                placeholder="title"
                value={String(p.title || "")}
                onChange={(e) =>
                  patchUserInputs({
                    ...ui,
                    properties: { ...properties, [key]: { ...p, title: e.target.value } },
                    required,
                    buttons,
                  })
                }
              />
              <input
                disabled={locked}
                placeholder="description"
                value={String(p.description || "")}
                onChange={(e) =>
                  patchUserInputs({
                    ...ui,
                    properties: { ...properties, [key]: { ...p, description: e.target.value } },
                    required,
                    buttons,
                  })
                }
              />
              <input
                disabled={locked}
                className="goutcomes__expr"
                placeholder='enum: approve, request_change, reject'
                value={enumStr}
                onChange={(e) => {
                  const vals = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                  const nextP = { ...p };
                  if (vals.length) nextP.enum = vals;
                  else delete nextP.enum;
                  patchUserInputs({
                    ...ui,
                    properties: { ...properties, [key]: nextP },
                    required,
                    buttons,
                  });
                }}
              />
            </div>
          );
        })}
        <button
          type="button"
          className="gchip"
          disabled={locked}
          onClick={() => {
            const id = `field${propKeys.length + 1}`;
            patchUserInputs({
              ...ui,
              properties: { ...properties, [id]: { type: "string", title: id } },
              required,
              buttons,
            });
          }}
        >
          + property
        </button>
      </div>

      <div className="goutcomes">
        <div className="goutcomes__title">Кнопки = выходы узла (точки справа)</div>
        <p className="muted" style={{ margin: "0 0 8px" }}>
          identifier кнопки должен совпадать с подписью стрелки (approve / decline). Меняете кнопку —
          меняется выход.
        </p>
        {buttons.map((b, idx) => (
          <div key={idx} className="goutcomes__row">
            <input
              disabled={locked}
              title="identifier"
              placeholder="identifier"
              value={String(b.identifier || "")}
              onChange={(e) => {
                const n = buttons.slice();
                n[idx] = { ...b, identifier: e.target.value.trim() };
                syncButtons(n);
              }}
            />
            <input
              disabled={locked}
              title="label"
              placeholder="label"
              value={String(b.label || "")}
              onChange={(e) => {
                const n = buttons.slice();
                n[idx] = { ...b, label: e.target.value };
                syncButtons(n);
              }}
            />
            <select
              disabled={locked}
              value={String(b.variant || "SECONDARY")}
              onChange={(e) => {
                const n = buttons.slice();
                n[idx] = { ...b, variant: e.target.value };
                syncButtons(n);
              }}
            >
              <option>PRIMARY</option>
              <option>SECONDARY</option>
              <option>DANGER</option>
            </select>
            <button
              type="button"
              className="gchip gchip--danger"
              disabled={locked || buttons.length <= 1}
              onClick={() => syncButtons(buttons.filter((_, i) => i !== idx))}
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          className="gchip"
          disabled={locked}
          onClick={() =>
            syncButtons([
              ...buttons,
              { identifier: `btn${buttons.length + 1}`, label: `Button ${buttons.length + 1}`, variant: "SECONDARY" },
            ])
          }
        >
          + button
        </button>
      </div>

      <details className="gdetails">
        <summary>outlets (служебное, синхронизируется с кнопками)</summary>
        <p className="muted">Обычно не трогайте: это те же identifier, что у кнопок.</p>
        {outlets.map((o, idx) => (
          <div key={idx} className="goutcomes__row">
            <input
              disabled={locked}
              title="identifier"
              placeholder="identifier"
              value={String(o.identifier || "")}
              onChange={(e) => {
                const n = outlets.slice();
                n[idx] = { ...o, identifier: e.target.value.trim(), evaluationMethod: "button" };
                setCfgMany({ type: "INPUT", outlets: n });
              }}
            />
            <input
              disabled={locked}
              title="title"
              placeholder="title"
              value={String(o.title || "")}
              onChange={(e) => {
                const n = outlets.slice();
                n[idx] = { ...o, title: e.target.value };
                setCfgMany({ type: "INPUT", outlets: n });
              }}
            />
            <input
              disabled={locked}
              type="number"
              min={1}
              title="numOfResponders"
              style={{ width: 64 }}
              value={Number(o.numOfResponders) > 0 ? Number(o.numOfResponders) : 1}
              onChange={(e) => {
                const n = outlets.slice();
                n[idx] = { ...o, numOfResponders: Math.max(1, Number(e.target.value) || 1) };
                setCfgMany({ type: "INPUT", outlets: n });
              }}
            />
            <button
              type="button"
              className="gchip gchip--danger"
              disabled={locked || outlets.length <= 1}
              onClick={() => setCfgMany({ type: "INPUT", outlets: outlets.filter((_, i) => i !== idx) })}
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          className="gchip"
          disabled={locked}
          onClick={() =>
            setCfgMany({
              type: "INPUT",
              outlets: [
                ...outlets,
                {
                  evaluationMethod: "button",
                  identifier: `out${outlets.length + 1}`,
                  title: `Outlet ${outlets.length + 1}`,
                  numOfResponders: 1,
                },
              ],
            })
          }
        >
          + outlet
        </button>
      </details>
    </>
  );
}

function slugify(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

function OutletsEditor({
  outlets,
  onChange,
}: {
  outlets: { identifier: string; title: string; expression: string }[];
  onChange: (o: { identifier: string; title: string; expression: string }[]) => void;
}) {
  const usedIds = outlets.map((x) => String(x.identifier || ""));

  const patch = (idx: number, extra: Partial<{ identifier: string; title: string; expression: string }>) => {
    const n = outlets.slice();
    n[idx] = { ...outlets[idx], ...extra };
    onChange(n);
  };

  const rename = (idx: number, title: string) => {
    const prev = outlets[idx];
    const prevSlug = slugify(prev.title);
    const nextSlug = slugify(title);
    const taken = usedIds.filter((_, i) => i !== idx);
    const autoId = !prev.identifier || prev.identifier === prevSlug || /^out\d+$/.test(prev.identifier);
    const identifier =
      autoId && nextSlug && !taken.includes(nextSlug)
        ? nextSlug
        : prev.identifier || nextPortId(usedIds, "out");
    patch(idx, { title, identifier });
  };

  return (
    <div className="goutcomes">
      <div className="goutcomes__title">Выходы</div>
      <p className="muted">
        Каждый выход — точка справа на блоке. Добавьте вариант и протяните с него стрелку к следующему шагу.
      </p>
      {outlets.map((o, idx) => (
        <div key={`out-${idx}`} className="goutcomes__col">
          <div className="goutcomes__row">
            <input
              title="Название на блоке"
              placeholder="Название"
              value={o.title}
              onChange={(e) => rename(idx, e.target.value)}
            />
            <button
              type="button"
              className="gchip gchip--danger"
              disabled={outlets.length <= 1}
              onClick={() => onChange(outlets.filter((_, i) => i !== idx))}
            >
              ×
            </button>
          </div>
          <input
            className="goutcomes__expr"
            title="Ключ выхода"
            placeholder="ключ (id связи)"
            value={o.identifier}
            onChange={(e) => {
              const id = e.target.value.trim().replace(/\s+/g, "_");
              patch(idx, { identifier: id || o.identifier });
            }}
          />
          <input
            className="goutcomes__expr"
            title="Условие"
            placeholder='условие, необязательно'
            value={o.expression || ""}
            onChange={(e) => patch(idx, { expression: e.target.value })}
          />
        </div>
      ))}
      <button
        type="button"
        className="gchip"
        onClick={() => {
          const identifier = nextPortId(usedIds, "out");
          onChange([...outlets, { identifier, title: identifier, expression: "" }]);
        }}
      >
        + Добавить выход
      </button>
    </div>
  );
}

function UserInputsEditor({ value, onChange }: any) {
  const props = value.properties || {};
  const keys = Object.keys(props);
  return (
    <div className="goutcomes">
      <div className="goutcomes__title">userInputs</div>
      {keys.map((key) => (
        <div key={key} className="goutcomes__row">
          <input value={key} disabled />
          <input value={String(props[key]?.title || "")} onChange={(e) => onChange({ ...value, properties: { ...props, [key]: { ...props[key], title: e.target.value } } })} />
          <button type="button" className="gchip gchip--danger" onClick={() => { const n = { ...props }; delete n[key]; onChange({ ...value, properties: n }); }}>×</button>
        </div>
      ))}
      <button type="button" className="gchip" onClick={() => {
        const id = `field${keys.length + 1}`;
        onChange({ ...value, properties: { ...props, [id]: { type: "string", title: id } } });
      }}>+ field</button>
    </div>
  );
}

function DataFlowHelp({ nodeId }: { nodeId?: string }) {
  const id = nodeId || "node-id";
  return (
    <details className="gadvanced">
      <summary>Data flow</summary>
      <p className="muted">
        Связи только маршрутизируют. Контекст запуска копится в{" "}
        <code>.outputs.&lt;id&gt;</code>. Чтобы шаг видел досье, вставьте нужные
        выходы в промпт. При реворке того же шага предыдущий черновик ещё лежит в{" "}
        <code>{`{{ .outputs["${id}"].text }}`}</code> — подставьте его явно, иначе
        агент пишет с нуля.
      </p>
      <pre className="gcode">
{`{{ .outputs.trigger.text }}
{{ .outputs.context_collection.body }}
{{ .outputs["${id}"].text }}
{{ .outputs.review.comment }}
{{ .secrets["api-token"] }}`}
      </pre>
    </details>
  );
}

function familyOf(type: NodeType | string): "trigger" | "action" | "flow" | "input" | "other" {
  if (type === "trigger") return "trigger";
  if (type === "input" || type === "approval") return "input";
  if (type === "condition" || type === "branch") return "flow";
  if (
    [
      "webhook",
      "ai_agent",
      "ai",
      "upsert_entity",
      "kafka",
      "integration_action",
      "internal_service",
      "subflow",
    ].includes(type)
  ) {
    return "action";
  }
  return "other";
}

export function defaultConfigFor(type: NodeType): Record<string, unknown> {
  switch (type) {
    case "trigger":
      return { type: "SELF_SERVE_TRIGGER", published: true, userInputs: { properties: {}, required: [] } };
    case "webhook":
      return { type: "WEBHOOK", url: "", method: "POST", onFailure: "terminate", synchronized: true };
    case "ai_agent":
      return { type: "AI_AGENT", agentIdentifier: "", userPrompt: "" };
    case "ai":
      return { type: "AI", userPrompt: "", systemPrompt: "" };
    case "upsert_entity":
      return { type: "UPSERT_ENTITY", blueprintIdentifier: "", mapping: {} };
    case "kafka":
      return { type: "KAFKA", payload: {} };
    case "integration_action":
      return { type: "INTEGRATION_ACTION", integrationProvider: "", repo: "", workflow: "", workflowInputs: {} };
    case "internal_service":
      return { type: "INTERNAL_SERVICE", service: "", parameter: {} };
    case "subflow":
      return { type: "SUBFLOW", graph_kind: "", graph_key: "", graph_id: "", input: {} };
    case "condition":
      return {
        type: "CONDITION",
        options: [
          { identifier: "yes", title: "Yes", expression: "" },
          { identifier: "no", title: "No", expression: "" },
        ],
      };
    case "input":
      return {
        type: "INPUT",
        description: "",
        userInputs: {
          properties: {
            reason: {
              type: "string",
              title: "Reason",
              description: "The reason for the approve/decline.",
            },
          },
          required: [],
          buttons: [
            { identifier: "approve", label: "Approve", variant: "PRIMARY" },
            { identifier: "decline", label: "Decline", variant: "DANGER" },
          ],
        },
        outlets: [
          { evaluationMethod: "button", identifier: "approve", title: "Approve", numOfResponders: 1 },
          { evaluationMethod: "button", identifier: "decline", title: "Decline", numOfResponders: 1 },
        ],
        responders: { users: [] },
      };
    default:
      return {};
  }
}

function readConditionOptions(node: WorkflowNode) {
  const raw = (node.config?.options as unknown[]) || (node.config?.outlets as unknown[]);
  if (Array.isArray(raw) && raw.length) {
    return raw.map((o: any, i: number) => ({
      identifier: String(o?.identifier || o?.id || `opt${i + 1}`),
      title: String(o?.title || o?.label || o?.identifier || `Option ${i + 1}`),
      expression: o?.expression != null ? String(o.expression) : "",
    }));
  }
  return [
    { identifier: "yes", title: "Yes", expression: "" },
    { identifier: "no", title: "No", expression: "" },
  ];
}

function stringifyJson(v: unknown): string {
  if (v == null || v === "") return "";
  if (typeof v === "string") return v;
  try { return JSON.stringify(v, null, 2); } catch { return ""; }
}

function parseJson(text: string, fallback: unknown): unknown {
  const t = text.trim();
  if (!t) return fallback;
  try { return JSON.parse(t); } catch { return fallback; }
}
