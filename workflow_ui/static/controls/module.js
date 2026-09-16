/**
 * Controls — catalog, detail drawer, editor, resolution preview.
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
    filters: { search: '', type: '', severity: '', status: '' },
  };

  function catalogMenu(id, actions) {
    return CardMenu().markup(id, actions || CardMenu().defaultActions());
  }

  function bindCardMenus(scope) {
    CardMenu().bind(scope || root(), (id, action) => {
      handleCardAction(action, id).catch((e) => toast(e.message));
    });
  }

  async function handleCardAction(action, id) {
    if (!id) {
      toast('Контроль не выбран');
      return;
    }
    if (action === 'edit') {
      if (!state.detail || String(control().id) !== String(id)) {
        await openDetail(id);
      }
      await openEditor();
      return;
    }
    if (action === 'delete') {
      await deleteControl(id);
    }
  }

  function root() {
    return document.getElementById('controls-module');
  }

  function $(sel) {
    return root() ? root().querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('co-hidden', !visible);
    if (el.classList.contains('co-drawer') || el.classList.contains('co-editor') || el.classList.contains('co-preview') || el.classList.contains('co-modal')) {
      el.classList.toggle('open', visible);
    }
  }

  function control() {
    return (state.detail && state.detail.control) || {};
  }

  function version() {
    return (state.detail && (state.detail.editable_version || state.detail.draft_version || state.detail.current_version)) || {};
  }

  function setSelectValue(sel, value) {
    const el = $(sel);
    if (!el || value == null) return;
    const str = String(value);
    if (![...el.options].some((o) => o.value === str)) {
      const opt = document.createElement('option');
      opt.value = str;
      opt.textContent = str;
      el.appendChild(opt);
    }
    el.value = str;
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    if (state.filters.search) q.set('search', state.filters.search);
    if (state.filters.type) q.set('type', state.filters.type);
    if (state.filters.severity) q.set('severity', state.filters.severity);
    if (state.filters.status) q.set('status', state.filters.status);
    const data = await fetchJSON(`/controls?${q.toString()}`);
    state.items = data.controls || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderGrid();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#co-metric-active': m.active,
      '#co-metric-evaluations': m.evaluations_today,
      '#co-metric-violations': m.open_violations,
      '#co-metric-exceptions': m.active_exceptions,
      '#co-metric-active-sub': `${m.critical || 0} критических`,
      '#co-metric-evaluations-sub': `${m.pass_rate_pct || 0}% пройдено`,
      '#co-metric-violations-sub': `${m.blocking_violations || 0} блокирующих`,
      '#co-metric-exceptions-sub': `${m.exceptions_expiring_week || 0} истекают на этой неделе`,
    };
    Object.entries(map).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value == null ? '—' : String(value);
    });
  }

  function renderGrid() {
    const grid = $('#co-grid');
    if (!grid) return;
    if (!state.items.length) {
      grid.innerHTML = '<div class="co-empty">Нет контролей по выбранным фильтрам.</div>';
      return;
    }
    grid.innerHTML = state.items.map((x) => `
      <article class="co-card" data-id="${esc(x.id)}" tabindex="0" role="button">
        <div class="card-head-row">
          <div class="co-card-head">
            <div class="co-icon">◆</div>
            <span class="co-status ${String(x.status || '').toLowerCase()}">${esc(x.status)}</span>
          </div>
          ${catalogMenu(x.id)}
        </div>
        <h3>${esc(x.name)}</h3>
        <p>${esc(x.description)}</p>
        <div class="co-badges">
          <span class="co-badge ${String(x.severity || '').toLowerCase()}">${esc(x.severity)}</span>
          <span class="co-badge">${esc(x.control_type)}</span>
          <span class="co-badge">${esc(x.enforcement)}</span>
        </div>
        <div class="co-metrics">
          <span>${esc(x.evaluation_point)}</span>
          <span>${esc(x.violations_count || 0)} нарушений</span>
          <span>${esc(x.pass_rate || '—')}</span>
        </div>
      </article>
    `).join('');
    bindCardMenus(grid);
    grid.querySelectorAll('.co-card').forEach((card) => {
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
  }

  async function openDetail(id) {
    state.detail = await fetchJSON(`/controls/${id}`);
    renderDetail();
    show($('#co-drawer'), true);
  }

  function closeDetail() {
    state.detail = null;
    show($('#co-drawer'), false);
  }

  function applicabilityText(v) {
    return (v.applicability || [])
      .map((cond) => `${cond.field || ''}=${cond.value || ''}`)
      .join('\n');
  }

  function fillEditorForm() {
    const c = control();
    const v = version();
    const name = $('#co-edit-name');
    const desc = $('#co-edit-description');
    const owner = $('#co-edit-owner');
    const expr = $('#co-edit-expression');
    const appl = $('#co-edit-applicability');
    const remed = $('#co-edit-remediation');
    if (name) name.value = c.name || '';
    if (desc) desc.value = c.description || '';
    if (owner) owner.value = c.owner_team || '';
    setSelectValue('#co-edit-type', v.control_type || 'QUALITY_GATE');
    setSelectValue('#co-edit-severity', v.severity || 'HIGH');
    setSelectValue('#co-edit-eval-point', v.evaluation_point || 'AFTER_GRAPH');
    setSelectValue('#co-edit-enforcement', v.enforcement_on_failed || 'BLOCK');
    if (expr) expr.value = v.expression || '';
    if (appl) appl.value = applicabilityText(v);
    if (remed) remed.value = (v.remediation_steps || []).join('\n');
  }

  function renderDetail() {
    const c = control();
    const v = version();
    const health = state.detail.health || {};
    const title = $('#co-detail-title');
    if (title) title.textContent = c.name || '—';
    const desc = $('#co-detail-description');
    if (desc) desc.textContent = c.description || '—';
    const meta = $('#co-detail-meta');
    if (meta) {
      meta.innerHTML = `
        <dt>Ключ</dt><dd>${esc(c.key)}</dd>
        <dt>Тип</dt><dd>${esc(v.control_type || '—')}</dd>
        <dt>Критичность</dt><dd>${esc(v.severity || '—')}</dd>
        <dt>Статус</dt><dd>${esc(v.status || c.status || '—')}</dd>
        <dt>Версия</dt><dd>${esc(v.semantic_version || '—')}</dd>
        <dt>Нарушения</dt><dd>${esc(v.violations_count || 0)}</dd>`;
    }
    const healthBox = $('#co-detail-health');
    if (healthBox) {
      healthBox.innerHTML = `
        <div class="co-health-row"><span>Последняя оценка</span><b>${esc(health.last_evaluation || '—')}</b></div>
        <div class="co-health-row"><span>Успешность</span><b class="ok">${esc(health.pass_rate_pct || 0)}%</b></div>
        <div class="co-health-row"><span>Открытые нарушения</span><b class="danger">${esc(health.open_violations || 0)}</b></div>
        <div class="co-health-row"><span>Активные исключения</span><b>${esc(health.active_exceptions || 0)}</b></div>`;
    }
    const evalPoint = $('#co-eval-point');
    if (evalPoint) evalPoint.textContent = v.evaluation_point || '—';
    const evalLogic = $('#co-eval-logic');
    if (evalLogic) evalLogic.textContent = v.expression || '—';
    const enforcement = $('#co-enforcement');
    if (enforcement) enforcement.textContent = v.enforcement_on_failed || '—';
    const owner = $('#co-owner');
    if (owner) owner.textContent = c.owner_team || '—';
    const applicability = $('#co-applicability');
    if (applicability) {
      applicability.innerHTML = (v.applicability || []).map((cond) =>
        `<span class="co-condition">${esc(cond.field)} ${esc(cond.operator || 'EQUALS')} ${esc(cond.value)}</span>`
      ).join('') || '<span class="co-condition">Все контексты</span>';
    }
    const violations = $('#co-violations');
    if (violations) {
      violations.innerHTML = (state.detail.violations || []).map((item) => `
        <div class="co-violation">
          <div><b>${esc(item.execution_id)}</b><small>${esc(item.summary)}</small></div>
          <span>${esc(item.status || 'OPEN')}</span>
        </div>
      `).join('') || '<p class="co-empty">Недавних нарушений нет</p>';
    }
    renderEditorChrome();
    fillEditorForm();

    const menuHost = $('#co-drawer-menu');
    if (menuHost && c.id) {
      menuHost.innerHTML = catalogMenu(c.id);
      bindCardMenus(menuHost);
    }
  }

  function renderEditorChrome() {
    const c = control();
    const v = version();
    const editorTitle = $('#co-editor-title');
    if (editorTitle) {
      const kind = v.status === 'DRAFT' ? 'Черновик' : 'Версия';
      editorTitle.textContent = `${c.name || 'Контроль'} · ${kind} ${v.semantic_version || '0.1.0'}`;
    }
    const preview = $('#co-effective-policy');
    if (preview) {
      preview.textContent = JSON.stringify({
        severity: v.severity,
        evaluationPoint: v.evaluation_point,
        expression: v.expression,
        onFailed: v.enforcement_on_failed,
        applicability: v.applicability || [],
      }, null, 2);
    }
    const problems = $('#co-problems');
    if (problems) {
      const report = v.validation_report || {};
      const rows = [
        ...(report.errors || []).map((e) => `<div class="co-problem warning">✕ ${esc(e.message || e)}</div>`),
        ...(report.warnings || []).map((w) => `<div class="co-problem warning">${esc(w.message || w)}</div>`),
      ];
      if (!(report.errors || []).length) {
        rows.push('<div class="co-problem good">✓ Выражение корректно</div>');
      }
      if (!(v.remediation_steps || []).length) {
        rows.push('<div class="co-problem warning">Добавьте шаги remediation</div>');
      }
      problems.innerHTML = rows.join('') || '<div class="co-problem good">✓ Проблем нет</div>';
    }
  }

  function switchEditorTab(tab) {
    const host = root();
    if (!host) return;
    host.querySelectorAll('.co-editor-nav button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.coTab === tab);
    });
    host.querySelectorAll('[data-co-section]').forEach((sec) => {
      sec.classList.toggle('co-hidden', sec.dataset.coSection !== tab);
    });
  }

  function bindEditorTabs() {
    root()?.querySelectorAll('.co-editor-nav button[data-co-tab]').forEach((btn) => {
      btn.onclick = () => switchEditorTab(btn.dataset.coTab);
    });
  }

  function openCreateModal() { show($('#co-create-modal'), true); }
  function closeCreateModal() { show($('#co-create-modal'), false); }

  async function openEditor(tab) {
    const id = control().id;
    if (!id) {
      toast('Контроль не выбран');
      return;
    }
    const v = version();
    if (v.status && v.status !== 'DRAFT') {
      state.detail = await fetchJSON(`/controls/${id}/draft`, { method: 'POST' });
      renderDetail();
    }
    fillEditorForm();
    renderEditorChrome();
    bindEditorTabs();
    switchEditorTab(tab || 'general');
    show($('#co-editor'), true);
  }

  function closeEditor() { show($('#co-editor'), false); }

  function collectEditorPayload() {
    return {
      name: ($('#co-edit-name') || {}).value || '',
      description: ($('#co-edit-description') || {}).value || '',
      owner_team: ($('#co-edit-owner') || {}).value || '',
      control_type: ($('#co-edit-type') || {}).value || 'QUALITY_GATE',
      severity: ($('#co-edit-severity') || {}).value || 'HIGH',
      evaluation_point: ($('#co-edit-eval-point') || {}).value || 'AFTER_GRAPH',
      expression: ($('#co-edit-expression') || {}).value || '',
      enforcement_on_failed: ($('#co-edit-enforcement') || {}).value || 'BLOCK',
      applicability: ($('#co-edit-applicability') || {}).value || '',
      remediation_steps: ($('#co-edit-remediation') || {}).value || '',
    };
  }

  async function saveDraft() {
    const id = control().id;
    if (!id) return;
    state.detail = await fetchJSON(`/controls/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collectEditorPayload()),
    });
    renderDetail();
    fillEditorForm();
    await loadCatalog();
    toast('Черновик контроля сохранён');
  }

  async function activateControl() {
    const id = control().id;
    if (!id) return;
    state.detail = await fetchJSON(`/controls/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collectEditorPayload()),
    });
    await fetchJSON(`/controls/${id}/activate`, { method: 'POST' });
    state.detail = await fetchJSON(`/controls/${id}`);
    renderDetail();
    await loadCatalog();
    toast('Контроль активирован');
  }

  async function createControl() {
    const name = ($('#co-new-name') || {}).value || 'Новый контроль governance';
    const type = ($('#co-new-type') || {}).value || 'QUALITY_GATE';
    const severity = ($('#co-new-severity') || {}).value || 'HIGH';
    const description = ($('#co-new-description') || {}).value || 'Обязательное требование governance.';
    const created = await fetchJSON('/controls', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, type, severity, description }),
    });
    closeCreateModal();
    await loadCatalog();
    const id = created && created.control && created.control.id;
    if (!id) {
      toast('Контроль создан, но не удалось открыть редактор');
      return;
    }
    await openDetail(id);
    await openEditor('applicability');
    toast('Черновик контроля создан');
  }

  async function deleteControl(id) {
    const item = state.items.find((x) => String(x.id) === String(id));
    const label = (item && item.name)
      || (control().id && String(control().id) === String(id) && control().name)
      || id;
    if (!window.confirm(`Удалить контроль «${label}»?`)) return;
    await fetchJSON(`/controls/${id}`, { method: 'DELETE' });
    if (state.detail && control().id && String(control().id) === String(id)) {
      closeDetail();
    }
    state.detail = null;
    await loadCatalog();
    toast('Контроль удалён');
  }

  async function validateControl() {
    const id = control().id;
    if (!id) return;
    const result = await fetchJSON(`/controls/${id}/validate`, { method: 'POST' });
    toast(result.valid ? 'Проверка завершена: блокирующих проблем нет' : `Проверка не пройдена: ${(result.errors || []).join('; ')}`);
    state.detail = await fetchJSON(`/controls/${id}`);
    renderDetail();
  }

  async function testControl() {
    const id = control().id;
    if (!id) return;
    const result = await fetchJSON(`/controls/${id}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context: { checkpoint: { status: 'PENDING' } } }),
    });
    toast(`Результат теста: ${result.result} · ${result.message} · применение ${result.enforcement}`);
  }

  function bindUI() {
    ['#co-search', '#co-type', '#co-severity', '#co-status'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      const key = sel === '#co-search' ? 'search' : sel.replace('#co-', '');
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
        state.filters[key] = el.value;
        loadCatalog().catch((e) => toast(e.message));
      });
    });

    const createBtn = $('#co-create-btn');
    const closeDrawer = $('#co-close-drawer');
    const editBtn = $('#co-edit-btn');
    const closeEditorBtn = $('#co-close-editor');
    const validateBtn = $('#co-validate-btn');
    const testBtn = $('#co-test-btn');
    const saveBtn = $('#co-save-draft-btn');
    const activateBtn = $('#co-activate-btn');
    const closeCreate = $('#co-close-create');
    const cancelCreate = $('#co-cancel-create');
    const saveCreate = $('#co-save-control');

    if (createBtn) createBtn.onclick = openCreateModal;
    if (closeDrawer) closeDrawer.onclick = closeDetail;
    if (editBtn) editBtn.onclick = () => openEditor().catch((e) => toast(e.message));
    if (closeEditorBtn) closeEditorBtn.onclick = closeEditor;
    if (validateBtn) validateBtn.onclick = () => validateControl().catch((e) => toast(e.message));
    if (testBtn) testBtn.onclick = () => testControl().catch((e) => toast(e.message));
    if (saveBtn) saveBtn.onclick = () => saveDraft().catch((e) => toast(e.message));
    if (activateBtn) activateBtn.onclick = () => activateControl().catch((e) => toast(e.message));
    if (closeCreate) closeCreate.onclick = closeCreateModal;
    if (cancelCreate) cancelCreate.onclick = closeCreateModal;
    if (saveCreate) saveCreate.onclick = () => createControl().catch((e) => toast(e.message));

    bindEditorTabs();
  }

  async function load(openId) {
    bindUI();
    await loadCatalog();
    if (openId) await openDetail(openId);
  }

  window.ControlsModule = { load, openDetail };
})();
