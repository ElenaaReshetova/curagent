/**
 * Согласования — очередь, ревью и решения.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);

  const STATUS_LABELS = {
    OPEN: 'Открыто',
    ASSIGNED: 'Назначено',
    IN_REVIEW: 'На ревью',
    ESCALATED: 'Эскалировано',
    APPROVED: 'Утверждено',
    REJECTED: 'Отклонено',
    CHANGES_REQUESTED: 'Нужны правки',
    COMPLETED: 'Завершено',
  };

  const PRIORITY_LABELS = {
    HIGH: 'Высокий',
    MEDIUM: 'Средний',
    LOW: 'Низкий',
  };

  const TYPE_LABELS = {
    APPROVAL: 'Утверждение',
    REVIEW: 'Ревью',
    RISK_ACCEPTANCE: 'Принятие риска',
    PUBLICATION_APPROVAL: 'Публикация',
    MANUAL_INPUT: 'Ручной ввод',
    SIGN_OFF: 'Подпись',
  };

  const DECISION_LABELS = {
    APPROVE: 'Утвердить',
    REJECT: 'Отклонить',
    REQUEST_CHANGES: 'Запросить правки',
    PROVIDE_INPUT: 'Предоставить данные',
    ACCEPT_RISK: 'Принять риск',
    DECLINE_RISK: 'Отклонить риск',
    ACKNOWLEDGE: 'Подтвердить',
    SELECT_OPTION: 'Выбрать вариант',
  };

  const TERMINAL_STATUSES = new Set([
    'APPROVED', 'REJECTED', 'CHANGES_REQUESTED', 'INPUT_PROVIDED', 'EXPIRED', 'CANCELLED', 'SUPERSEDED',
  ]);

  const state = {
    items: [],
    metrics: null,
    detail: null,
    currentView: 'all',
    filters: { search: '', type: '', priority: '', status: '' },
    runMode: null,
  };

  function root() {
    return document.getElementById('human-checkpoints-module');
  }

  function $(sel) {
    return root() ? root().querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('hc-hidden', !visible);
    if (el.classList.contains('hc-detail') || el.classList.contains('hc-modal')) {
      el.classList.toggle('open', visible);
    }
  }

  function selectedCheckpoint() {
    return (state.detail && state.detail.checkpoint) || {};
  }

  function statusLabel(status) {
    const key = String(status || '').toUpperCase();
    return STATUS_LABELS[key] || String(status || '—').replace(/_/g, ' ');
  }

  function priorityLabel(priority) {
    const key = String(priority || '').toUpperCase();
    return PRIORITY_LABELS[key] || priority || '—';
  }

  function typeLabel(type) {
    const key = String(type || '').toUpperCase();
    return TYPE_LABELS[key] || type || '—';
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    if (state.currentView) q.set('view', state.currentView);
    if (state.filters.search) q.set('search', state.filters.search);
    if (state.filters.type) q.set('type', state.filters.type);
    if (state.filters.priority) q.set('priority', state.filters.priority);
    if (state.filters.status) q.set('status', state.filters.status);
    const data = await fetchJSON(`/human-checkpoints?${q.toString()}`);
    state.items = data.checkpoints || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderList();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#hc-metric-my-open': m.my_open,
      '#hc-metric-team': m.team_queue,
      '#hc-metric-overdue': m.overdue,
      '#hc-metric-avg': m.avg_decision_time,
      '#hc-metric-my-open-sub': `${m.due_today || 0} срок сегодня`,
      '#hc-metric-team-sub': `${m.unassigned || 0} без исполнителя`,
      '#hc-metric-overdue-sub': `${m.escalated || 0} эскалировано`,
      '#hc-metric-avg-sub': `${m.completed || 0} завершено`,
    };
    Object.entries(map).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value == null ? '—' : String(value);
    });
  }

  function renderList() {
    const list = $('#hc-checkpoint-list');
    if (!list) return;
    if (!state.items.length) {
      list.innerHTML = '<div class="hc-empty">Нет согласований для выбранного представления.</div>';
      return;
    }
    list.innerHTML = state.items.map((x) => `
      <article class="hc-checkpoint" data-id="${esc(x.id)}">
        <div class="hc-icon">✓</div>
        <div><b>${esc(x.title)}</b><small>${esc(x.execution_id)} · ${esc(x.source)}</small></div>
        <div><b>${esc(x.artifact_name)}</b><small>${esc(x.assignee)}</small></div>
        <span class="hc-priority ${String(x.priority || '').toLowerCase()}" title="${esc(x.priority)}">${esc(priorityLabel(x.priority))}</span>
        <span class="hc-status ${String(x.status || '').toLowerCase()}" title="${esc(x.status)}">${esc(statusLabel(x.status))}</span>
        <div class="hc-sla ${/просроч|overdue/i.test(String(x.sla_label || '')) ? 'overdue' : ''}">${esc(x.sla_label)}<small>SLA решения</small></div>
      </article>
    `).join('');
    list.querySelectorAll('.hc-checkpoint').forEach((row) => {
      row.onclick = () => openDetail(row.dataset.id);
    });
  }

  function isTerminal(cp) {
    return TERMINAL_STATUSES.has(String((cp && cp.status) || '').toUpperCase());
  }

  async function ensureArtifactPreview(cp) {
    if ((cp.artifact_preview || '').trim()) return;
    if (!cp.id) return;
    try {
      const data = await fetchJSON(`/human-checkpoints/${cp.id}/artifact`);
      const preview = data && data.artifact && data.artifact.preview;
      if (preview && state.detail && state.detail.checkpoint) {
        state.detail.checkpoint.artifact_preview = preview;
        if (data.artifact.name) state.detail.checkpoint.artifact_name = data.artifact.name;
        if (data.artifact.version) state.detail.checkpoint.artifact_version = data.artifact.version;
      }
    } catch (_) {
      // Preview endpoint may be empty for older mock checkpoints.
    }
  }

  async function openDetail(id) {
    state.detail = await fetchJSON(`/human-checkpoints/${id}`);
    await ensureArtifactPreview(selectedCheckpoint());
    renderDetail();
    show($('#hc-detail'), true);
    const cp = selectedCheckpoint();
    showTab((cp.artifact_preview || '').trim() ? 'artifact' : 'review');
  }

  function closeDetail() {
    destroyRunMode();
    state.detail = null;
    show($('#hc-detail'), false);
  }

  function destroyRunMode() {
    if (state.runMode && typeof state.runMode.destroy === 'function') {
      try { state.runMode.destroy(); } catch (_) { /* ignore */ }
    }
    state.runMode = null;
  }

  function resolveCheckpointGraphRunId(cp) {
    const summary = cp.review_summary || {};
    let runId = summary.graph_run_id || '';
    const wf = String(summary.temporal_workflow_id || '');
    if (!runId && wf.indexOf('graph-run-') === 0) {
      runId = wf.slice('graph-run-'.length);
    }
    return runId;
  }

  async function ensureCheckpointRunMode(cp) {
    const box = $('#hc-run-graph');
    const hint = $('#hc-graph-hint');
    if (!box) return;
    const runId = resolveCheckpointGraphRunId(cp || {});
    const graphId = (cp.review_summary || {}).graph_id || '';
    if ((!runId && !graphId) || !window.FlowCanvas || typeof window.FlowCanvas.createRunMode !== 'function') {
      destroyRunMode();
      box.innerHTML = '';
      if (hint) hint.textContent = 'Для этого согласования нет связанного graph run.';
      return;
    }
    const modeKey = runId || graphId;
    if (state.runMode && state.runMode.runId === modeKey) return;
    destroyRunMode();
    if (hint) hint.textContent = 'Контекст графа (readonly). Решения — в панели справа.';
    box.innerHTML = '<div style="padding:16px;color:var(--muted,#64748b)">Загрузка графа…</div>';
    try {
      let viewer = null;
      if (runId) {
        try { viewer = await fetchJSON(`/runs/${runId}/viewer`); } catch (_) { viewer = null; }
      }
      if ((!viewer || !(viewer.graph || viewer.canvas)) && graphId) {
        const rec = await fetchJSON(`/scenarios/${graphId}`);
        viewer = { graph: rec.canvas || rec.dsl || (rec.draft && rec.draft.dsl) || null, state: null };
      }
      const graph = viewer && (viewer.graph || viewer.canvas);
      if (!graph) {
        box.innerHTML = '<p class="hc-empty">Граф не найден</p>';
        return;
      }
      state.runMode = window.FlowCanvas.createRunMode({
        mount: box,
        kind: graph.kind || 'e2e',
        graph: graph,
        runId: runId,
        runState: viewer.state || null,
        readOnly: true,
        pollMs: 3000,
      });
      state.runMode.runId = modeKey;
    } catch (err) {
      destroyRunMode();
      box.innerHTML = `<p class="hc-empty">Не удалось загрузить граф: ${esc(err.message || err)}</p>`;
    }
  }

  function renderDetail() {
    const cp = selectedCheckpoint();
    const locked = isTerminal(cp);
    const title = $('#hc-detail-title');
    if (title) title.textContent = cp.title || '—';
    const execution = $('#hc-detail-execution');
    if (execution) {
      if (cp.execution_id && window.PlatformUtil && window.PlatformUtil.entityLink) {
        execution.innerHTML = window.PlatformUtil.entityLink('executions', cp.execution_id, { id: cp.execution_id });
        window.PlatformUtil.bindEntityLinks(execution);
      } else {
        execution.textContent = cp.execution_id || '—';
      }
    }
    const type = $('#hc-detail-type');
    if (type) type.textContent = typeLabel(cp.checkpoint_type);
    const risk = $('#hc-detail-risk');
    if (risk) risk.textContent = `Риск: ${cp.risk_level || '—'}`;
    const sla = $('#hc-detail-sla');
    if (sla) sla.textContent = `SLA: ${cp.sla_label || '—'}`;
    const statusChip = $('#hc-detail-status');
    if (statusChip) statusChip.textContent = statusLabel(cp.status);
    const q = $('#hc-question');
    if (q) q.textContent = cp.question || '—';
    const notice = $('#hc-pause-notice');
    if (notice) {
      notice.textContent = locked
        ? `Согласование закрыто: ${statusLabel(cp.status)}.`
        : 'Запуск приостановлен, пока согласование не закрыто.';
      notice.classList.toggle('hc-notice-done', locked);
    }
    const clock = $('#hc-sla-clock');
    if (clock) clock.textContent = cp.sla_label || '—';
    const due = $('#hc-sla-due');
    if (due) due.textContent = cp.due_label || '—';

    const summary = cp.review_summary || {};
    const summaryBox = $('#hc-summary-grid');
    if (summaryBox) {
      summaryBox.innerHTML = `
        <div><small>Артефакт</small><b>${esc(summary.artifact || `${cp.artifact_name || 'Артефакт'} ${cp.artifact_version || ''}`.trim())}</b></div>
        <div><small>Evidence</small><b>${esc(summary.evidence || cp.evidence_count || 0)} шт.</b></div>
        <div><small>Предупреждения</small><b class="${(cp.warnings_count || 0) ? 'warning-text' : 'good-text'}">${esc(cp.warnings_count || 0)} ${cp.warnings_count ? 'неблокирующих' : 'нет'}</b></div>
        <div><small>Контроли</small><b class="good-text">${esc(summary.controls_passed || cp.controls_passed || 0)} пройдено</b></div>
      `;
    }

    const changes = $('#hc-key-changes');
    if (changes) {
      changes.innerHTML = (cp.key_changes || []).length
        ? `<ul>${cp.key_changes.map((item) => `<li>${esc(item)}</li>`).join('')}</ul>`
        : '<p class="hc-empty">Ключевых изменений нет</p>';
    }

    const preview = (cp.artifact_preview || '').trim();
    const artifact = $('#hc-artifact-body');
    if (artifact) {
      if (preview) {
        artifact.textContent = preview;
        artifact.classList.remove('hc-empty-doc');
      } else {
        artifact.innerHTML = '<p class="hc-empty">Текст артефакта отсутствует</p>';
        artifact.classList.add('hc-empty-doc');
      }
    }

    const teaser = $('#hc-artifact-teaser');
    const teaserPanel = $('#hc-artifact-teaser-panel');
    if (teaser) {
      teaser.textContent = preview
        ? (preview.length > 1200 ? `${preview.slice(0, 1200)}…` : preview)
        : '';
    }
    if (teaserPanel) teaserPanel.classList.toggle('hc-hidden', !preview);

    const diff = $('#hc-diff-body');
    if (diff) {
      diff.innerHTML = (cp.artifact_diff || []).map((item) => {
        const cls = item.trim().startsWith('-') ? 'remove' : 'add';
        return `<div class="hc-diff ${cls}">${esc(item)}</div>`;
      }).join('') || '<p class="hc-empty">Diff недоступен</p>';
    }

    const evidence = $('#hc-evidence-body');
    if (evidence) {
      evidence.innerHTML = (cp.evidence || []).map((item) => `
        <div class="hc-evidence"><div><b>${esc(item.title)}</b><small>${esc(item.source)}</small></div><span>${esc(item.score)}</span></div>
      `).join('') || '<p class="hc-empty">Evidence отсутствует</p>';
    }

    const controls = $('#hc-controls-body');
    if (controls) {
      controls.innerHTML = (cp.controls || []).map((item) => `
        <div class="hc-control ${String(item.result || '').toLowerCase()}"><b>${esc(item.name)}</b><span>${esc(item.result)}</span></div>
      `).join('') || '<p class="hc-empty">Контролей нет</p>';
    }

    const activity = $('#hc-activity-body');
    if (activity) {
      activity.innerHTML = (cp.activity || []).map((item) => `
        <div class="hc-activity"><time>${esc(item.at)}</time><div><b>${esc(item.title)}</b><small>${esc(item.actor)}${item.detail ? ` · ${esc(item.detail)}` : ''}</small></div></div>
      `).join('') || '<p class="hc-empty">Активности нет</p>';
    }

    const audit = $('#hc-audit-body');
    if (audit) {
      audit.innerHTML = (cp.audit || []).length
        ? `<pre>${esc(JSON.stringify(cp.audit, null, 2))}</pre>`
        : '<p class="hc-empty">Записей аудита нет</p>';
    }

    const selectedKey = String(cp.selected_decision || '').toUpperCase();
    const choices = $('#hc-decision-choices');
    if (choices) {
      choices.innerHTML = (cp.decision_options || []).map((option, index) => {
        const selected = selectedKey ? option.key === selectedKey : (!locked && index === 0);
        return `
        <label class="hc-choice ${selected ? 'selected' : ''} ${locked ? 'locked' : ''}">
          <input type="radio" name="hc-decision" value="${esc(option.key)}" ${selected ? 'checked' : ''} ${locked ? 'disabled' : ''}/>
          <span><b>${esc(option.label)}</b><small>${esc(option.impact)}</small></span>
        </label>`;
      }).join('');
      if (!locked) {
        choices.querySelectorAll('input[name="hc-decision"]').forEach((radio) => {
          radio.onchange = () => {
            choices.querySelectorAll('.hc-choice').forEach((el) => el.classList.remove('selected'));
            radio.closest('.hc-choice').classList.add('selected');
            const option = (cp.decision_options || []).find((item) => item.key === radio.value);
            const impact = $('#hc-impact-text');
            if (impact) impact.textContent = option ? option.impact : '—';
          };
        });
      }
      const selectedOption = (cp.decision_options || []).find((item) => item.key === selectedKey)
        || ((!locked && cp.decision_options && cp.decision_options[0]) || null);
      const impact = $('#hc-impact-text');
      if (impact) impact.textContent = selectedOption ? selectedOption.impact : '—';
    }

    const result = $('#hc-decision-result');
    if (result) {
      if (locked) {
        const label = DECISION_LABELS[selectedKey] || statusLabel(cp.status);
        const commentText = (cp.decision_comment || '').trim();
        result.innerHTML = `<b>Решение зафиксировано:</b> ${esc(label)}${commentText ? `<small>${esc(commentText)}</small>` : ''}`;
        result.classList.remove('hc-hidden');
      } else {
        result.innerHTML = '';
        result.classList.add('hc-hidden');
      }
    }

    const comment = $('#hc-comment');
    if (comment) {
      if (locked) comment.value = cp.decision_comment || '';
      comment.disabled = locked;
      comment.placeholder = locked ? 'Комментарий к решению' : 'Добавьте обоснование или список правок...';
    }

    const primary = $('#hc-primary-action');
    if (primary) {
      primary.textContent = cp.status === 'OPEN' || cp.status === 'ESCALATED' ? 'Взять в работу' : 'Начать ревью';
      primary.disabled = locked;
      primary.classList.toggle('hc-hidden', locked);
    }
    const submit = $('#hc-submit-decision');
    if (submit) {
      submit.disabled = locked;
      submit.textContent = locked ? 'Решение уже отправлено' : 'Отправить решение';
    }
    const panel = $('.hc-decision-panel');
    if (panel) panel.classList.toggle('is-locked', locked);
    ensureCheckpointRunMode(cp).catch(() => { /* non-blocking */ });
  }

  function showTab(tab) {
    root()?.querySelectorAll('.hc-tabs button').forEach((button) => {
      button.classList.toggle('active', button.dataset.tab === tab);
    });
    root()?.querySelectorAll('.hc-tab-body').forEach((panel) => {
      panel.classList.toggle('hidden', panel.id !== `hc-tab-${tab}`);
    });
  }

  async function claimNext() {
    await fetchJSON('/human-checkpoints/claim-next', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reviewer: 'Alexey Khromov' }) });
    await loadCatalog();
    toast('Следующее согласование взято в работу');
  }

  async function primaryAction() {
    const cp = selectedCheckpoint();
    if (!cp.id || isTerminal(cp)) return;
    if (cp.status === 'OPEN' || cp.status === 'ESCALATED') {
      state.detail = await fetchJSON(`/human-checkpoints/${cp.id}/claim`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reviewer: 'Alexey Khromov' }) });
      toast('Согласование взято в работу');
    } else {
      state.detail = await fetchJSON(`/human-checkpoints/${cp.id}/start-review`, { method: 'POST' });
      toast('Ревью начато');
    }
    renderDetail();
    await loadCatalog();
  }

  async function submitDecision() {
    const cp = selectedCheckpoint();
    if (!cp.id) return;
    if (isTerminal(cp)) {
      toast('Решение уже зафиксировано');
      return;
    }
    const selected = root()?.querySelector('input[name="hc-decision"]:checked');
    const decision = selected ? selected.value : '';
    const comment = ($('#hc-comment') || {}).value || '';
    state.detail = await fetchJSON(`/human-checkpoints/${cp.id}/decisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, comment }),
    });
    renderDetail();
    await loadCatalog();
    toast(`Решение записано: ${decision}`);
  }

  function bindUI() {
    ['#hc-search', '#hc-type', '#hc-priority', '#hc-status'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      const key = sel === '#hc-search' ? 'search' : sel === '#hc-type' ? 'type' : sel === '#hc-priority' ? 'priority' : 'status';
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
        state.filters[key] = el.value;
        loadCatalog().catch((e) => toast(e.message));
      });
    });

    root()?.querySelectorAll('.hc-view').forEach((button) => {
      button.onclick = () => {
        root().querySelectorAll('.hc-view').forEach((el) => el.classList.remove('active'));
        button.classList.add('active');
        state.currentView = button.dataset.view;
        loadCatalog().catch((e) => toast(e.message));
      };
    });

    const teamBtn = $('#hc-team-btn');
    const claimNextBtn = $('#hc-claim-next-btn');
    const closeDetailBtn = $('#hc-close-detail');
    const primaryBtn = $('#hc-primary-action');
    const submitBtn = $('#hc-submit-decision');
    const openExecutionBtn = $('#hc-open-execution-btn');

    if (teamBtn) {
      teamBtn.onclick = () => {
        const teamView = root().querySelector('.hc-view[data-view="team"]');
        if (teamView) teamView.click();
      };
    }
    if (claimNextBtn) claimNextBtn.onclick = () => claimNext().catch((e) => toast(e.message));
    if (closeDetailBtn) closeDetailBtn.onclick = closeDetail;
    if (primaryBtn) primaryBtn.onclick = () => primaryAction().catch((e) => toast(e.message));
    if (submitBtn) submitBtn.onclick = () => submitDecision().catch((e) => toast(e.message));
    if (openExecutionBtn) {
      openExecutionBtn.onclick = () => {
        const cp = selectedCheckpoint();
        closeDetail();
        window.PlatformUtil.navigateTo('inspector', { id: cp.execution_id }).catch((e) => toast(e.message));
      };
    }

    root()?.querySelectorAll('.hc-tabs button').forEach((button) => {
      button.onclick = () => showTab(button.dataset.tab);
    });

    const openArtifactTab = $('#hc-open-artifact-tab');
    if (openArtifactTab) openArtifactTab.onclick = () => showTab('artifact');
  }

  async function load(openId) {
    bindUI();
    await loadCatalog();
    if (openId) await openDetail(openId);
  }

  window.HumanCheckpointsModule = { load, openDetail };
})();
