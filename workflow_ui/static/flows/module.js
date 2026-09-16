/**
 * Flows — Catalog / Detail drawer / Designer shell / Routing preview.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const state = {
    items: [],
    metrics: null,
    detail: null,
    filters: { search: '', type: '', status: '' },
    modalMode: 'create', // create | edit
    editingId: null,
    designer: {
      nodes: [],
      edges: [],
      selectedKey: null,
      canvas: null,
      designerEdit: null,
      graphId: null,
    },
  };

  function productStatus(card) {
    return String((card && card.status) || 'draft').toLowerCase();
  }

  function asDetail(card) {
    const status = productStatus(card);
    const nodes = (card && card.canvas && card.canvas.nodes) || [];
    return {
      scenario: card,
      revision: card.revision,
      canvas: card.canvas,
      dsl: card.dsl,
      plan: card.plan,
      flow: {
        id: card.id,
        key: card.key,
        name: card.name,
        description: card.description || '',
        status: status.toUpperCase(),
        launched: status === 'launched',
        flow_type: card.kind === 'stage' ? 'STAGE' : 'E2E',
        current_published_version_id: status === 'draft' ? null : card.id,
        executions_30d: 0,
        success_rate: 0,
      },
      current_version: {
        id: card.id,
        status: status === 'draft' ? 'DRAFT' : 'PUBLISHED',
        revision: card.revision,
        semantic_version: '',
      },
      draft_version: status === 'draft'
        ? { id: card.id, status: 'DRAFT', revision: card.revision }
        : null,
      validation: {
        valid: !(card.validation) || card.validation.ok !== false,
        errors: ((card.validation && card.validation.issues) || []).map((i) => i.message || i.code || i),
      },
      stage_path: nodes.map((n) => n.label || n.title || n.id),
      runtime: {},
    };
  }

  function scenarioId() {
    return (state.detail && state.detail.flow && state.detail.flow.id)
      || (state.detail && state.detail.scenario && state.detail.scenario.id)
      || state.designer.graphId;
  }

  function root() {
    return document.getElementById('flows-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('fl-hidden', !visible);
  }

  function statusClass(status) {
    const s = (status || '').toLowerCase();
    if (s === 'published' || s === 'launched') return 'published-status';
    if (s === 'deprecated') return 'deprecated-status';
    return 'draft-status';
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    q.set('kind', 'e2e');
    if (state.filters.search) q.set('q', state.filters.search);
    if (state.filters.status) q.set('status', String(state.filters.status).toLowerCase());
    const data = await fetchJSON(`/scenarios?${q.toString()}`);
    const items = data.items || [];
    state.items = items.map((x) => ({
      id: x.id,
      name: x.name,
      key: x.key,
      description: '',
      status: String(x.status || 'draft').toUpperCase(),
      launched: x.status === 'launched',
      flow_type: x.kind || 'e2e',
      stages: [],
      stages_count: x.node_count || 0,
      executions_30d: 0,
      success_rate: 0,
    }));
    const launched = items.filter((x) => x.status === 'launched').length;
    const published = items.filter((x) => x.status === 'published' || x.status === 'launched').length;
    state.metrics = {
      published,
      active_executions: launched,
      success_rate_pct: null,
      validation_issues: 0,
    };
    renderMetrics();
    renderCards();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#fl-metric-published': m.published,
      '#fl-metric-exec': m.active_executions,
      '#fl-metric-success': m.success_rate_pct != null ? `${m.success_rate_pct}%` : '—',
      '#fl-metric-issues': m.validation_issues,
    };
    Object.entries(map).forEach(([sel, val]) => {
      const el = $(sel);
      if (el) el.textContent = val == null ? '—' : String(val);
    });
  }

  function catalogMenu(id) {
    return CardMenu().markup(id, CardMenu().defaultActions([
      { id: 'designer', label: 'Открыть в дизайнере' },
    ]));
  }

  function bindCardMenus(scope) {
    CardMenu().bind(scope || root(), (id, action) => {
      handleCardAction(action, id).catch((e) => toast(e.message));
    });
  }

  async function handleCardAction(action, id) {
    if (!id) {
      toast('Сценарий не выбран');
      return;
    }
    if (action === 'edit') {
      await openEditModal(id);
      return;
    }
    if (action === 'designer') {
      await openDetail(id);
      openDesigner();
      return;
    }
    if (action === 'delete') {
      await deleteFlow(id);
    }
  }

  function renderCards() {
    const grid = $('#fl-cards');
    if (!grid) return;
    if (!state.items.length) {
      grid.innerHTML = '<p style="color:var(--fl-muted)">Е2Е Сценарии не найдены</p>';
      return;
    }
    grid.innerHTML = state.items.map((x) => {
      const n = x.stages_count || 0;
      const mini = Array.from({ length: Math.min(4, Math.max(1, n)) }, (_, i) =>
        `<span class="${i < n ? 'active' : ''}"></span>`
      ).join('');
      const success = x.executions_30d ? `${x.success_rate}%` : '—';
      const launchBadge = x.launched
        ? '<span class="fl-status published" title="Агент выполняет">LAUNCHED</span>'
        : (x.status === 'PUBLISHED'
          ? '<span class="fl-status draft" title="Опубликован, но не запущен — система игнорирует">IDLE</span>'
          : '');
      return `<article class="fl-card" data-id="${esc(x.id)}" tabindex="0" role="button">
        <div class="fl-card-head">
          <div class="fl-card-head-main">
            <div class="fl-icon">⌘</div>
            <div class="fl-card-badges">
              <span class="fl-status ${statusClass(x.status)}">${esc(x.status)}</span>${launchBadge}
            </div>
          </div>
          ${catalogMenu(x.id)}
        </div>
        <h3>${esc(x.name)}</h3>
        <p>${esc(x.description || '')}</p>
        <div class="fl-stage-mini">${mini}</div>
        <div class="fl-metrics"><span>${esc(x.flow_type)}</span><span>${esc(n)} шагов</span><span>${esc(success)}</span></div>
      </article>`;
    }).join('');
    grid.querySelectorAll('.fl-card').forEach((card) => {
      card.onclick = (e) => {
        if (e.target.closest('.card-menu')) return;
        openDetail(card.dataset.id);
      };
      card.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openDetail(card.dataset.id);
        }
      };
    });
    bindCardMenus(grid);
  }

  async function openEditModal(id) {
    const detail = (state.detail && state.detail.flow && state.detail.flow.id === id)
      ? state.detail
      : asDetail(await fetchJSON(`/scenarios/${id}`));
    const flow = detail.flow || {};
    state.modalMode = 'edit';
    state.editingId = flow.id || id;
    state.detail = detail;
    const title = $('#fl-modal-title');
    const saveBtn = $('#fl-save-flow');
    const name = $('#fl-new-name');
    const key = $('#fl-new-key');
    const type = $('#fl-new-type');
    const desc = $('#fl-new-desc');
    if (title) title.textContent = 'Редактировать Е2Е Сценарий';
    if (saveBtn) saveBtn.textContent = 'Сохранить';
    if (name) name.value = flow.name || '';
    if (key) {
      key.value = flow.key || '';
      key.disabled = true;
      key.title = 'Ключ нельзя изменить';
    }
    if (type) type.value = flow.flow_type || 'FEATURE_DELIVERY';
    if (desc) desc.value = flow.description || '';
    show($('#fl-modal'), true);
  }

  function openCreateModal() {
    state.modalMode = 'create';
    state.editingId = null;
    const title = $('#fl-modal-title');
    const saveBtn = $('#fl-save-flow');
    const name = $('#fl-new-name');
    const key = $('#fl-new-key');
    const type = $('#fl-new-type');
    const desc = $('#fl-new-desc');
    if (title) title.textContent = 'Создать Е2Е Сценарий';
    if (saveBtn) saveBtn.textContent = 'Создать черновик';
    if (name) name.value = 'Новый сценарий поставки';
    if (key) {
      key.value = 'new-delivery-flow';
      key.disabled = false;
      key.title = '';
    }
    if (type) type.value = 'FEATURE_DELIVERY';
    if (desc) desc.value = '';
    show($('#fl-modal'), true);
  }

  function openModal() { openCreateModal(); }
  function closeModal() {
    show($('#fl-modal'), false);
    state.modalMode = 'create';
    state.editingId = null;
    const key = $('#fl-new-key');
    if (key) {
      key.disabled = false;
      key.title = '';
    }
  }
  async function openDetail(id) {
    state.detail = asDetail(await fetchJSON(`/scenarios/${id}?view=canvas`));
    state.designer.nodes = [];
    state.designer.edges = [];
    state.designer.selectedKey = null;
    show($('#fl-drawer'), true);
    renderDetail();
    showTab('overview');
  }

  function closeDrawer() {
    show($('#fl-drawer'), false);
    state.detail = null;
  }

  function renderDetail() {
    const detail = state.detail;
    if (!detail) return;
    const flow = detail.flow || {};
    const ver = detail.current_version || {};
    const menuHost = $('#fl-drawer-menu');
    if (menuHost && flow.id) {
      menuHost.innerHTML = catalogMenu(flow.id);
      bindCardMenus(menuHost);
    }
    const name = $('#fl-drawer-name');
    if (name) name.textContent = flow.name || '';
    const desc = $('#fl-description');
    if (desc) desc.textContent = flow.description || '';
    const meta = $('#fl-meta');
    if (meta) {
      const catalogStatus = flow.current_published_version_id && flow.status === 'active'
        ? 'PUBLISHED' : (flow.status || '').toUpperCase();
      meta.innerHTML = `
        <dt>Ключ</dt><dd>${esc(flow.key)}</dd>
        <dt>Тип</dt><dd>${esc(flow.flow_type)}</dd>
        <dt>Статус</dt><dd>${esc(catalogStatus)}</dd>
        <dt>Версия</dt><dd>${esc(ver.semantic_version ? `v${ver.semantic_version}` : '—')}</dd>
        <dt>Запуски</dt><dd>${esc(flow.executions_30d || 0)}</dd>
        <dt>Успех</dt><dd>${esc(flow.executions_30d ? `${flow.success_rate}%` : '—')}</dd>`;
    }
    const runtime = detail.runtime || {};
    const rt = $('#fl-runtime');
    if (rt) {
      rt.innerHTML = `
        <div class="fl-health-row"><span>Профиль исполнения</span><b>${esc(runtime.runtime_profile || '—')}</b></div>
        <div class="fl-health-row"><span>Knowledge Space</span><b>${esc(runtime.knowledge_space || '—')}</b></div>
        <div class="fl-health-row"><span>Средняя длительность</span><b>${esc(runtime.avg_duration || '—')}</b></div>`;
    }
    const path = $('#fl-stage-path');
    if (path) {
      const stages = detail.stage_path || [];
      const link = (name, key, view) => {
        if (key && window.PlatformUtil && window.PlatformUtil.entityLink) {
          return window.PlatformUtil.entityLink(view || 'flows', name, { id: key, key });
        }
        return `<span>${esc(name)}</span>`;
      };
      path.innerHTML = stages.length
        ? stages.map((s, i) => {
          const name = typeof s === 'string' ? s : (s.name || s.playbook_key || s.flow_key || '—');
          const pb = typeof s === 'string' ? null : (s.playbook_key || null);
          const fk = typeof s === 'string' ? null : (s.flow_key || null);
          const view = 'flows';
          return `${i ? '<b>→</b>' : ''}${link(name, fk || pb, view)}`;
        }).join('')
        : '<span style="color:var(--fl-muted)">Нет этапов</span>';
      if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
        window.PlatformUtil.bindEntityLinks(path);
      }
    }
    const routing = $('#fl-routing-list');
    if (routing) {
      const rules = (ver.routing_rules || []);
      routing.innerHTML = rules.length
        ? rules.map((r) => `
          <div class="fl-routing-card">
            <b>${esc(r.name)}</b>
            <span>${esc(r.expression)}</span>
            <em>Приоритет ${esc(r.priority)}</em>
          </div>`).join('')
        : '<p style="color:var(--fl-muted)">Нет правил маршрутизации</p>';
    }
    const stagesTab = $('#fl-stages-list');
    if (stagesTab) {
      const stages = (ver.stages || []).filter((s) =>
        s.type === 'PLAYBOOK' || s.type === 'SUBFLOW' || s.type === 'PLATFORM' || s.type === 'WAIT_EVENT'
      );
      stagesTab.innerHTML = stages.length
        ? stages.map((s) => {
          const ref = s.type === 'SUBFLOW'
            ? (s.flow_key || '—')
            : (s.type === 'PLAYBOOK' ? (s.playbook_key || '—') : (s.type === 'WAIT_EVENT' ? ((s.config && s.config.source) || 'ingress') : ((s.config && s.config.step) || 'platform')));
          const view = 'flows';
          const canLink = Boolean(s.flow_key || s.playbook_key);
          const linkKey = s.flow_key || s.playbook_key;
          return `
          <div class="fl-health-row">
            <span>${esc(s.name)} <em style="color:var(--fl-muted)">${esc(s.type)}</em></span>
            <b>${canLink && window.PlatformUtil && window.PlatformUtil.entityLink
              ? window.PlatformUtil.entityLink(view, ref, { id: linkKey, key: linkKey })
              : esc(ref)}</b>
          </div>`;
        }).join('')
        : '<p style="color:var(--fl-muted)">Нет этапов / сценариев</p>';
      if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
        window.PlatformUtil.bindEntityLinks(stagesTab);
      }
    }
    const validation = $('#fl-validation-box');
    if (validation) {
      const report = detail.validation || {};
      const errors = report.errors || [];
      const warnings = report.warnings || [];
      validation.innerHTML = `
        <div class="fl-problem ${report.valid ? '' : 'warn-box'}">
          Статус: ${esc(report.status || 'unknown')} · ${report.valid ? 'Валиден' : 'Невалиден'}
        </div>
        ${errors.map((e) => `<div class="fl-problem warn-box">${esc(e.message || e)}</div>`).join('')}
        ${warnings.map((w) => `<div class="fl-problem warn-box">${esc(w.message || w)}</div>`).join('')}
        ${!errors.length && !warnings.length ? '<div class="fl-problem">Все контракты совместимы</div>' : ''}`;
    }
  }

  function showTab(tab) {
    root()?.querySelectorAll('.fl-tabs button').forEach((b) => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    ['overview', 'stages', 'validation'].forEach((t) => {
      show($(`#fl-tab-${t}`), t === tab);
    });
  }

  function nodeSubtitle(type) {
    if (type === 'PLAYBOOK' || type === 'SUBFLOW') return 'Е2Е сценарий';
    if (type === 'HUMAN_DECISION') return 'Human decision';
    if (type === 'CONDITION') return 'Condition';
    if (type === 'PARALLEL') return 'Parallel split';
    if (type === 'WAIT_EVENT') return 'Ingress';
    if (type === 'PLATFORM') return 'Platform pipeline';
    if (type === 'START') return 'Work request';
    if (type === 'END') return 'Completed';
    return type || 'Stage';
  }

  function nodeAccentClass(type) {
    if (type === 'PLAYBOOK') return 'playbook';
    if (type === 'SUBFLOW') return 'playbook';
    if (type === 'HUMAN_DECISION') return 'human';
    if (type === 'CONDITION' || type === 'PLATFORM') return 'decision';
    if (type === 'WAIT_EVENT') return 'human';
    return 'default';
  }

  function renderFlowNode(node, ctx) {
    const type = node.type;
    const data = node.data || {};
    const selected = ctx.selected ? ' selected' : '';
    const terminal = type === 'START' ? ' fc-start' : (type === 'END' ? ' fc-end' : '');
    const accent = type === 'START' || type === 'END'
      ? ''
      : ` fc-accent-${nodeAccentClass(type)}`;
    let sub = data.subtitle || nodeSubtitle(type);
    if (type === 'PLAYBOOK' && data.playbook_key) sub = data.playbook_key;
    if (type === 'SUBFLOW' && data.flow_key) sub = data.flow_key;
    if (type === 'WAIT_EVENT' && data.config && data.config.source) {
      sub = `Ingress · ${data.config.source}`;
    }
    if (type === 'PLATFORM' && data.config && data.config.step) {
      sub = `Platform · ${data.config.step}`;
    }
    return {
      className: `fc-node${accent}${terminal}${selected}`,
      body: `<div class="fc-node-label">${esc(data.name || node.id)}</div>`
        + `<div class="fc-node-sub">${esc(sub)}</div>`,
    };
  }

  function designerNodeToFc(n) {
    return {
      id: n.key,
      type: n.type,
      position: { x: n.x, y: n.y },
      data: {
        name: n.name,
        playbook_key: n.playbook_key || '',
        flow_key: n.flow_key || '',
        knowledge_space_key: n.knowledge_space_key || '',
        timeout_seconds: n.timeout_seconds || 3600,
        failure_behavior: n.failure_behavior || 'ASK_HUMAN',
        config: n.config || {},
        subtitle: nodeSubtitle(n.type),
      },
    };
  }

  function fcNodeToDesigner(n) {
    const d = n.data || {};
    return {
      key: n.id,
      name: d.name || '',
      type: n.type,
      playbook_key: d.playbook_key || '',
      flow_key: d.flow_key || '',
      knowledge_space_key: d.knowledge_space_key || '',
      timeout_seconds: d.timeout_seconds || 3600,
      failure_behavior: d.failure_behavior || 'ASK_HUMAN',
      config: d.config || {},
      x: n.position.x,
      y: n.position.y,
    };
  }

  function edgeConditionFromFc(e) {
    if (e.data && e.data.condition != null && String(e.data.condition).trim() !== '') {
      return e.data.condition;
    }
    if (e.condition != null && String(e.condition).trim() !== '') return e.condition;
    const h = String(e.sourceHandle || '').trim();
    const hl = h.toLowerCase();
    if (!hl || hl === 'out' || hl === 'in') return null;
    if (hl === 'yes' || hl === 'pass' || hl === 'true') return 'yes';
    if (hl === 'no' || hl === 'fail' || hl === 'false') return 'no';
    if (hl === 'approve') return 'approve';
    if (hl === 'changes' || hl === 'clarify' || hl === 'request_changes') return 'request_changes';
    if (hl === 'reject' || hl === 'decline') return 'decline';
    // Classifier / custom ports: persist handle id as condition.
    return h;
  }

  function sourceHandleFromCondition(condition) {
    const c = String(condition || '').trim();
    const cl = c.toLowerCase();
    if (!cl) return null;
    if (cl === 'yes' || cl === 'pass' || cl === 'true') return 'yes';
    if (cl === 'no' || cl === 'fail' || cl === 'false') return 'no';
    if (cl === 'approve' || cl === 'approved') return 'approve';
    if (cl === 'request_changes' || cl === 'changes' || cl === 'clarify' || cl === 'refine') {
      return 'changes';
    }
    if (cl === 'reject' || cl === 'rejected' || cl === 'decline') return 'decline';
    // high / medium / low / billing / …
    return c;
  }

  function isFailCondition(condition, sourceHandle) {
    const h = String(sourceHandle || '').toLowerCase();
    const c = String(condition || '').toLowerCase();
    const fail = new Set(['no', 'fail', 'false', 'block', 'error', 'decline', 'reject', 'rejected']);
    return fail.has(h) || fail.has(c);
  }

  function designerEdgeFromFc(e) {
    const condition = edgeConditionFromFc(e);
    const sourceHandle = e.sourceHandle || sourceHandleFromCondition(condition) || null;
    return {
      key: e.id || e.key || `e-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      condition,
      sourceHandle,
    };
  }

  function buildFcEdges(nodes, edges) {
    if (edges && edges.length) {
      return edges.map((e) => {
        const condition = e.condition != null ? e.condition : null;
        const sourceHandle = e.sourceHandle
          || sourceHandleFromCondition(condition)
          || null;
        const label = (e.data && e.data.label)
          || (condition && /^(approve|approved)$/i.test(String(condition)) ? 'Approve'
            : condition && /^(request_changes|changes|clarify|refine)$/i.test(String(condition)) ? 'Request changes'
              : condition && /^(reject|rejected)$/i.test(String(condition)) ? 'Reject'
                : condition && /^(yes|pass|true)$/i.test(String(condition)) ? 'Yes'
                  : condition && /^(no|fail|false)$/i.test(String(condition)) ? 'No' : '');
        return {
          id: e.key || e.id || `e-${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          sourceHandle,
          targetHandle: 'in',
          data: { condition, label },
        };
      });
    }
    return nodes.slice(0, -1).map((n, i) => ({
      id: `e-${n.key}-${nodes[i + 1].key}`,
      source: n.key,
      target: nodes[i + 1].key,
      data: {},
    }));
  }

  function syncDesignerFromGraph(graph) {
    state.designer.nodes = (graph.nodes || []).map(fcNodeToDesigner);
    state.designer.edges = (graph.edges || []).map(designerEdgeFromFc);
    const edit = state.designer.designerEdit;
    if (edit && !edit.isDslDirty()) edit.syncFromGraph();
  }

  function domainGraphFromDesigner() {
    return {
      schema_version: '1',
      nodes: (state.designer.nodes || []).map((n) => ({
        key: n.key,
        type: n.type,
        name: n.name,
        playbook_key: n.playbook_key || '',
        flow_key: n.flow_key || '',
        knowledge_space_key: n.knowledge_space_key || '',
        timeout_seconds: n.timeout_seconds || 3600,
        failure_behavior: n.failure_behavior || 'ASK_HUMAN',
        config: n.config || {},
        position: { x: n.x || 0, y: n.y || 0 },
      })),
      edges: (state.designer.edges || []).map((e) => ({
        key: e.key || e.id || `e-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        condition: e.condition != null ? e.condition : (e.sourceHandle || null),
      })),
    };
  }

  function applyDomainGraph(parsed) {
    const nodes = (parsed.nodes || []).map((n, i) => {
      const pos = n.position || {};
      return {
        key: n.key || n.id || `node-${i}`,
        name: n.name || n.key || `Node ${i + 1}`,
        type: n.type === 'PLAYBOOK' ? 'SUBFLOW' : (n.type || 'SUBFLOW'),
        playbook_key: n.playbook_key || '',
        flow_key: n.flow_key || '',
        knowledge_space_key: n.knowledge_space_key || '',
        timeout_seconds: n.timeout_seconds || 3600,
        failure_behavior: n.failure_behavior || 'ASK_HUMAN',
        config: n.config || {},
        x: pos.x != null ? pos.x : (n.x || 40 + i * 280),
        y: pos.y != null ? pos.y : (n.y || 140),
      };
    });
    const edges = (parsed.edges || []).map((e, i) => ({
      key: e.key || e.id || `e-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      condition: e.condition != null ? e.condition : null,
      sourceHandle: e.sourceHandle || sourceHandleFromCondition(e.condition) || null,
    }));
    state.designer.nodes = nodes;
    state.designer.edges = edges;
    const canvas = state.designer.canvas;
    if (canvas) {
      canvas.setGraph({
        nodes: nodes.map(designerNodeToFc),
        edges: buildFcEdges(nodes, edges),
      });
    }
    if (state.designer.selectedKey) {
      const still = nodes.find((n) => n.key === state.designer.selectedKey);
      if (still) fillInspector(still);
      else {
        state.designer.selectedKey = null;
        fillInspector(null);
      }
    }
  }

  function ensureDesignerEdit() {
    if (state.designer.designerEdit) return state.designer.designerEdit;
    if (!window.DesignerEdit || typeof window.DesignerEdit.create !== 'function') {
      toast('DesignerEdit не загружен');
      return null;
    }
    const designerRoot = $('#fl-designer') || root();
    state.designer.designerEdit = window.DesignerEdit.create({
      root: designerRoot,
      getGraph: domainGraphFromDesigner,
      setGraph: applyDomainGraph,
      getCanvas: () => state.designer.canvas,
      isReadOnly: () => false,
      onApplied: () => { /* graph already applied */ },
      readOnlyMessage: 'Е2Е Сценарий только для чтения',
      appliedMessage: 'DSL применён к canvas',
    });
    return state.designer.designerEdit;
  }

  function destroyDesignerCanvas() {
    if (state.designer.canvas) {
      state.designer.canvas.destroy();
      state.designer.canvas = null;
    }
  }

  async function resolveLinkedGraphId() {
    const id = scenarioId();
    if (!id) return '';
    state.designer.graphId = id;
    return id;
  }

  function applyScenarioCanvas(canvas) {
    if (!canvas || !Array.isArray(canvas.nodes) || !canvas.nodes.length) return false;
    applyDomainGraph({
      nodes: canvas.nodes.map((n) => ({
        key: n.id || n.key,
        id: n.id || n.key,
        name: n.label || n.title || n.id,
        type: (n.config && n.config.type) || n.type,
        config: n.config || {},
        position: n.position || {},
        x: n.position && n.position.x,
        y: n.position && n.position.y,
      })),
      edges: (canvas.edges || []).map((e) => ({
        key: e.id || e.key || `e-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        condition: e.sourceHandle || e.condition || null,
        sourceHandle: e.sourceHandle || e.condition || null,
      })),
    });
    return true;
  }

  function initDesignerCanvas() {
    const mount = $('#fl-canvas');
    if (!mount || !window.FlowCanvas) return;

    const graph = {
      nodes: state.designer.nodes.map(designerNodeToFc),
      edges: buildFcEdges(state.designer.nodes, state.designer.edges),
    };
    const flow = (state.detail && state.detail.flow) || {};

    if (state.designer.canvas) {
      if (state.designer.canvas.setGraphName) state.designer.canvas.setGraphName(flow.name || 'E2E Scenario');
      state.designer.canvas.setGraph(graph);
      if (state.designer.graphId && state.designer.canvas.setGraphId) {
        state.designer.canvas.setGraphId(state.designer.graphId);
      }
      return;
    }

    state.designer.canvas = window.FlowCanvas.create({
      mount,
      kind: 'e2e',
      graphId: state.designer.graphId || undefined,
      graphName: flow.name || 'E2E Scenario',
      readOnly: false,
      onSelect: ({ node }) => {
        state.designer.selectedKey = node ? node.id : null;
      },
      onChange: (g) => {
        syncDesignerFromGraph(g);
      },
    });

    state.designer.canvas.setGraph(graph);
    if (state.designer.graphId && state.designer.canvas.setGraphId) {
      state.designer.canvas.setGraphId(state.designer.graphId);
    }
    if (state.designer.canvas.ensureLayout) {
      state.designer.canvas.ensureLayout({ silent: true }).catch(() => {});
    }
  }

  async function openDesigner() {
    const title = $('#fl-designer-title');
    const flow = (state.detail && state.detail.flow) || {};
    const status = productStatus(state.detail && state.detail.scenario);
    if (title) {
      title.textContent = flow.name
        ? `${flow.name} · ${status}`
        : 'Дизайнер Е2Е Сценария';
    }
    await resolveLinkedGraphId();
    const localCanvas = (state.detail && (state.detail.canvas || state.detail.dsl)) || null;
    if (!applyScenarioCanvas(localCanvas)) {
      await hydrateDesignerFromLinkedGraph();
    }
    show($('#fl-designer'), true);
    const edit = ensureDesignerEdit();
    if (edit) {
      edit.bind();
      edit.reset('canvas');
    }
    initDesignerCanvas();
    if (edit) edit.syncFromGraph({ force: true });
    syncDesignerActions();
  }

  async function hydrateDesignerFromLinkedGraph() {
    const id = state.designer.graphId;
    if (!id) return;
    try {
      const detail = await fetchJSON(`/scenarios/${id}?view=canvas`);
      state.detail = asDetail(detail);
      applyScenarioCanvas(detail.canvas || detail.dsl);
    } catch (_e) {
      /* canvas stays empty */
    }
  }

  function closeDesigner() {
    show($('#fl-designer'), false);
    const edit = state.designer.designerEdit;
    if (edit) edit.reset('canvas');
  }

  function loadDesignerGraph(ver) {
    const prev = state.designer.nodes;
    const byKey = Object.fromEntries(prev.map((n) => [n.key, n]));
    const nodes = [];
    let stages = (ver && ver.stages) ? [...ver.stages] : [];
    if (!stages.length) {
      stages = [
        { key: 'trigger', name: 'Trigger', type: 'START' },
      ];
    }
    stages.forEach((s, i) => {
      const saved = byKey[s.key];
      const isTerminal = s.type === 'START' || s.type === 'END';
      const cfgPos = (s.config && s.config.position) || {};
      const x = saved
        ? saved.x
        : (cfgPos.x != null ? cfgPos.x : (s.x != null ? s.x : 40 + i * 280));
      const y = saved
        ? saved.y
        : (cfgPos.y != null ? cfgPos.y : (s.y != null ? s.y : (isTerminal ? 160 : 140)));
      nodes.push({
        key: s.key,
        name: s.name,
        type: s.type,
        playbook_key: s.playbook_key || '',
        flow_key: s.flow_key || '',
        knowledge_space_key: s.knowledge_space_key || '',
        timeout_seconds: s.timeout_seconds || 3600,
        failure_behavior: s.failure_behavior || 'ASK_HUMAN',
        config: s.config || {},
        x,
        y,
      });
    });
    state.designer.nodes = nodes;
    const rawEdges = (ver && ver.edges) || [];
    state.designer.edges = rawEdges.map((e, i) => ({
      key: e.key || e.id || `e-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      condition: e.condition != null ? e.condition : null,
      sourceHandle: e.sourceHandle || sourceHandleFromCondition(e.condition) || null,
    }));
    if (!state.designer.selectedKey && nodes.length) {
      state.designer.selectedKey = nodes.find((n) =>
        n.type === 'PLAYBOOK' || n.type === 'SUBFLOW' || n.type === 'WAIT_EVENT'
      )?.key || nodes[0].key;
    }
  }

  function getDesignerNode(key) {
    return state.designer.nodes.find((n) => n.key === key) || null;
  }

  function fillInspector(node) {
    const empty = $('#fl-insp-empty');
    const fields = $('#fl-insp-fields');
    if (!node) {
      show(empty, true);
      show(fields, false);
      return;
    }
    show(empty, false);
    show(fields, true);
    const name = $('#fl-insp-name');
    const type = $('#fl-insp-type');
    const playbook = $('#fl-insp-playbook');
    const flowSel = $('#fl-insp-flow');
    const kspace = $('#fl-insp-kspace');
    const timeout = $('#fl-insp-timeout');
    const failure = $('#fl-insp-failure');
    const cfg = node.config || {};

    if (name) name.value = node.name || '';
    if (type) type.value = nodeSubtitle(node.type);
    if (kspace) kspace.value = node.knowledge_space_key || '';
    if (timeout) timeout.value = String(node.timeout_seconds || 3600);
    if (failure) failure.value = node.failure_behavior || 'ASK_HUMAN';

    show($('#fl-insp-playbook-block'), node.type === 'PLAYBOOK');
    show($('#fl-insp-subflow-block'), node.type === 'SUBFLOW');
    show($('#fl-insp-ingress-block'), node.type === 'WAIT_EVENT');
    show($('#fl-insp-platform-block'), node.type === 'PLATFORM');

    if (playbook && node.type === 'PLAYBOOK') {
      ensureSelectOption(playbook, node.playbook_key);
      playbook.value = node.playbook_key || '';
    }
    if (flowSel && node.type === 'SUBFLOW') {
      ensureSelectOption(flowSel, node.flow_key);
      flowSel.value = node.flow_key || '';
    }
    if (node.type === 'WAIT_EVENT') {
      const src = $('#fl-insp-ingress-source');
      const mode = $('#fl-insp-ingress-mode');
      const target = $('#fl-insp-ingress-target');
      if (src) src.value = cfg.source || 'slack';
      if (mode) mode.value = cfg.mode || 'mention';
      if (target) target.value = cfg.channel_id || cfg.project || cfg.target || '';
    }
    if (node.type === 'PLATFORM') {
      const step = $('#fl-insp-platform-step');
      if (step) step.value = cfg.step || 'classify';
    }
  }

  function ensureSelectOption(selectEl, value) {
    if (!selectEl || !value) return;
    const exists = Array.from(selectEl.options).some((o) => o.value === value);
    if (!exists) {
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = value;
      selectEl.appendChild(opt);
    }
  }

  function bindInspectorInputs() {
    const sync = () => {
      const key = state.designer.selectedKey;
      if (!key) return;
      const node = getDesignerNode(key);
      const name = $('#fl-insp-name');
      const playbook = $('#fl-insp-playbook');
      const flowSel = $('#fl-insp-flow');
      const kspace = $('#fl-insp-kspace');
      const timeout = $('#fl-insp-timeout');
      const failure = $('#fl-insp-failure');
      const cfg = { ...((node && node.config) || {}) };

      if (node && node.type === 'WAIT_EVENT') {
        const src = $('#fl-insp-ingress-source');
        const mode = $('#fl-insp-ingress-mode');
        const target = $('#fl-insp-ingress-target');
        cfg.role = 'ingress';
        cfg.source = src ? src.value : 'slack';
        cfg.mode = mode ? mode.value : 'mention';
        const t = target ? target.value.trim() : '';
        if (cfg.source === 'jira') {
          cfg.project = t;
          delete cfg.channel_id;
        } else {
          cfg.channel_id = t;
          delete cfg.project;
        }
      }
      if (node && node.type === 'PLATFORM') {
        const step = $('#fl-insp-platform-step');
        cfg.step = step ? step.value : 'classify';
        cfg.locked = true;
        if (cfg.step === 'classify') cfg.skill_key = 'classify';
      }

      const patch = {
        name: name ? name.value : '',
        playbook_key: playbook ? playbook.value : '',
        flow_key: flowSel ? flowSel.value : '',
        knowledge_space_key: kspace ? kspace.value : '',
        timeout_seconds: Number(timeout && timeout.value) || 3600,
        failure_behavior: failure ? failure.value : 'ASK_HUMAN',
        config: cfg,
      };
      const canvas = state.designer.canvas;
      if (canvas) {
        canvas.updateNodeData(key, patch);
        return;
      }
      if (!node) return;
      Object.assign(node, patch);
    };
    [
      '#fl-insp-name', '#fl-insp-playbook', '#fl-insp-flow', '#fl-insp-kspace',
      '#fl-insp-timeout', '#fl-insp-failure',
      '#fl-insp-ingress-source', '#fl-insp-ingress-mode', '#fl-insp-ingress-target',
      '#fl-insp-platform-step',
    ].forEach((sel) => {
      const el = $(sel);
      if (!el || el.dataset.bound) return;
      el.dataset.bound = '1';
      el.addEventListener('input', sync);
      el.addEventListener('change', sync);
    });
  }

  function addDesignerNode(kind) {
    const typeMap = {
      playbook: 'SUBFLOW',
      subflow: 'SUBFLOW',
      condition: 'CONDITION',
      parallel: 'PARALLEL',
      wait: 'WAIT_EVENT',
      platform: 'PLATFORM',
      human: 'HUMAN_DECISION',
      end: 'END',
    };
    const type = typeMap[kind] || 'SUBFLOW';
    const key = `new-${kind}-${Date.now()}`;
    const nameMap = {
      playbook: 'Е2Е сценарий',
      subflow: 'Е2Е сценарий',
      condition: 'Condition',
      parallel: 'Parallel split',
      wait: 'Ingress',
      platform: 'Platform step',
      human: 'Human decision',
      end: 'End',
    };
    const defaultConfig = {};
    if (type === 'WAIT_EVENT') {
      Object.assign(defaultConfig, { role: 'ingress', source: 'slack', mode: 'mention', channel_id: '' });
    }
    if (type === 'PLATFORM') {
      Object.assign(defaultConfig, { step: 'classify', skill_key: 'classify', locked: true });
    }
    const anchor = getDesignerNode(state.designer.selectedKey)
      || state.designer.nodes[state.designer.nodes.length - 1];
    const x = anchor ? anchor.x + 280 : 240;
    const y = anchor ? anchor.y : 140;
    const canvas = state.designer.canvas;
    const data = {
      name: nameMap[kind] || 'New stage',
      playbook_key: type === 'PLAYBOOK' ? '' : '',
      flow_key: type === 'SUBFLOW' ? '' : '',
      knowledge_space_key: '',
      timeout_seconds: 3600,
      failure_behavior: 'ASK_HUMAN',
      config: defaultConfig,
      subtitle: nodeSubtitle(type),
    };

    if (canvas) {
      canvas.addNode({
        id: key,
        type,
        position: { x, y },
        data,
      });
      if (anchor && type !== 'END') {
        canvas.addEdge(anchor.key, key);
      }
    } else {
      state.designer.nodes.push({
        key,
        name: data.name,
        type,
        playbook_key: data.playbook_key,
        flow_key: data.flow_key,
        knowledge_space_key: '',
        timeout_seconds: 3600,
        failure_behavior: 'ASK_HUMAN',
        config: defaultConfig,
        x,
        y,
      });
      if (anchor && type !== 'END') {
        state.designer.edges.push({ key: `e-${anchor.key}-${key}`, source: anchor.key, target: key });
      }
      state.designer.selectedKey = key;
    }
    toast(`Added ${nameMap[kind] || kind}`);
  }

  async function saveFlowModal() {
    const name = ($('#fl-new-name') || {}).value || '';
    const key = ($('#fl-new-key') || {}).value || '';
    const type = ($('#fl-new-type') || {}).value || 'FEATURE_DELIVERY';
    const description = ($('#fl-new-desc') || {}).value || '';
    if (!name.trim()) {
      toast('Укажите имя');
      return;
    }
    if (state.modalMode === 'edit' && state.editingId) {
      const current = await fetchJSON(`/scenarios/${state.editingId}`);
      if (productStatus(current) !== 'draft') {
        toast('Сначала верните сценарий в черновик (Править)');
        return;
      }
      const detail = asDetail(await fetchJSON(`/scenarios/${state.editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          revision: current.revision,
          name: name.trim(),
          description,
          dsl: current.dsl,
        }),
      }));
      closeModal();
      await loadCatalog();
      state.detail = detail;
      show($('#fl-drawer'), true);
      renderDetail();
      toast('Е2Е Сценарий обновлён');
      return;
    }
    const detail = asDetail(await fetchJSON('/scenarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        key: key.trim() || undefined,
        kind: 'e2e',
        description,
      }),
    }));
    closeModal();
    await loadCatalog();
    state.detail = detail;
    show($('#fl-drawer'), true);
    renderDetail();
    toast('Черновик Е2Е Сценария создан');
  }

  async function deleteFlow(id) {
    const item = state.items.find((x) => x.id === id);
    const label = (item && item.name)
      || (state.detail && state.detail.flow && state.detail.flow.id === id && state.detail.flow.name)
      || id;
    if (!window.confirm(`Удалить Е2Е сценарий «${label}»? Это действие нельзя отменить.`)) {
      return;
    }
    await fetchJSON(`/scenarios/${id}`, { method: 'DELETE' });
    if (state.detail && state.detail.flow && state.detail.flow.id === id) {
      closeDrawer();
      closeDesigner();
    }
    await loadCatalog();
    toast('Е2Е Сценарий удалён');
  }

  function collectDesignerGraph() {
    const canvas = state.designer.canvas;
    let nodes = state.designer.nodes;
    let edges = state.designer.edges;
    if (canvas && typeof canvas.getGraph === 'function') {
      const g = canvas.getGraph();
      nodes = (g.nodes || []).map(fcNodeToDesigner);
      edges = (g.edges || []).map(designerEdgeFromFc);
    } else if (canvas && canvas.nodes) {
      nodes = canvas.nodes.map(fcNodeToDesigner);
      edges = (canvas.edges || []).map(designerEdgeFromFc);
    }
    return {
      stages: nodes.map((n) => {
        const config = Object.assign({}, n.config || {});
        const stage = {
          key: n.key,
          name: n.name,
          type: n.type,
          playbook_key: n.playbook_key || null,
          flow_key: n.flow_key || null,
          knowledge_space_key: n.knowledge_space_key || null,
          timeout_seconds: n.timeout_seconds || 3600,
          failure_behavior: n.failure_behavior || 'ASK_HUMAN',
          config,
        };
        if (n.x != null && n.y != null && Number.isFinite(n.x) && Number.isFinite(n.y)) {
          stage.x = n.x;
          stage.y = n.y;
          stage.config = Object.assign({}, config, { position: { x: n.x, y: n.y } });
        }
        return stage;
      }),
      edges: edges.map((e) => ({
        key: e.key || e.id || `e-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        condition: e.condition != null ? e.condition : (e.sourceHandle || null),
      })),
    };
  }

  async function saveDesignerGraph() {
    const id = scenarioId();
    if (!id) {
      toast('Сначала откройте Е2Е Сценарий');
      return;
    }
    if (productStatus(state.detail && state.detail.scenario) !== 'draft') {
      toast('Сначала нажмите «Править», чтобы вернуть черновик');
      return;
    }
    const canvas = state.designer.canvas;
    const dsl = canvas && typeof canvas.getGraph === 'function'
      ? canvas.getGraph()
      : collectDesignerGraph();
    const card = await fetchJSON(`/scenarios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revision: state.detail.revision, dsl }),
    });
    state.detail = asDetail(card);
    state.designer.graphId = card.id;
    if (canvas && canvas.setGraphId) canvas.setGraphId(card.id);
    if (canvas && typeof canvas.getGraph === 'function') {
      syncDesignerFromGraph(canvas.getGraph());
    }
    const title = $('#fl-designer-title');
    if (title && state.detail.flow) title.textContent = state.detail.flow.name || 'Е2Е';
    syncDesignerActions();
    toast(`Сохранено · rev ${card.revision}`);
  }

  async function setScenarioStatus(status) {
    const id = scenarioId();
    if (!id) {
      toast('Сначала откройте Е2Е Сценарий');
      return;
    }
    const prev = productStatus(state.detail && state.detail.scenario);
    const card = await fetchJSON(`/scenarios/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revision: state.detail.revision, status }),
    });
    state.detail = asDetail(card);
    syncDesignerActions();
    await loadCatalog();
    const msg = status === 'launched'
      ? 'Запущено — агент берёт этот plan'
      : status === 'draft'
        ? 'Снова черновик'
        : prev === 'launched'
          ? 'Снято с запуска'
          : 'Опубликовано';
    toast(msg);
  }

  async function publishDesignerGraph() {
    const id = scenarioId();
    if (!id) {
      toast('Сначала откройте Е2Е Сценарий');
      return;
    }
    if (productStatus(state.detail && state.detail.scenario) === 'draft') {
      await saveDesignerGraph();
    }
    await setScenarioStatus('published');
  }

  function syncDesignerActions() {
    const status = productStatus(state.detail && state.detail.scenario);
    const saveBtn = $('#fl-designer-save');
    const publishBtn = $('#fl-designer-publish');
    const launchBtn = $('#fl-designer-launch');
    const disarmBtn = $('#fl-designer-disarm');
    const draftBtn = $('#fl-designer-draft');
    if (saveBtn) saveBtn.disabled = status !== 'draft';
    if (publishBtn) publishBtn.classList.toggle('fl-hidden', status !== 'draft');
    if (launchBtn) launchBtn.classList.toggle('fl-hidden', status !== 'published');
    if (disarmBtn) disarmBtn.classList.toggle('fl-hidden', status !== 'launched');
    if (draftBtn) draftBtn.classList.toggle('fl-hidden', status === 'draft');
  }

  async function loadKnowledgeOptions() {
    const list = $('#fl-ks-datalist');
    if (!list || list.dataset.loaded) return;
    try {
      const data = await fetchJSON('/knowledge-spaces');
      list.innerHTML = (data.knowledge_spaces || []).map((s) =>
        `<option value="${esc(s.key)}">${esc(s.name || s.key)}</option>`
      ).join('');
      list.dataset.loaded = '1';
    } catch (_) { /* optional */ }
  }

  async function loadPlaybookOptions() {
    return;
  }

  function openLinkedPlaybook() {
    const key = (($('#fl-insp-playbook') || {}).value || '').trim();
    if (!key) {
      toast('Выберите сценарий');
      return;
    }
    if (window.PlatformUtil) window.PlatformUtil.navigateTo('flows', { id: key, key });
  }

  async function loadFlowOptions() {
    const sel = $('#fl-insp-flow');
    if (!sel || sel.dataset.loaded) return;
    try {
      const data = await fetchJSON('/scenarios?kind=e2e');
      const items = data.items || [];
      const currentKey = state.detail && state.detail.flow ? state.detail.flow.key : null;
      const opts = ['<option value="">— выберите сценарий —</option>']
        .concat(items
          .filter((f) => f.key !== currentKey)
          .map((f) => `<option value="${esc(f.key)}">${esc(f.name || f.key)} (${esc(f.key)})</option>`));
      sel.innerHTML = opts.join('');
      sel.dataset.loaded = '1';
    } catch (_) { /* optional */ }
  }

  function openLinkedFlow() {
    const key = (($('#fl-insp-flow') || {}).value || '').trim();
    if (!key) {
      toast('Выберите E2E сценарий');
      return;
    }
    const item = state.items.find((f) => f.key === key);
    if (item) {
      openDetail(item.id).then(openDesigner).catch((e) => toast(e.message));
      return;
    }
    if (window.PlatformUtil) window.PlatformUtil.navigateTo('flows', { id: key, key });
  }

  function openLinkedKnowledge() {
    const key = (($('#fl-insp-kspace') || {}).value || '').trim();
    if (!key) {
      toast('Укажите knowledge space');
      return;
    }
    if (window.PlatformUtil) window.PlatformUtil.navigateTo('knowledge', { id: key, key });
  }

  async function simulate() {
    const id = scenarioId();
    if (!id) {
      toast('Сначала откройте Е2Е Сценарий');
      return;
    }
    const designerEl = $('#fl-designer');
    const designerOpen = designerEl && !designerEl.classList.contains('fl-hidden');
    if (designerOpen && productStatus(state.detail && state.detail.scenario) === 'draft') {
      await saveDesignerGraph();
    }
    const run = await fetchJSON('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: id, mode: 'test', input: {} }),
    });
    toast(`Test run ${run.id} · ${run.status}`);
  }

  function bindUI() {
    const search = $('#fl-search');
    const type = $('#fl-type-filter');
    const status = $('#fl-status-filter');
    if (search) search.oninput = () => { state.filters.search = search.value; loadCatalog().catch((e) => toast(e.message)); };
    if (type) type.onchange = () => { state.filters.type = type.value; loadCatalog().catch((e) => toast(e.message)); };
    if (status) status.onchange = () => { state.filters.status = status.value; loadCatalog().catch((e) => toast(e.message)); };

    const createBtn = $('#fl-btn-create');
    const designerBtn = $('#fl-btn-designer');
    if (createBtn) createBtn.onclick = openModal;
    if (designerBtn) designerBtn.onclick = () => {
      if (!state.detail && state.items[0]) {
        openDetail(state.items[0].id).then(openDesigner).catch((e) => toast(e.message));
      } else {
        openDesigner();
      }
    };

    const closeDrawerBtn = $('#fl-close-drawer');
    if (closeDrawerBtn) closeDrawerBtn.onclick = closeDrawer;
    root()?.querySelectorAll('.fl-tabs button').forEach((b) => {
      b.onclick = () => showTab(b.dataset.tab);
    });
    const editBtn = $('#fl-edit-designer');
    if (editBtn) editBtn.onclick = openDesigner;

    const closeModalBtn = $('#fl-close-modal');
    const cancelModal = $('#fl-cancel-modal');
    const saveFlow = $('#fl-save-flow');
    if (closeModalBtn) closeModalBtn.onclick = closeModal;
    if (cancelModal) cancelModal.onclick = closeModal;
    if (saveFlow) saveFlow.onclick = () => saveFlowModal().catch((e) => toast(e.message));

    const closeDesignerBtn = $('#fl-close-designer');
    const simulateBtn = $('#fl-simulate');
    const saveBtn = $('#fl-designer-save');
    const publishBtn = $('#fl-designer-publish');
    const launchBtn = $('#fl-designer-launch');
    const disarmBtn = $('#fl-designer-disarm');
    const draftBtn = $('#fl-designer-draft');
    const autoLayoutBtn = $('#fl-btn-auto-layout');
    if (closeDesignerBtn) closeDesignerBtn.onclick = closeDesigner;
    if (simulateBtn) simulateBtn.onclick = () => simulate().catch((e) => toast(e.message));
    if (saveBtn) saveBtn.onclick = () => saveDesignerGraph().catch((e) => toast(e.message));
    if (publishBtn) publishBtn.onclick = () => publishDesignerGraph().catch((e) => toast(e.message));
    if (launchBtn) launchBtn.onclick = () => setScenarioStatus('launched').catch((e) => toast(e.message));
    if (disarmBtn) disarmBtn.onclick = () => setScenarioStatus('published').catch((e) => toast(e.message));
    if (draftBtn) draftBtn.onclick = () => setScenarioStatus('draft').catch((e) => toast(e.message));
    if (autoLayoutBtn) {
      autoLayoutBtn.onclick = () => {
        if (state.designer.canvas && state.designer.canvas.autoLayout) {
          state.designer.canvas.autoLayout();
        }
      };
    }
  }

  function bindInspectorResize() {
    const grid = root()?.querySelector('.fl-designer-body');
    const handle = $('#fl-inspector-resizer');
    if (!grid || !handle || handle.dataset.bound === '1') return;
    handle.dataset.bound = '1';

    const STORAGE_KEY = 'fl.inspectorWidth';
    const MIN = 220;
    const MAX = 720;
    const DEFAULT = 260;

    function applyWidth(px) {
      const width = Math.max(MIN, Math.min(MAX, Math.round(px)));
      grid.style.setProperty('--fl-inspector-w', `${width}px`);
      return width;
    }

    try {
      const saved = parseInt(localStorage.getItem(STORAGE_KEY) || '', 10);
      if (saved) applyWidth(saved);
      else applyWidth(DEFAULT);
    } catch (_) {
      applyWidth(DEFAULT);
    }

    let dragging = false;
    let startX = 0;
    let startWidth = DEFAULT;

    function onMove(ev) {
      if (!dragging) return;
      const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const delta = startX - clientX;
      applyWidth(startWidth + delta);
      ev.preventDefault();
    }

    function onUp() {
      if (!dragging) return;
      dragging = false;
      grid.classList.remove('is-resizing-inspector');
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend', onUp);
      const raw = getComputedStyle(grid).getPropertyValue('--fl-inspector-w');
      const width = parseInt(raw, 10);
      if (width) {
        try { localStorage.setItem(STORAGE_KEY, String(width)); } catch (_) { /* ignore */ }
      }
    }

    handle.addEventListener('pointerdown', (ev) => {
      if (ev.button != null && ev.button !== 0) return;
      dragging = true;
      startX = ev.clientX;
      startWidth = parseInt(getComputedStyle(grid).getPropertyValue('--fl-inspector-w'), 10) || DEFAULT;
      grid.classList.add('is-resizing-inspector');
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
      ev.preventDefault();
    });

    handle.addEventListener('dblclick', () => {
      applyWidth(DEFAULT);
      try { localStorage.setItem(STORAGE_KEY, String(DEFAULT)); } catch (_) { /* ignore */ }
    });
  }

  async function load(openId, opts) {
    bindUI();
    await loadCatalog();
    if (openId) {
      const byKey = state.items.find((i) => i.key === openId || String(i.id) === String(openId));
      await openDetail(byKey ? byKey.id : openId);
      if (opts && opts.designer) {
        openDesigner();
      }
    }
  }

  window.FlowsModule = { load, openDetail };
})();
