/**
 * Rules module — Catalog / Full-screen Detail / Resolve preview.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const STATUS_LABELS = {
    PUBLISHED: 'Опубликовано',
    DRAFT: 'Черновик',
    DEPRECATED: 'Устарело',
    active: 'Активно',
    draft: 'Черновик',
    deprecated: 'Устарело',
    archived: 'Архив',
  };

  const state = {
    items: [],
    metrics: null,
    detail: null,
    filters: { search: '', status: '' },
    uiBound: false,
    modalMode: 'create',
    editingId: null,
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
      toast('Правило не выбрано');
      return;
    }
    if (action === 'edit') {
      await openEditModal(id);
      return;
    }
    if (action === 'delete') {
      await deleteRule(id);
    }
  }

  function root() {
    return document.getElementById('rules-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('ru-hidden', !visible);
  }

  function statusLabel(s) {
    return STATUS_LABELS[s] || STATUS_LABELS[String(s || '').toLowerCase()] || s || '—';
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    Object.entries(state.filters).forEach(([k, v]) => {
      if (v) q.set(k, v);
    });
    const data = await fetchJSON(`/rules?${q.toString()}`);
    state.items = data.rules || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderRows();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#ru-metric-published': m.published,
      '#ru-metric-drafts': m.drafts,
      '#ru-metric-executions': m.executions_30d,
    };
    Object.entries(map).forEach(([sel, val]) => {
      const el = $(sel);
      if (el) el.textContent = val == null ? '—' : String(val);
    });
  }

  function renderRows() {
    const tbody = $('#ru-rules-body');
    if (!tbody) return;
    if (!state.items.length) {
      tbody.innerHTML = '<tr><td colspan="6">Правила не найдены</td></tr>';
      return;
    }
    tbody.innerHTML = state.items.map((r) => `
      <tr class="ru-row" data-id="${esc(r.id)}" tabindex="0" role="button">
        <td><span class="ru-name">${esc(r.name)}</span><span class="ru-key">${esc(r.key)}</span></td>
        <td>${esc(r.priority)}</td>
        <td>v${esc(r.version || '—')}</td>
        <td><span class="ru-badge status-${esc((r.status || '').toLowerCase())}">${esc(statusLabel(r.status))}</span></td>
        <td>${esc(r.usage_count)}</td>
        <td class="table-actions-cell">${catalogMenu(r.id)}</td>
      </tr>`).join('');
    bindCardMenus(tbody);
  }

  async function openDetail(id) {
    if (!id) return;
    try {
      state.detail = await fetchJSON(`/rules/${encodeURIComponent(id)}`);
      show($('#ru-catalog-view'), false);
      show($('#ru-detail-view'), true);
      renderDetail();
      showTab('overview');
    } catch (err) {
      toast(err.message || 'Не удалось открыть правило');
    }
  }

  function backToCatalog() {
    state.detail = null;
    show($('#ru-detail-view'), false);
    show($('#ru-catalog-view'), true);
    loadCatalog().catch((e) => toast(e.message));
  }

  function currentVersion(detail) {
    return detail && (detail.published_version || detail.draft_version || detail.current_version);
  }

  function renderDetail() {
    const detail = state.detail;
    if (!detail) return;
    const rule = detail.rule || {};
    const ver = currentVersion(detail) || {};
    const status = detail.published_version
      ? 'PUBLISHED'
      : (detail.draft_version ? 'DRAFT' : (rule.status || '').toUpperCase());

    const eyebrow = $('#ru-detail-eyebrow');
    const title = $('#ru-detail-title');
    const desc = $('#ru-detail-desc');
    if (eyebrow) eyebrow.textContent = 'ПРАВИЛО';
    if (title) title.textContent = rule.name || '';
    if (desc) desc.textContent = rule.description || '';

    const strip = $('#ru-meta-strip');
    if (strip) {
      strip.innerHTML = `
        <span class="ru-pill status-${esc(String(status).toLowerCase())}">${esc(statusLabel(status))}</span>
        <span>v${esc(ver.semantic_version || '—')}</span>
        <span>Приоритет: ${esc(ver.priority != null ? ver.priority : '—')}</span>
        <span>Владелец: ${esc(rule.owner_team || '—')}</span>
        <span>Ключ: <code>${esc(rule.key || '—')}</code></span>`;
    }

    const meta = $('#ru-meta');
    if (meta) {
      meta.innerHTML = `
        <dt>Ключ</dt><dd>${esc(rule.key)}</dd>
        <dt>Приоритет</dt><dd>${esc(ver.priority)}</dd>
        <dt>Версия</dt><dd>v${esc(ver.semantic_version || '—')}</dd>
        <dt>Статус</dt><dd>${esc(statusLabel(ver.status || rule.status))}</dd>
        <dt>Владелец</dt><dd>${esc(rule.owner_team)}</dd>
        <dt>Ключ конфликта</dt><dd>${esc(ver.conflict_key || '—')}</dd>`;
    }
    const content = $('#ru-content');
    if (content) content.textContent = ver.content_markdown || '';
    const report = ver.validation_report || {};
    const validEl = $('#ru-validation');
    if (validEl) {
      if (report.valid !== false && (ver.validation_status === 'valid' || ver.validation_status === 'warning' || report.valid)) {
        validEl.innerHTML = `<div class="ru-valid">✓ Блокирующих ошибок нет</div>
          <p class="ru-muted">Статус: ${esc(ver.validation_status || 'valid')}</p>
          ${(report.warnings || []).map((w) => `<p class="ru-muted">⚠ ${esc(w.message || w.code)}</p>`).join('')}`;
      } else {
        validEl.innerHTML = (report.errors || []).map((e) =>
          `<div style="color:var(--ru-red)">✗ ${esc(e.message || e.code)}</div>`
        ).join('') || '<div style="color:var(--ru-red)">✗ Невалидно</div>';
      }
    }
    const versions = $('#ru-versions');
    if (versions) {
      versions.innerHTML = (detail.versions || []).map((v) =>
        `<p><strong>v${esc(v.semantic_version)}</strong> · ${esc(statusLabel(v.status))} · ${esc(v.validation_status)}</p>`
      ).join('') || '<p class="ru-muted">Нет версий</p>';
    }

    const menuHost = $('#ru-detail-menu');
    if (menuHost && rule.id) {
      menuHost.innerHTML = catalogMenu(rule.id);
      bindCardMenus(menuHost);
    }
  }

  function showTab(tab) {
    root()?.querySelectorAll('.ru-tabs button').forEach((b) => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    ['overview', 'content', 'usage', 'versions', 'validation'].forEach((t) => {
      show($(`#ru-tab-${t}`), t === tab);
    });
    if (tab === 'usage') renderUsage();
  }

  async function renderUsage() {
    const el = $('#ru-usage-list');
    if (!el || !state.detail) return;
    const rule = state.detail.rule || {};
    el.innerHTML = '<p class="ru-muted">Загрузка привязок…</p>';
    try {
      const data = await fetchJSON(`/rules/${rule.id}/usage`);
      const usages = data.usages || [];
      if (!usages.length) {
        el.innerHTML = `<p class="ru-muted">Правило <strong>${esc(rule.key || '')}</strong> ещё не привязано к графу.</p>
          <p class="ru-muted">Привязки задаются в Control Packs и компилируются в Governance Tail графа.</p>`;
        return;
      }
      el.innerHTML = `<table class="ru-usage-table"><thead><tr>
          <th>Граф / сценарий</th><th>Шаг</th><th>Версия</th><th>Статус</th>
        </tr></thead><tbody>${usages.map((u) => {
          const name = u.flow_name || u.flow_key || u.playbook_name || u.playbook_key;
          const key = u.flow_id || u.flow_key || u.playbook_id || u.playbook_key;
          const link = key && window.PlatformUtil && window.PlatformUtil.entityLink
            ? window.PlatformUtil.entityLink('flows', name, { id: key, key })
            : esc(name);
          return `<tr>
            <td>${link}</td>
            <td><code>${esc(u.step_key || '—')}</code></td>
            <td>v${esc(u.semantic_version || '—')}</td>
            <td>${esc(statusLabel(u.version_status || u.status))}</td>
          </tr>`;
        }).join('')}</tbody></table>`;
      if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
        window.PlatformUtil.bindEntityLinks(el);
      }
    } catch (err) {
      el.innerHTML = `<p class="ru-muted">Не удалось загрузить привязки: ${esc(err.message || err)}</p>`;
    }
  }

  function openModal() {
    state.modalMode = 'create';
    state.editingId = null;
    const title = $('#ru-modal-title');
    const saveBtn = $('#ru-save-rule');
    const key = $('#ru-new-key');
    if (title) title.textContent = 'Новое правило';
    if (saveBtn) saveBtn.textContent = 'Создать черновик';
    if (key) {
      key.disabled = false;
      key.title = '';
    }
    show($('#ru-modal'), true);
  }

  async function openEditModal(id) {
    const detail = (state.detail && state.detail.rule && String(state.detail.rule.id) === String(id))
      ? state.detail
      : await fetchJSON(`/rules/${encodeURIComponent(id)}`);
    const rule = detail.rule || {};
    state.modalMode = 'edit';
    state.editingId = rule.id || id;
    state.detail = detail;
    const title = $('#ru-modal-title');
    const saveBtn = $('#ru-save-rule');
    const name = $('#ru-new-name');
    const key = $('#ru-new-key');
    const desc = $('#ru-new-desc');
    if (title) title.textContent = 'Редактировать правило';
    if (saveBtn) saveBtn.textContent = 'Сохранить';
    if (name) name.value = rule.name || '';
    if (key) {
      key.value = rule.key || '';
      key.disabled = true;
      key.title = 'Ключ нельзя изменить';
    }
    if (desc) desc.value = rule.description || '';
    show($('#ru-modal'), true);
  }

  function closeModal() {
    show($('#ru-modal'), false);
    state.modalMode = 'create';
    state.editingId = null;
    const key = $('#ru-new-key');
    if (key) {
      key.disabled = false;
      key.title = '';
    }
  }

  async function createRule() {
    const name = ($('#ru-new-name') || {}).value || '';
    const key = ($('#ru-new-key') || {}).value || '';
    const description = ($('#ru-new-desc') || {}).value || '';
    if (!name.trim()) {
      toast('Укажите название');
      return;
    }
    if (state.modalMode === 'edit' && state.editingId) {
      const detail = await fetchJSON(`/rules/${state.editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          description,
        }),
      });
      closeModal();
      await loadCatalog();
      state.detail = detail;
      show($('#ru-catalog-view'), false);
      show($('#ru-detail-view'), true);
      renderDetail();
      showTab('overview');
      toast('Правило обновлено');
      return;
    }
    const detail = await fetchJSON('/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        key: key.trim() || undefined,
        description,
      }),
    });
    closeModal();
    await loadCatalog();
    state.detail = detail;
    show($('#ru-catalog-view'), false);
    show($('#ru-detail-view'), true);
    renderDetail();
    showTab('overview');
    toast('Черновик правила создан');
  }

  async function deleteRule(id) {
    const item = state.items.find((r) => String(r.id) === String(id));
    const label = (item && item.name)
      || (state.detail && state.detail.rule && String(state.detail.rule.id) === String(id) && state.detail.rule.name)
      || id;
    if (!window.confirm(`Удалить правило «${label}»?`)) return;
    await fetchJSON(`/rules/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (state.detail && state.detail.rule && String(state.detail.rule.id) === String(id)) {
      backToCatalog();
      return;
    }
    await loadCatalog();
    toast('Правило удалено');
  }

  function bindUI() {
    if (state.uiBound) return;
    state.uiBound = true;

    ['search', 'status'].forEach((key) => {
      const el = $(`#ru-${key === 'search' ? 'search' : key + '-filter'}`);
      if (!el) return;
      const eventName = key === 'search' ? 'input' : 'change';
      el.addEventListener(eventName, () => {
        state.filters[key] = el.value;
        loadCatalog().catch((e) => toast(e.message));
      });
    });

    const tbody = $('#ru-rules-body');
    if (tbody) {
      tbody.addEventListener('click', (ev) => {
        if (ev.target.closest('.card-menu')) return;
        const row = ev.target.closest('tr.ru-row');
        if (!row || !row.dataset.id) return;
        openDetail(row.dataset.id);
      });
      tbody.addEventListener('keydown', (ev) => {
        if (ev.key !== 'Enter' && ev.key !== ' ') return;
        const row = ev.target.closest('tr.ru-row');
        if (!row || !row.dataset.id) return;
        ev.preventDefault();
        openDetail(row.dataset.id);
      });
    }

    root()?.querySelectorAll('.ru-tabs button').forEach((b) => {
      b.onclick = () => showTab(b.dataset.tab);
    });

    const actions = [
      ['#ru-btn-create', openModal],
      ['#ru-btn-back', backToCatalog],
      ['#ru-close-modal', closeModal],
      ['#ru-cancel-modal', closeModal],
      ['#ru-save-rule', () => createRule().catch((e) => toast(e.message))],
    ];
    actions.forEach(([sel, fn]) => {
      const el = $(sel);
      if (el) el.onclick = fn;
    });
  }

  async function load(openId) {
    if (!root()) return;
    show($('#ru-detail-view'), false);
    show($('#ru-catalog-view'), true);
    show($('#ru-modal'), false);
    bindUI();
    await loadCatalog();
    if (openId) {
      const byKey = state.items.find((i) => i.key === openId || String(i.id) === String(openId));
      await openDetail(byKey ? byKey.id : openId);
    }
  }

  window.RulesModule = { load, openDetail };
})();
