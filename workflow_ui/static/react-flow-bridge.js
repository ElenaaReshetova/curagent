/**
 * Bridge: mounts React Flow designer into E2E / Stage hosts.
 * Maps flow types → workflow node types.
 * Workflows have no End node — leaf actions terminate the run.
 */
(function (global) {
  'use strict';

  const LEGACY_TO_UNIFIED = {
    START: 'trigger',
    // END intentionally omitted — dropped in fcToWorkflow
    SKILL_SLOT: 'ai_agent',
    LOCKED_STEP: 'ai_agent',
    ADAPTIVE_ZONE: 'ai_agent',
    CONTROL_GATE: 'input',
    HUMAN_CHECKPOINT: 'input',
    HUMAN_DECISION: 'input',
    CONDITIONAL_BRANCH: 'condition',
    CONDITION: 'condition',
    PARALLEL_BRANCH: 'condition',
    PARALLEL: 'condition',
    MERGE: 'webhook',
    ARTIFACT_BOUNDARY: 'webhook',
    PUBLICATION_STEP: 'webhook',
    SCRIPT: 'webhook',
    PLAYBOOK: 'subflow',
    SUBFLOW: 'subflow',
    WAIT_EVENT: 'internal_service',
    PLATFORM: 'integration_action',
    AI: 'ai',
    AI_AGENT: 'ai_agent',
    WEBHOOK: 'webhook',
    KAFKA: 'kafka',
    UPSERT_ENTITY: 'upsert_entity',
    INTEGRATION_ACTION: 'integration_action',
    INTERNAL_SERVICE: 'internal_service',
    INPUT: 'input',
    HUMAN_DECISION: 'input',
    HUMAN_CHECKPOINT: 'input',
    SELF_SERVE_TRIGGER: 'trigger',
    EVENT_TRIGGER: 'trigger',
    SCHEDULE_TRIGGER: 'trigger',
  };

  const CONFIG_TO_UNIFIED = {
    SELF_SERVE_TRIGGER: 'trigger',
    EVENT_TRIGGER: 'trigger',
    SCHEDULE_TRIGGER: 'trigger',
    AI_AGENT: 'ai_agent',
    AI: 'ai',
    WEBHOOK: 'webhook',
    CONDITION: 'condition',
    INPUT: 'input',
    UPSERT_ENTITY: 'upsert_entity',
    KAFKA: 'kafka',
    INTEGRATION_ACTION: 'integration_action',
    INTERNAL_SERVICE: 'internal_service',
    SUBFLOW: 'subflow',
  };

  const UNIFIED_TO_LEGACY_DEFAULT = {
    trigger: 'START',
    ai_agent: 'SKILL_SLOT',
    ai: 'SKILL_SLOT',
    agent: 'SKILL_SLOT',
    webhook: 'SCRIPT',
    tool: 'SCRIPT',
    transform: 'SCRIPT',
    condition: 'CONDITIONAL_BRANCH',
    branch: 'CONDITIONAL_BRANCH',
    parallel: 'CONDITIONAL_BRANCH',
    input: 'HUMAN_CHECKPOINT',
    approval: 'HUMAN_CHECKPOINT',
    delay: 'WAIT_EVENT',
    subflow: 'SUBFLOW',
    internal_service: 'SUBFLOW',
    upsert_entity: 'PLATFORM',
    kafka: 'PLATFORM',
    integration_action: 'PLATFORM',
  };

  function detectKind(mount) {
    if (!mount) return 'stage';
    const id = mount.id || '';
    if (id.indexOf('fl-') === 0 || (mount.className || '').indexOf('fl-') >= 0) return 'e2e';
    if (mount.closest && mount.closest('#fl-designer, .fl-designer')) return 'e2e';
    return 'e2e';
  }

  function defaultConfigFor(legacy, unified, data) {
    const cfg = Object.assign({}, data.config || {}, {
      flow_key: data.flow_key || data.playbook_key,
      interface_key: data.interface_key,
      knowledge_space_key: data.knowledge_space_key,
      timeout_seconds: data.timeout_seconds,
      failure_behavior: data.failure_behavior,
      control_source: data.control_source,
    });

    if (legacy === 'CONTROL_GATE') {
      cfg.type = 'INPUT';
      cfg.gate_mode = cfg.gate_mode || 'yes_no';
      cfg.description = cfg.description || cfg.question || 'Approve?';
      if (!cfg.userInputs) {
        cfg.userInputs = {
          properties: {},
          buttons: [
            { identifier: 'yes', label: 'Yes', variant: 'PRIMARY' },
            { identifier: 'no', label: 'No', variant: 'DANGER' },
          ],
        };
      }
      if (!cfg.outlets) {
        cfg.outlets = [
          { identifier: 'yes', title: 'Yes', evaluationMethod: 'button', numOfResponders: 1 },
          { identifier: 'no', title: 'No', evaluationMethod: 'button', numOfResponders: 1 },
        ];
      }
    } else if (unified === 'input' && !cfg.type) {
      cfg.type = 'INPUT';
      if (!cfg.userInputs) {
        cfg.userInputs = {
          properties: {},
          buttons: [
            { identifier: 'approve', label: 'Approve', variant: 'PRIMARY' },
            { identifier: 'decline', label: 'Decline', variant: 'DANGER' },
          ],
        };
      }
    } else if (unified === 'ai_agent' || unified === 'ai') {
      cfg.type = cfg.type || (unified === 'ai' ? 'AI' : 'AI_AGENT');
      if (data.interface_key && !cfg.agentIdentifier) cfg.agentIdentifier = data.interface_key;
      if (!cfg.userPrompt && cfg.task) cfg.userPrompt = cfg.task;
    } else if (unified === 'condition') {
      cfg.type = 'CONDITION';
      // CONDITION uses options[]
      if (!cfg.options) {
        var legacyOpts = cfg.outlets || cfg.outcomes || null;
        if (Array.isArray(legacyOpts)) {
          cfg.options = legacyOpts.map(function (o) {
            return {
              identifier: o.id || o.identifier,
              title: o.label || o.title || o.id || o.identifier,
              expression: o.expression || '',
            };
          });
        }
      }
      delete cfg.outlets;
      delete cfg.outcomes;
    } else if (unified === 'webhook') {
      cfg.type = cfg.type || 'WEBHOOK';
      if (!cfg.url && cfg.script_key) cfg.url = String(cfg.script_key);
    } else if (unified === 'trigger') {
      cfg.type = cfg.type || cfg.triggerType || 'SELF_SERVE_TRIGGER';
      cfg.triggerType = cfg.triggerType || cfg.type;
    } else if (unified === 'internal_service') {
      cfg.type = 'INTERNAL_SERVICE';
      cfg.service = cfg.service
        || data.flow_key
        || cfg.flow_key
        || cfg.graph_key
        || (legacy === 'WAIT_EVENT' ? 'wait_event' : 'service');
      cfg.parameter = cfg.parameter || {};
      if (data.flow_key) cfg.parameter.flow_key = data.flow_key;
    } else if (unified === 'integration_action') {
      cfg.type = cfg.type || 'INTEGRATION_ACTION';
    }
    return cfg;
  }

  function normalizeHandle(handle) {
    const h = String(handle || '').trim().toLowerCase();
    if (!h || h === 'out' || h === 'source' || h === 'in' || h === 'target') return handle || null;
    if (h === 'reject' || h === 'rejected') return 'decline';
    if (h === 'request_changes' || h === 'changes_requested') return 'changes';
    return handle;
  }

  function migrateLegacyNodeData(legacy, unified, data) {
    const cfg = defaultConfigFor(legacy, unified, data);
    // Skills: prefer interface_key / playbook skill binding as skill_keys
    if (unified === 'ai_agent' || unified === 'ai' || unified === 'agent') {
      const key = cfg.agentIdentifier || cfg.skill_key || data.interface_key || '';
      if (key) {
        cfg.agentIdentifier = cfg.agentIdentifier || key;
        cfg.skill_key = cfg.skill_key || key;
        if (!Array.isArray(cfg.skill_keys) || !cfg.skill_keys.length) {
          cfg.skill_keys = [String(key)];
        }
      }
      if (!cfg.userPrompt) cfg.userPrompt = cfg.task || '';
    }
    if (unified === 'subflow') {
      cfg.type = cfg.type || 'SUBFLOW';
      if (!cfg.graph_key) {
        cfg.graph_key = data.flow_key || cfg.flow_key || cfg.graph_key || data.playbook_key || '';
      }
    } else if (unified === 'internal_service') {
      cfg.type = 'INTERNAL_SERVICE';
      cfg.service = cfg.service
        || data.flow_key
        || cfg.flow_key
        || 'service';
    }
    if (unified === 'input' || unified === 'approval') {
      cfg.collectComment = cfg.collectComment !== false;
      if (!cfg.outlets && cfg.userInputs && Array.isArray(cfg.userInputs.buttons)) {
        cfg.outlets = cfg.userInputs.buttons.map(function (b) {
          return {
            identifier: b.identifier,
            title: b.label || b.identifier,
            evaluationMethod: 'button',
            numOfResponders: 1,
          };
        });
      }
    }
    return cfg;
  }

  function fcToWorkflow(fcGraph, kind) {
    const nodes = [];
    (fcGraph.nodes || []).forEach(function (n) {
      const legacy = String(n.type || '').toUpperCase();
      if (legacy === 'END') return; // no End node
      const data = n.data || {};
      const cfgType = String((data.config && data.config.type) || '').toUpperCase();
      let unified = CONFIG_TO_UNIFIED[cfgType]
        || LEGACY_TO_UNIFIED[legacy]
        || String(n.type || 'webhook').toLowerCase();
      if (unified === 'end') return; // no End node
      if (unified === 'delay' || unified === 'parallel' || unified === 'transform') {
        unified = 'webhook';
      }
      const pos = n.position || { x: 0, y: 0 };
      nodes.push({
        id: n.id,
        type: unified,
        label: data.name || data.label || n.id,
        position: {
          x: pos.x == null || Number.isNaN(+pos.x) ? 0 : +pos.x,
          y: pos.y == null || Number.isNaN(+pos.y) ? 0 : +pos.y,
        },
        config: migrateLegacyNodeData(legacy, unified, data),
        metadata: {
          legacy_type: legacy || UNIFIED_TO_LEGACY_DEFAULT[unified],
          immutable: !!data.immutable,
          subtitle: data.subtitle,
        },
      });
    });
    const keep = {};
    nodes.forEach(function (n) { keep[n.id] = true; });
    const edges = (fcGraph.edges || []).filter(function (e) {
      return keep[e.source] && keep[e.target];
    }).map(function (e) {
      const data = e.data || {};
      let handle = e.sourceHandle
        || data.condition
        || (data.config && data.config.source_handle)
        || null;
      handle = normalizeHandle(handle);
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: handle,
        targetHandle: e.targetHandle === 'target' ? 'in' : (e.targetHandle || 'in'),
        condition: data.condition || handle || null,
        label: data.label || e.label || handle || null,
      };
    });
    return {
      graphId: '',
      version: '0.1.0',
      name: kind === 'e2e' ? 'E2E' : 'Stage',
      kind: kind,
      entrypoints: nodes.filter(function (n) { return n.type === 'trigger'; }).map(function (n) { return n.id; }),
      nodes: nodes,
      edges: edges,
      policies: {},
    };
  }

  function dslNodeToFcType(n) {
    const cfgType = String((n.config || {}).type || '').toUpperCase();
    if (n.type === 'trigger' || cfgType.endsWith('TRIGGER')) return 'START';
    if (n.type === 'condition' || n.type === 'branch' || cfgType === 'CONDITION') return 'CONDITION';
    if (n.type === 'input' || n.type === 'approval' || cfgType === 'INPUT') return 'HUMAN_DECISION';
    if (n.type === 'subflow' || cfgType === 'SUBFLOW') return 'SUBFLOW';
    if (cfgType) return cfgType;
    return UNIFIED_TO_LEGACY_DEFAULT[n.type] || String(n.type || '').toUpperCase();
  }

  function workflowToFc(graph, kind) {
    return {
      nodes: (graph.nodes || []).filter(function (n) {
        return n.type !== 'end' && String((n.config || {}).type || '').toUpperCase() !== 'END';
      }).map(function (n) {
        const cfg = n.config || {};
        const cfgType = String(cfg.type || '').toUpperCase();
        const fromDsl = dslNodeToFcType(n);
        const stale = n.metadata && n.metadata.legacy_type;
        const isDslConfig = !!(CONFIG_TO_UNIFIED[cfgType] || cfgType.endsWith('TRIGGER'));
        const legacy = isDslConfig ? fromDsl : (stale || fromDsl);
        return {
          id: n.id,
          type: legacy === 'END' ? 'PLATFORM' : legacy,
          position: n.position || { x: 0, y: 0 },
          data: {
            name: n.label || n.id,
            label: n.label || n.id,
            flow_key: cfg.flow_key || cfg.graph_key || cfg.service || (cfg.parameter && cfg.parameter.flow_key) || cfg.playbook_key || '',
            interface_key: cfg.interface_key || cfg.agentIdentifier || null,
            control_source: cfg.control_source || null,
            knowledge_space_key: cfg.knowledge_space_key || '',
            timeout_seconds: cfg.timeout_seconds || 3600,
            failure_behavior: cfg.failure_behavior || 'ASK_HUMAN',
            immutable: !!(n.metadata && n.metadata.immutable),
            subtitle: (n.metadata && n.metadata.subtitle) || '',
            config: cfg,
          },
        };
      }),
      edges: (graph.edges || []).map(function (e) {
        const handle = e.sourceHandle || e.condition || null;
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: handle || undefined,
          targetHandle: e.targetHandle || 'in',
          label: e.label || handle || '',
          data: {
            condition: e.condition || handle || null,
            label: e.label || handle || '',
            priority: 100,
            config: handle ? { source_handle: handle, label: e.label || handle || '' } : {},
          },
        };
      }),
    };
  }

  function fcNeedsLayout(fcGraph) {
    const nodes = (fcGraph && fcGraph.nodes) || [];
    if (!nodes.length) return false;
    const pts = [];
    for (let i = 0; i < nodes.length; i++) {
      const p = nodes[i].position || {};
      if (p.x == null || p.y == null || Number.isNaN(+p.x) || Number.isNaN(+p.y)) continue;
      pts.push({ x: +p.x, y: +p.y });
    }
    if (!pts.length) return true;
    if (nodes.length === 1) return false;
    if (pts.length < 2) return true;
    const keys = {};
    for (let i = 0; i < pts.length; i++) {
      keys[Math.round(pts[i].x) + ',' + Math.round(pts[i].y)] = 1;
    }
    return Object.keys(keys).length <= 1;
  }

  function create(opts) {
    const mount = opts.mount;
    if (!mount) throw new Error('FlowCanvas bridge: mount required');
    const kind = opts.kind || detectKind(mount);
    let currentFc = { nodes: [], edges: [] };
    let graphName = opts.graphName;
    let handle = null;
    let graphId = opts.graphId || mount.getAttribute('data-graph-id') || '';
    let readOnly = !!opts.readOnly;

    function ensureMounted() {
      if (handle) return;
      if (!global.ReactFlowDesigner || typeof global.ReactFlowDesigner.mount !== 'function') {
        mount.innerHTML = '<div style="padding:16px;color:#b91c1c">ReactFlowDesigner не загружен. Пересоберите frontend.</div>';
        return;
      }
      const wf = fcToWorkflow(currentFc, kind);
      if (graphName) wf.name = graphName;
      handle = global.ReactFlowDesigner.mount(mount, {
        kind: kind,
        graphId: graphId || undefined,
        graph: wf,
        readOnly: readOnly,
        chrome: 'full',
        embedded: true,
        onSelect: function (nodeId) {
          const node = (currentFc.nodes || []).find(function (n) { return n.id === nodeId; }) || null;
          if (typeof opts.onSelect === 'function') opts.onSelect({ node: node, edge: null });
        },
        onChange: function (wfGraph) {
          currentFc = workflowToFc(wfGraph, kind);
          if (typeof opts.onChange === 'function') opts.onChange(currentFc);
        },
        onSave: opts.onSave,
        onPublish: opts.onPublish,
        onReady: function () {
          // Re-push latest fc graph after React handle is live (mount/setGraph race).
          if (handle && typeof handle.setGraph === 'function' && (currentFc.nodes || []).length) {
            const latest = fcToWorkflow(currentFc, kind);
            if (graphName) latest.name = graphName;
            handle.setGraph(latest);
          }
        },
      });
    }

    ensureMounted();

    return {
      setGraph: function (g) {
        const incoming = g || { nodes: [], edges: [] };
        const needs = fcNeedsLayout(incoming);
        currentFc = {
          nodes: (incoming.nodes || []).map(function (n) {
            const p = n.position || {};
            const x = p.x == null || Number.isNaN(+p.x) ? 0 : +p.x;
            const y = p.y == null || Number.isNaN(+p.y) ? 0 : +p.y;
            return Object.assign({}, n, {
              position: { x: x, y: y },
              data: Object.assign({}, n.data || {}, { _needsLayout: needs }),
            });
          }),
          edges: incoming.edges || [],
        };
        currentFc._needsLayout = needs;
        ensureMounted();
        if (handle && typeof handle.setGraph === 'function') {
          const wf = fcToWorkflow(currentFc, kind);
          if (graphName) wf.name = graphName;
          handle.setGraph(wf);
          if (needs && handle.ensureLayout) {
            Promise.resolve(handle.ensureLayout({ silent: true })).catch(function () { /* ignore */ });
          }
        }
      },
      getGraph: function () {
        if (handle && typeof handle.getGraph === 'function') {
          try {
            currentFc = workflowToFc(handle.getGraph(), kind);
          } catch (e) { /* keep */ }
        }
        return currentFc;
      },
      setGraphId: function (id) {
        graphId = id || '';
        if (handle && typeof handle.setGraphId === 'function') {
          handle.setGraphId(graphId);
        }
      },
      setGraphName: function (name) {
        graphName = name || '';
      },
      setReadOnly: function (ro) { readOnly = !!ro; },
      save: function () { return handle && handle.save ? handle.save() : Promise.resolve(); },
      validate: function () { return handle && handle.validate ? handle.validate() : Promise.resolve({ ok: true }); },
      publish: function () { return handle && handle.publish ? handle.publish() : Promise.resolve(); },
      autoLayout: function () { return handle && handle.autoLayout ? handle.autoLayout() : Promise.resolve(); },
      deleteSelected: function () { if (handle && handle.deleteSelected) handle.deleteSelected(); },
      destroy: function () {
        if (handle && handle.unmount) handle.unmount();
        handle = null;
        mount.innerHTML = '';
      },
      selectNode: function (id) {
        const node = (currentFc.nodes || []).find(function (n) { return n.id === id; }) || null;
        if (typeof opts.onSelect === 'function') opts.onSelect({ node: node, edge: null });
      },
      ensureLayout: function (optsIn) {
        const o = optsIn || {};
        const force = !!o.force;
        if (handle && typeof handle.ensureLayout === 'function') {
          return Promise.resolve(handle.ensureLayout({ silent: !!o.silent, force: force || !!currentFc._needsLayout })).then(function (mode) {
            currentFc._needsLayout = false;
            return mode;
          });
        }
        if (!force && !fcNeedsLayout(currentFc)) {
          return Promise.resolve('manual');
        }
        if (handle && handle.autoLayout) {
          return Promise.resolve(handle.autoLayout()).then(function () {
            currentFc._needsLayout = false;
            return 'auto';
          });
        }
        return Promise.resolve('manual');
      },
      fitView: function () {
        if (handle && handle.ensureLayout) {
          return Promise.resolve(handle.ensureLayout({ silent: true })).catch(function () { /* ignore */ });
        }
      },
      undo: function () {},
      redo: function () {},
      updateNodeData: function () {},
    };
  }

  function createRunMode(opts) {
    const mount = opts.mount;
    if (!mount) throw new Error('FlowCanvas.createRunMode: mount required');
    if (!global.ReactFlowDesigner || typeof global.ReactFlowDesigner.mountRunMode !== 'function') {
      mount.innerHTML = '<div style="padding:16px;color:#b91c1c">ReactFlowDesigner.mountRunMode отсутствует.</div>';
      return { destroy: function () { mount.innerHTML = ''; } };
    }
    const kind = opts.kind || detectKind(mount);
    const wf = opts.graph || fcToWorkflow(opts.fcGraph || { nodes: [], edges: [] }, kind);
    const handle = global.ReactFlowDesigner.mountRunMode(mount, {
      graph: wf,
      runId: opts.runId,
      runState: opts.runState || null,
      apiBase: opts.apiBase,
      readOnly: opts.readOnly === true,
      pollMs: opts.pollMs,
      onState: opts.onState,
    });
    return {
      setRunState: function (s) { if (handle && handle.setRunState) handle.setRunState(s); },
      refresh: function () { return handle && handle.refresh ? handle.refresh() : Promise.resolve(); },
      destroy: function () { if (handle && handle.unmount) handle.unmount(); mount.innerHTML = ''; },
    };
  }

  function bindPalette() { /* palette inside React */ }

  global.FlowCanvas = {
    create: create,
    createRunMode: createRunMode,
    bindPalette: bindPalette,
    engine: 'react-flow+elk',
  };
})(typeof window !== 'undefined' ? window : globalThis);
