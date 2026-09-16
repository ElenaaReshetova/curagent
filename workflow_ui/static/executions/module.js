/**
 * Запуски — каталог / инспектор / модалка старта.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);

  const STATUS_LABELS = {
    RUNNING: 'Выполняется',
    WAITING_FOR_HUMAN: 'Ожидает человека',
    COMPLETED: 'Завершён',
    FAILED: 'Ошибка',
    PAUSED: 'Пауза',
    CANCELLED: 'Отменён',
  };

  const RISK_LABELS = {
    LOW: 'Низкий',
    MEDIUM: 'Средний',
    HIGH: 'Высокий',
    CRITICAL: 'Критический',
  };

  const ACTION_LABELS = {
    pause: 'пауза',
    cancel: 'отмена',
    retry: 'повтор',
  };

  const POLL_MS = 2000;
  const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED', 'CANCELLED']);

  const state = {
    items: [],
    metrics: null,
    detail: null,
    filters: { search: '', status: '', type: '', risk: '' },
    sort: { key: 'started_at', dir: 'desc' },
    pollTimer: null,
    pollInFlight: false,
    runMode: null,
  };

  function root() {
    return document.getElementById('executions-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('ex-hidden', !visible);
  }

  function statusClass(status) {
    return (status || 'running').toLowerCase();
  }

  function statusLabel(status) {
    const key = String(status || '').toUpperCase();
    return STATUS_LABELS[key] || String(status || '—').replace(/_/g, ' ');
  }

  function riskLabel(risk) {
    const key = String(risk || '').toUpperCase();
    return RISK_LABELS[key] || risk || '—';
  }

  function normalizeStatus(status) {
    return String(status || '').toUpperCase().replace(/-/g, '_');
  }

  function isTerminal(status) {
    return TERMINAL_STATUSES.has(normalizeStatus(status));
  }

  function isViewActive() {
    const view = document.getElementById('view-inspector');
    return !!(view && view.classList.contains('active') && !view.classList.contains('hidden'));
  }

  function isInspectorOpen() {
    const panel = $('#ex-inspector');
    return !!(panel && !panel.classList.contains('ex-hidden'));
  }

  function hasActiveExecutions() {
    if (isInspectorOpen() && state.detail && state.detail.execution && !isTerminal(ex().status)) return true;
    return state.items.some((x) => !isTerminal(x.status));
  }

  function fetchLive(path) {
    const sep = path.includes('?') ? '&' : '?';
    return fetchJSON(`${path}${sep}_=${Date.now()}`, { cache: 'no-store' });
  }

  function stopPolling() {
    if (!state.pollTimer) return;
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  function syncPolling() {
    if (!isViewActive() || document.visibilityState === 'hidden' || !hasActiveExecutions()) {
      stopPolling();
      return;
    }
    if (state.pollTimer) return;
    tickPoll().catch(() => {});
    state.pollTimer = setInterval(() => {
      tickPoll().catch(() => {});
    }, POLL_MS);
  }

  async function tickPoll() {
    if (!isViewActive() || document.visibilityState === 'hidden') {
      stopPolling();
      return;
    }
    if (state.pollInFlight) return;
    state.pollInFlight = true;
    try {
      const openId = ex().id;
      const inspectorOpen = isInspectorOpen();
      const refreshDetail = inspectorOpen && openId && !isTerminal(ex().status);
      const refreshCatalog = state.items.some((x) => !isTerminal(x.status));

      if (refreshDetail) {
        state.detail = await fetchLive(`/executions/${openId}`);
        renderInspector();
      }
      if (refreshCatalog) {
        await refreshCatalogQuiet();
      }
      if (!hasActiveExecutions()) stopPolling();
    } catch (_) {
      // Keep polling; operator can use manual refresh on persistent errors.
    } finally {
      state.pollInFlight = false;
    }
  }

  async function refreshCatalogQuiet() {
    const q = new URLSearchParams();
    if (state.filters.search) q.set('search', state.filters.search);
    if (state.filters.status) q.set('status', state.filters.status);
    if (state.filters.type) q.set('type', state.filters.type);
    if (state.filters.risk) q.set('risk', state.filters.risk);
    const data = await fetchLive(`/executions?${q.toString()}`);
    state.items = data.executions || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderTable();
  }

  async function refreshOpenDetail() {
    const openId = ex().id;
    if (!openId || !isInspectorOpen()) return;
    state.detail = await fetchLive(`/executions/${openId}`);
    renderInspector();
    syncPolling();
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    if (state.filters.search) q.set('search', state.filters.search);
    if (state.filters.status) q.set('status', state.filters.status);
    if (state.filters.type) q.set('type', state.filters.type);
    if (state.filters.risk) q.set('risk', state.filters.risk);
    const data = await fetchJSON(`/executions?${q.toString()}`);
    state.items = data.executions || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderTable();
    syncPolling();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#ex-metric-running': m.running,
      '#ex-metric-completed': m.completed_today,
      '#ex-metric-failed': m.failed,
    };
    Object.entries(map).forEach(([sel, val]) => {
      const el = $(sel);
      if (el) el.textContent = val == null ? '—' : String(val);
    });
    const subRunning = $('#ex-metric-running-sub');
    if (subRunning) subRunning.textContent = `${m.waiting_human || 0} ожидают человека`;
    const subCompleted = $('#ex-metric-completed-sub');
    if (subCompleted) subCompleted.textContent = `${m.success_rate_pct || 0}% успешно`;
    const subFailed = $('#ex-metric-failed-sub');
    if (subFailed) subFailed.textContent = `${m.retryable || 0} можно повторить`;
  }

  function parseUtcDate(value) {
    if (!value) return null;
    let raw = String(value).trim();
    // Server stores naive UTC; without Z the browser may treat it as local.
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(raw) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(raw)) {
      raw += 'Z';
    }
    const date = new Date(raw);
    return Number.isFinite(date.getTime()) ? date : null;
  }

  function parseTime(value) {
    const date = parseUtcDate(value);
    return date ? date.getTime() : NaN;
  }

  function formatStartedAt(value) {
    const date = parseUtcDate(value);
    if (!date) return { absolute: value ? String(value) : '—', relative: '' };
    const absolute = date.toLocaleString(undefined, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
    const delta = Math.max(0, Date.now() - date.getTime());
    const minutes = Math.floor(delta / 60000);
    let relative = 'только что';
    if (minutes >= 1 && minutes < 60) relative = `${minutes} мин назад`;
    else if (minutes >= 60 && minutes < 1440) relative = `${Math.floor(minutes / 60)} ч назад`;
    else if (minutes >= 1440) relative = `${Math.floor(minutes / 1440)} дн назад`;
    return { absolute, relative };
  }

  function sortedItems() {
    const items = state.items.slice();
    const { key, dir } = state.sort;
    const mult = dir === 'asc' ? 1 : -1;
    items.sort((a, b) => {
      if (key === 'started_at') {
        const ta = parseTime(a.started_at);
        const tb = parseTime(b.started_at);
        const aMissing = Number.isNaN(ta);
        const bMissing = Number.isNaN(tb);
        if (aMissing && bMissing) return String(b.id).localeCompare(String(a.id));
        if (aMissing) return 1;
        if (bMissing) return -1;
        if (ta === tb) return String(b.id).localeCompare(String(a.id));
        return (ta - tb) * mult;
      }
      return 0;
    });
    return items;
  }

  function syncSortHeader() {
    const btn = $('#ex-sort-started');
    if (!btn) return;
    const active = state.sort.key === 'started_at';
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    const ind = btn.querySelector('.ex-sort-ind');
    if (ind) ind.textContent = active && state.sort.dir === 'asc' ? '↑' : '↓';
  }

  function toggleSort(key) {
    if (state.sort.key === key) {
      state.sort.dir = state.sort.dir === 'desc' ? 'asc' : 'desc';
    } else {
      state.sort = { key, dir: 'desc' };
    }
    renderTable();
  }

  function renderTable() {
    const body = $('#ex-table-body');
    if (!body) return;
    syncSortHeader();
    const rows = sortedItems();
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="8" style="color:var(--ex-muted)">Запуски не найдены. Измените фильтры или создайте новый запуск.</td></tr>';
      return;
    }
    body.innerHTML = rows.map((x) => {
      const started = formatStartedAt(x.started_at);
      return `
      <tr class="ex-row" data-id="${esc(x.id)}">
        <td><span class="execution-name">${esc(x.title)}</span><span class="execution-id">${esc(x.id)}</span></td>
        <td>${esc(x.source)}</td>
        <td>${esc(x.flow_name)}</td>
        <td>${esc(x.current_stage)}</td>
        <td><div class="mini-progress"><i style="width:${esc(x.progress_pct)}%"></i></div><small>${esc(x.progress_pct)}%</small></td>
        <td><span class="status-badge ${statusClass(x.status)}" title="${esc(x.status)}">${esc(statusLabel(x.status))}</span></td>
        <td title="${esc(started.absolute)}"><span class="ex-started">${esc(started.absolute)}${started.relative ? `<small>${esc(started.relative)}</small>` : ''}</span></td>
        <td>${esc(x.duration)}</td>
      </tr>`;
    }).join('');
    body.querySelectorAll('.ex-row').forEach((row) => {
      row.onclick = () => openDetail(row.dataset.id);
    });
  }

  async function openDetail(id) {
    state.detail = await fetchJSON(`/executions/${id}`);
    show($('#ex-inspector'), true);
    renderInspector();
    showTab('overview');
    syncPolling();
  }

  function closeInspector() {
    destroyRunMode();
    show($('#ex-inspector'), false);
    state.detail = null;
    syncPolling();
  }

  function ex() {
    return (state.detail && state.detail.execution) || {};
  }

  function resolveGraphRefs(item) {
    const snap = item.snapshot || {};
    let runId = item.graph_run_id || snap.graph_run_id || '';
    let graphId = item.graph_id || snap.graph_id || '';
    const wf = String(snap.temporal_workflow_id || '');
    if (!runId && wf.indexOf('graph-run-') === 0) {
      runId = wf.slice('graph-run-'.length);
    }
    return { runId: runId || '', graphId: graphId || '' };
  }

  function destroyRunMode() {
    if (state.runMode && typeof state.runMode.destroy === 'function') {
      try { state.runMode.destroy(); } catch (_) { /* ignore */ }
    }
    state.runMode = null;
  }

  async function ensureRunMode(item) {
    const box = $('#ex-runtime-graph');
    if (!box) return;
    const refs = resolveGraphRefs(item || {});
    const runKey = refs.runId || refs.graphId || '';
    if (!runKey || !window.FlowCanvas || typeof window.FlowCanvas.createRunMode !== 'function') {
      destroyRunMode();
      renderGraphFallback(visibleStages((item && item.stage_runs) || []));
      return;
    }
    if (state.runMode && state.runMode.runId === runKey) {
      return;
    }
    destroyRunMode();
    box.classList.add('runtime-graph--canvas');
    box.innerHTML = '<div style="padding:12px;color:var(--ex-muted)">Загрузка графа…</div>';
    try {
      const viewer = await loadExecutionViewer(refs);
      const graph = viewer && (viewer.graph || viewer.canvas);
      if (!graph) {
        renderGraphFallback(visibleStages((item && item.stage_runs) || []));
        return;
      }
      const waiting = String(item.status || '') === 'WAITING_FOR_HUMAN';
      state.runMode = window.FlowCanvas.createRunMode({
        mount: box,
        kind: graph.kind || 'e2e',
        graph: graph,
        runId: refs.runId,
        runState: viewer.state || null,
        readOnly: !waiting,
        pollMs: 2000,
      });
      state.runMode.runId = runKey;
    } catch (err) {
      destroyRunMode();
      renderGraphFallback(visibleStages((item && item.stage_runs) || []));
      box.insertAdjacentHTML(
        'beforeend',
        `<div style="width:100%;color:var(--ex-muted);font-size:11px">Run Mode недоступен: ${esc(err.message || err)}</div>`,
      );
    }
  }

  async function loadExecutionViewer(refs) {
    if (refs.runId) {
      try {
        return await fetchJSON(`/runs/${refs.runId}/viewer`);
      } catch (_) { /* fall through to published graph */ }
    }
    if (!refs.graphId) return null;
    const rec = await fetchJSON(`/scenarios/${refs.graphId}`);
    return { graph: rec.canvas || rec.dsl || (rec.draft && rec.draft.dsl) || null, state: null };
  }

  function visibleStages(stages) {
    const list = stages || [];
    const legacy = { intake: 1, classify: 1, brd: 1, srd: 1, approval: 1 };
    const hasGraph = list.some((s) => s && s.key && !legacy[s.key] && String(s.key).indexOf('approval-') !== 0);
    if (!hasGraph) return list;
    return list.filter((s) => s && s.key && !legacy[s.key] && String(s.key).indexOf('approval-') !== 0);
  }

  function renderGraphFallback(stages) {
    const box = $('#ex-runtime-graph');
    if (!box) return;
    box.classList.remove('runtime-graph--canvas');
    if (!stages.length) {
      box.innerHTML = '<span style="color:var(--ex-muted)">Граф недоступен</span>';
      return;
    }
    box.innerHTML = stages.map((s, i) => {
      const cls = s.status === 'COMPLETED' ? 'done' : (s.status === 'RUNNING' ? 'running' : '');
      const arrow = i < stages.length - 1 ? '<span>→</span>' : '';
      return `<div class="g-node ${cls}">${esc(s.name)}<small>${esc(s.duration || statusLabel(s.status))}</small></div>${arrow}`;
    }).join('');
  }

  function renderInspector() {
    const item = ex();
    const title = $('#ex-inspector-title');
    if (title) title.textContent = `${item.id || ''} · ${item.title || ''}`;
    const bigStatus = $('#ex-big-status');
    if (bigStatus) {
      bigStatus.textContent = statusLabel(item.status);
      bigStatus.title = item.status || '';
    }
    const progress = $('#ex-big-progress');
    if (progress) progress.style.width = `${item.progress_pct || 0}%`;
    const progressText = $('#ex-progress-text');
    if (progressText) {
      progressText.textContent = `${item.progress_pct || 0}% выполнено · Текущий этап: ${item.current_stage || '—'}`;
    }
    const meta = $('#ex-meta');
    if (meta) {
      const flowLink = item.flow_id || item.flow_key
        ? (window.PlatformUtil && window.PlatformUtil.entityLink
          ? window.PlatformUtil.entityLink('flows', item.flow_name || item.flow_key || 'Е2Е Сценарий', { id: item.flow_id || item.flow_key })
          : esc(item.flow_name || '—'))
        : esc(item.flow_name || item.playbook_name || '—');
      const graphLink = item.graph_id || item.graph_key || item.playbook_id || item.playbook_key
        ? (window.PlatformUtil && window.PlatformUtil.entityLink
          ? window.PlatformUtil.entityLink('flows', item.graph_name || item.graph_key || item.playbook_name || item.playbook_key || 'Граф', { id: item.graph_id || item.graph_key || item.playbook_id || item.playbook_key })
          : esc(item.graph_name || item.playbook_name || '—'))
        : '—';
      const skillLink = item.current_skill
        ? (window.PlatformUtil && window.PlatformUtil.entityLink
          ? window.PlatformUtil.entityLink('skills', item.current_skill, { id: item.current_skill, key: item.current_skill })
          : esc(item.current_skill))
        : '—';
      meta.innerHTML = `
        <dt>Источник</dt><dd>${esc(`${item.source_type || ''} ${item.source_ref || ''}`.trim())}</dd>
        <dt>Е2Е Сценарий</dt><dd>${flowLink}${item.flow_version ? ` · v${esc(item.flow_version)}` : ''}</dd>
        <dt>Граф</dt><dd>${graphLink}${item.graph_version || item.playbook_version ? ` · v${esc(item.graph_version || item.playbook_version)}` : ''}</dd>
        <dt>Навык</dt><dd>${skillLink}</dd>
        <dt>Риск</dt><dd>${esc(riskLabel(item.risk_level))}</dd>
        <dt>Запущен</dt><dd>${esc(formatStartedAt(item.started_at).absolute)}</dd>
        <dt>Длительность</dt><dd>${esc(item.duration || '—')}</dd>
        <dt>Владелец</dt><dd>${esc(item.owner_team || '—')}</dd>`;
      if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
        window.PlatformUtil.bindEntityLinks(meta);
      }
    }
    const usage = $('#ex-usage');
    if (usage) {
      usage.innerHTML = `
        <div class="metric-row"><span>Токены</span><b>${esc((item.tokens || 0) / 1000)}k</b></div>
        <div class="metric-row"><span>Evidence</span><b>${esc(item.evidence_count || 0)}</b></div>
        <div class="metric-row"><span>Артефакты</span><b>${esc(item.artifacts_count || 0)}</b></div>`;
    }
    const activity = $('#ex-current-activity');
    if (activity) {
      activity.innerHTML = `
        <span class="pulse"></span>
        <div><b>${esc(item.current_activity || '—')}</b><small>Навык: ${esc(item.current_skill || '—')}</small></div>
        <em>${esc(item.duration || '—')}</em>`;
    }
    renderStagePath(visibleStages(item.stage_runs || []));
    renderTimeline(item.timeline || []);
    ensureRunMode(item);
    renderArtifacts(item.artifacts || []);
    renderEvidence(item.evidence || []);
    const runtime = $('#ex-runtime-pre');
    if (runtime) runtime.textContent = JSON.stringify(item.runtime_effective || {}, null, 2);
    const logs = $('#ex-logs-pre');
    if (logs) logs.textContent = item.logs || 'Логи отсутствуют';
    const snapshot = $('#ex-snapshot-pre');
    if (snapshot) snapshot.textContent = JSON.stringify(item.snapshot || {}, null, 2);
  }

  function renderStagePath(stages) {
    const box = $('#ex-stage-path');
    if (!box) return;
    if (!stages.length) {
      box.innerHTML = '<span style="color:var(--ex-muted)">Этапы отсутствуют</span>';
      return;
    }
    const parts = [];
    stages.forEach((s, i) => {
      if (i) parts.push(`<div class="line ${s.status === 'COMPLETED' ? 'done' : ''}"></div>`);
      const cls = s.status === 'COMPLETED' ? 'done' : (s.status === 'RUNNING' ? 'active' : '');
      const icon = s.status === 'COMPLETED' ? '✓' : String(i + 1);
      parts.push(`<div class="stage ${cls}"><span>${icon}</span><b>${esc(s.name)}</b><small>${esc(statusLabel(s.status))}</small></div>`);
    });
    box.innerHTML = parts.join('');
  }

  function renderTimeline(events) {
    const list = $('#ex-timeline-list');
    if (!list) return;
    list.innerHTML = events.length
      ? events.map((e) => `
        <div class="timeline-item">
          <time>${esc(e.at)}</time>
          <span class="timeline-dot"></span>
          <div><b>${esc(e.title)}</b><small>${esc(e.detail)}</small></div>
          <span>${esc(e.actor)}</span>
        </div>`).join('')
      : '<p style="color:var(--ex-muted)">Событий в хронологии нет</p>';
  }

  // legacy alias used by older call sites
  function renderGraph(stages) {
    renderGraphFallback(stages);
  }

  function renderArtifacts(artifacts) {
    const box = $('#ex-artifacts-list');
    if (!box) return;
    box.innerHTML = artifacts.length
      ? artifacts.map((a, index) => `
        <div class="artifact">
          <div><b>${esc(a.name)}</b><small>${esc(a.version)} · ${esc(a.status)}</small></div>
          <button type="button" class="ex-btn secondary small" data-artifact-index="${index}">Просмотр</button>
        </div>`).join('')
      : '<p style="color:var(--ex-muted)">Артефактов пока нет</p>';
    box.querySelectorAll('[data-artifact-index]').forEach((btn) => {
      btn.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        const artifact = artifacts[Number(btn.dataset.artifactIndex)];
        openArtifactView(artifact).catch((e) => toast(e.message));
      };
    });
  }

  function resolveArtifactPreview(artifact) {
    const snap = (ex().snapshot || {});
    const body = (snap.artifact_preview || '').trim();
    if (!body) return null;
    if (artifact && snap.artifact_name && snap.artifact_name !== artifact.name) return null;
    return {
      name: (artifact && artifact.name) || snap.artifact_name || 'Артефакт',
      version: (artifact && artifact.version) || snap.artifact_version || '',
      body,
    };
  }

  async function openArtifactView(artifact) {
    let preview = resolveArtifactPreview(artifact);
    if (!preview) {
      const executionId = ex().id || '';
      const checkpointId = `CHK-${executionId.replace(/^EXE-/, '')}`;
      try {
        const data = await fetchJSON(`/human-checkpoints/${checkpointId}/artifact`);
        const art = (data && data.artifact) || {};
        if ((art.preview || '').trim()) {
          preview = {
            name: art.name || (artifact && artifact.name) || 'Артефакт',
            version: art.version || (artifact && artifact.version) || '',
            body: art.preview,
          };
        }
      } catch (_) {
        // Checkpoint may not exist for this execution.
      }
    }
    if (!preview || !(preview.body || '').trim()) {
      toast('Содержимое артефакта пока недоступно');
      return;
    }
    const title = $('#ex-artifact-view-title');
    if (title) {
      title.textContent = [preview.name, preview.version].filter(Boolean).join(' · ');
    }
    const body = $('#ex-artifact-view-body');
    if (body) body.textContent = preview.body;
    show($('#ex-artifact-modal'), true);
  }

  function closeArtifactView() {
    show($('#ex-artifact-modal'), false);
  }

  function renderEvidence(evidence) {
    const box = $('#ex-evidence-list');
    if (!box) return;
    box.innerHTML = evidence.length
      ? evidence.map((e) => `
        <div class="evidence"><b>${esc(e.title)}</b><span>${esc(e.source)}</span></div>`).join('')
      : '<p style="color:var(--ex-muted)">Evidence отсутствует</p>';
  }

  function showTab(tab) {
    root()?.querySelectorAll('.ex-tabs button').forEach((b) => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    ['overview', 'timeline', 'graph', 'artifacts', 'evidence', 'runtime', 'logs', 'snapshot'].forEach((t) => {
      show($(`#ex-tab-${t}`), t === tab);
    });
  }

  function openStartModal() { show($('#ex-start-modal'), true); }
  function closeStartModal() { show($('#ex-start-modal'), false); }

  async function startExecution() {
    const title = ($('#ex-start-title') || {}).value || '';
    const type = ($('#ex-start-type') || {}).value || 'FLOW';
    const flow = ($('#ex-start-flow') || {}).value || 'Feature Delivery';
    const sourceType = ($('#ex-start-source-type') || {}).value || 'MANUAL';
    const reference = ($('#ex-start-ref') || {}).value || '';
    const detail = await fetchJSON('/executions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title.trim() || 'Новый запуск',
        type,
        flow_name: flow,
        source_type: sourceType,
        source_ref: reference,
      }),
    });
    closeStartModal();
    await loadCatalog();
    state.detail = detail;
    show($('#ex-inspector'), true);
    renderInspector();
    syncPolling();
    toast('Запуск создан');
  }

  async function action(name) {
    const id = ex().id;
    if (!id) return;
    if (name === 'cancel' && !confirm('Отменить запуск?')) return;
    const path = name === 'retry' ? 'retry' : name;
    await fetchJSON(`/executions/${id}/${path}`, { method: 'POST' });
    state.detail = await fetchJSON(`/executions/${id}`);
    renderInspector();
    await loadCatalog();
    syncPolling();
    toast(`Запрошено действие: ${ACTION_LABELS[name] || name}`);
  }

  function bindUI() {
    const mod = root();
    if (mod && mod.dataset.bound === '1') return;
    if (mod) mod.dataset.bound = '1';
    ['#ex-search', '#ex-status-filter', '#ex-type-filter', '#ex-risk-filter'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      const key = sel.includes('search') ? 'search' : sel.includes('status') ? 'status' : sel.includes('type') ? 'type' : 'risk';
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
        state.filters[key] = el.value;
        loadCatalog().catch((e) => toast(e.message));
      });
    });

    const sortStarted = $('#ex-sort-started');
    if (sortStarted) {
      sortStarted.onclick = (event) => {
        event.preventDefault();
        toggleSort('started_at');
      };
    }

    const refreshBtn = $('#ex-btn-refresh');
    const startBtn = $('#ex-btn-start');
    if (refreshBtn) {
      refreshBtn.onclick = () => {
        Promise.resolve()
          .then(() => loadCatalog())
          .then(() => refreshOpenDetail())
          .catch((e) => toast(e.message));
      };
    }
    if (startBtn) startBtn.onclick = openStartModal;

    const closeInspectorBtn = $('#ex-close-inspector');
    if (closeInspectorBtn) closeInspectorBtn.onclick = closeInspector;
    root()?.querySelectorAll('.ex-tabs button').forEach((b) => {
      b.onclick = () => showTab(b.dataset.tab);
    });

    const pauseBtn = $('#ex-pause-btn');
    const cancelBtn = $('#ex-cancel-btn');
    const retryBtn = $('#ex-retry-btn');
    if (pauseBtn) pauseBtn.onclick = () => action('pause').catch((e) => toast(e.message));
    if (cancelBtn) cancelBtn.onclick = () => action('cancel').catch((e) => toast(e.message));
    if (retryBtn) retryBtn.onclick = () => action('retry').catch((e) => toast(e.message));

    const closeStart = $('#ex-close-start');
    const cancelStart = $('#ex-cancel-start');
    const confirmStart = $('#ex-confirm-start');
    if (closeStart) closeStart.onclick = closeStartModal;
    if (cancelStart) cancelStart.onclick = closeStartModal;
    if (confirmStart) confirmStart.onclick = () => startExecution().catch((e) => toast(e.message));

    const closeArtifact = $('#ex-close-artifact');
    const closeArtifactBtn = $('#ex-close-artifact-btn');
    if (closeArtifact) closeArtifact.onclick = closeArtifactView;
    if (closeArtifactBtn) closeArtifactBtn.onclick = closeArtifactView;
    const artifactModal = $('#ex-artifact-modal');
    if (artifactModal) {
      artifactModal.onclick = (event) => {
        if (event.target === artifactModal) closeArtifactView();
      };
    }

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') stopPolling();
      else syncPolling();
    });
  }

  function unload() {
    stopPolling();
  }

  async function load(openId) {
    bindUI();
    await loadCatalog();
    if (openId) await openDetail(openId);
    else syncPolling();
  }

  window.ExecutionsModule = { load, openDetail, unload };
})();
