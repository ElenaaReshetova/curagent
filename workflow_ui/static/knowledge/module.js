/**
 * Knowledge Spaces — Catalog / Full-screen detail / Search playground.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const STATUS_LABELS = {
    ACTIVE: 'Активно',
    DEGRADED: 'Деградирует',
    DRAFT: 'Черновик',
    DISABLED: 'Отключено',
    ARCHIVED: 'Архив',
    ERROR: 'Ошибка',
  };

  const POLICY_LABELS = {
    max_results: 'Макс. результатов',
    dedupe: 'Дедупликация',
    prefer_fresh: 'Предпочитать свежие',
    roles: 'Роли',
  };

  const PROVIDER_HINTS = {
    jira: 'Например: project: PAY',
    confluence: 'Например: space: PAY',
    slack: 'Например: channels: #payments-dev, #payments-ops',
    git: 'Например: repos: payment-api, payment-core',
    api_catalog: 'Например: catalog: IAM',
    policy_library: 'Например: pack: pci-dss',
    audit_repo: 'Например: scope: pci',
    other: 'По одной паре ключ: значение на строку. Несколько значений — через запятую.',
  };

  const state = {
    items: [],
    metrics: null,
    detail: null,
    filters: { search: '', type: '', status: '' },
    editingSourceId: null,
    modalMode: 'create',
    editingId: null,
    createFormMounted: false,
  };

  function spaceMenuActions(space) {
    const status = String((space && space.status) || '').toUpperCase();
    const extra = [];
    if (status === 'DRAFT' || status === 'DISABLED' || status === 'DEGRADED') {
      extra.push({ id: 'activate', label: 'Активировать' });
    }
    if (status === 'ACTIVE' || status === 'DEGRADED') {
      extra.push({ id: 'disable', label: 'Отключить' });
    }
    return CardMenu().defaultActions(extra);
  }

  function catalogMenu(id, actions) {
    return CardMenu().markup(id, actions || CardMenu().defaultActions());
  }

  const CREATE_FIELD_TIPS = {
    name: {
      conceptKey: 'knowledge-space.name',
      label: 'Название',
      tip: 'Как область будет называться в каталоге. Можно менять позже. Пример: «Платежи».',
      controlHtml: '<input id="ks-new-name" placeholder="Например: Платежи" />',
    },
    key: {
      conceptKey: 'knowledge-space.key',
      label: 'Ключ',
      tip: 'Технический slug для API и привязок: латиница, цифры, дефисы. После создания не меняется. Пример: payments.',
      controlHtml: '<input id="ks-new-key" placeholder="например: payments" autocomplete="off" />',
    },
    type: {
      conceptKey: 'knowledge-space.type',
      label: 'Тип',
      tip: 'DOMAIN — домен, PRODUCT — продукт, TEAM — команда, SYSTEM — платформа, REGULATORY — compliance. Обычно DOMAIN.',
      controlHtml: '<select id="ks-new-type"><option>DOMAIN</option><option>PRODUCT</option><option>TEAM</option><option>SYSTEM</option><option>REGULATORY</option></select>',
    },
    classification: {
      conceptKey: 'knowledge-space.classification',
      label: 'Классификация',
      tip: 'Чувствительность данных: INTERNAL — обычный контекст, CONFIDENTIAL — коммерческий, RESTRICTED — жёсткие ограничения (PII/PCI).',
      controlHtml: '<select id="ks-new-class"><option>INTERNAL</option><option>CONFIDENTIAL</option><option>RESTRICTED</option></select>',
    },
    purpose: {
      conceptKey: 'knowledge-space.purpose',
      label: 'Назначение',
      tip: 'Зачем агенту эта область: какой домен и границы поиска. 1–3 предложения, без списка MCP-инструментов.',
      controlHtml: '<textarea id="ks-new-purpose" rows="3" placeholder="Доверенный контекст платёжных продуктов: Jira PAY, Confluence PAY, repos payment-*"></textarea>',
    },
  };

  function renderPlainCreateField(field) {
    return `<label class="ks-plain-field"><span class="ks-plain-label">${esc(field.label)} `
      + `<button type="button" class="help-q" title="${esc(field.tip)}" aria-label="Подсказка: ${esc(field.label)}">?</button></span>`
      + `${field.controlHtml}</label>`;
  }

  function mountCreateFormFields() {
    const host = $('#ks-modal-fields');
    if (!host || state.createFormMounted) return;

    if (!window.HelpUI || !HelpUI.renderFieldHelp) {
      host.innerHTML = [
        renderPlainCreateField(CREATE_FIELD_TIPS.name),
        renderPlainCreateField(CREATE_FIELD_TIPS.key),
        `<div class="ks-form-row">${renderPlainCreateField(CREATE_FIELD_TIPS.type)}${renderPlainCreateField(CREATE_FIELD_TIPS.classification)}</div>`,
        renderPlainCreateField(CREATE_FIELD_TIPS.purpose),
      ].join('');
      state.createFormMounted = true;
      return;
    }

    if (window.HelpRegistry && HelpRegistry.clear) HelpRegistry.clear();

    host.innerHTML = '';
    const appendField = (field) => {
      host.appendChild(HelpUI.renderFieldHelp({
        conceptKey: field.conceptKey,
        label: field.label,
        shortDescription: field.tip,
        controlHtml: field.controlHtml,
      }));
    };

    appendField(CREATE_FIELD_TIPS.name);
    appendField(CREATE_FIELD_TIPS.key);

    const row = document.createElement('div');
    row.className = 'ks-form-row';
    [CREATE_FIELD_TIPS.type, CREATE_FIELD_TIPS.classification].forEach((field) => {
      row.appendChild(HelpUI.renderFieldHelp({
        conceptKey: field.conceptKey,
        label: field.label,
        shortDescription: field.tip,
        controlHtml: field.controlHtml,
      }));
    });
    host.appendChild(row);
    appendField(CREATE_FIELD_TIPS.purpose);
    state.createFormMounted = true;
  }

  function resetCreateForm() {
    const name = $('#ks-new-name');
    const key = $('#ks-new-key');
    const type = $('#ks-new-type');
    const classification = $('#ks-new-class');
    const purpose = $('#ks-new-purpose');
    if (name) name.value = '';
    if (key) {
      key.value = '';
      key.disabled = false;
      key.title = '';
    }
    if (type) type.value = 'DOMAIN';
    if (classification) classification.value = 'INTERNAL';
    if (purpose) purpose.value = 'Доверенный контекст для этого домена.';
  }

  function bindCardMenus(scope) {
    CardMenu().bind(scope || root(), (id, action) => {
      handleCardAction(action, id).catch((e) => toast(e.message));
    });
  }

  async function handleCardAction(action, id) {
    if (!id) {
      toast('Область знаний не выбрана');
      return;
    }
    if (action === 'edit') {
      await openEditModal(id);
      return;
    }
    if (action === 'activate') {
      await activateSpace(id);
      return;
    }
    if (action === 'disable') {
      await disableSpace(id);
      return;
    }
    if (action === 'delete') {
      await deleteSpace(id);
    }
  }

  function root() {
    return document.getElementById('knowledge-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('ks-hidden', !visible);
  }

  function statusClass(status) {
    const s = (status || '').toLowerCase();
    if (s === 'active') return 'active-status';
    if (s === 'degraded') return 'degraded-status';
    return 'draft-status';
  }

  function statusLabel(status) {
    const key = String(status || '').toUpperCase();
    return STATUS_LABELS[key] || status || '—';
  }

  function boolLabel(v) {
    if (v === true) return 'Да';
    if (v === false) return 'Нет';
    return String(v);
  }

  function formatSelector(selector) {
    if (!selector || typeof selector !== 'object') return '';
    return Object.entries(selector)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
      .join(' · ');
  }

  function selectorToText(selector) {
    if (!selector || typeof selector !== 'object') return '';
    return Object.entries(selector)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
      .join('\n');
  }

  function parseSelectorText(text) {
    const selector = {};
    String(text || '').split('\n').forEach((line) => {
      const raw = line.trim();
      if (!raw || raw.startsWith('#')) return;
      const idx = raw.indexOf(':');
      if (idx <= 0) return;
      const key = raw.slice(0, idx).trim();
      const value = raw.slice(idx + 1).trim();
      if (!key) return;
      if (value.includes(',')) {
        selector[key] = value.split(',').map((x) => x.trim()).filter(Boolean);
      } else {
        selector[key] = value;
      }
    });
    return selector;
  }

  function policyRows(policy, fallback) {
    const entries = Object.entries(policy || {});
    if (!entries.length) {
      return `<dt>—</dt><dd style="color:var(--ks-muted)">${esc(fallback)}</dd>`;
    }
    return entries.map(([key, value]) => {
      const label = POLICY_LABELS[key] || key;
      const display = Array.isArray(value)
        ? value.join(', ')
        : typeof value === 'boolean'
          ? boolLabel(value)
          : String(value);
      return `<dt>${esc(label)}</dt><dd>${esc(display)}</dd>`;
    }).join('');
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    if (state.filters.search) q.set('search', state.filters.search);
    if (state.filters.type) q.set('type', state.filters.type);
    if (state.filters.status) q.set('status', state.filters.status);
    const data = await fetchJSON(`/knowledge-spaces?${q.toString()}`);
    state.items = data.knowledge_spaces || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderCards();
    fillPlaySelect();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#ks-metric-active': m.active_spaces,
      '#ks-metric-sources': m.connected_sources,
      '#ks-metric-success': m.search_success_pct != null ? `${m.search_success_pct}%` : '—',
      '#ks-metric-stale': m.stale_sources,
    };
    Object.entries(map).forEach(([sel, val]) => {
      const el = $(sel);
      if (el) el.textContent = val == null ? '—' : String(val);
    });
  }

  function renderCards() {
    const grid = $('#ks-cards');
    if (!grid) return;
    if (!state.items.length) {
      grid.innerHTML = '<p style="color:var(--ks-muted)">Области знаний не найдены</p>';
      return;
    }
    grid.innerHTML = state.items.map((x) => {
      const tags = (x.source_labels || []).slice(0, 3).map((s) => `<span class="ks-tag">${esc(s)}</span>`).join('');
      const more = (x.source_labels || []).length > 3
        ? `<span class="ks-tag">+${x.source_labels.length - 3}</span>` : '';
      const health = x.health_pct != null ? `${x.health_pct}%` : '—';
      const sourcesWord = x.source_count === 1 ? 'источник' : (x.source_count > 1 && x.source_count < 5 ? 'источника' : 'источников');
      return `<article class="ks-card" data-id="${esc(x.id)}" tabindex="0" role="button">
        <div class="card-head-row">
          <div class="ks-card-head"><div class="ks-icon">◫</div>
            <span class="ks-status ${statusClass(x.status)}">${esc(statusLabel(x.status))}</span></div>
          ${catalogMenu(x.id, spaceMenuActions(x))}
        </div>
        <h3>${esc(x.name)}</h3>
        <p>${esc(x.purpose || '')}</p>
        <div class="ks-tags">${tags}${more}</div>
        <div class="ks-metrics"><span>${esc(x.space_type)}</span><span>${esc(x.source_count)} ${sourcesWord}</span><span>${esc(health)}</span></div>
      </article>`;
    }).join('');
    bindCardMenus(grid);
    grid.querySelectorAll('.ks-card').forEach((card) => {
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

  function fillPlaySelect() {
    const sel = $('#ks-play-space');
    if (!sel) return;
    const current = sel.value;
    const preferred = state.detail && state.detail.space ? String(state.detail.space.id) : '';
    sel.innerHTML = state.items.map((x) =>
      `<option value="${esc(x.id)}">${esc(x.name)}</option>`
    ).join('');
    if (preferred && state.items.some((x) => String(x.id) === preferred)) {
      sel.value = preferred;
    } else if (current) {
      sel.value = current;
    }
  }

  async function openDetail(id) {
    state.detail = await fetchJSON(`/knowledge-spaces/${id}`);
    show($('#ks-catalog-view'), false);
    show($('#ks-detail-view'), true);
    renderDetail();
  }

  function backToCatalog() {
    state.detail = null;
    show($('#ks-detail-view'), false);
    show($('#ks-catalog-view'), true);
    loadCatalog().catch((e) => toast(e.message));
  }

  function renderDetail() {
    const detail = state.detail;
    if (!detail) return;
    const space = detail.space || {};

    const eyebrow = $('#ks-detail-eyebrow');
    const title = $('#ks-detail-title');
    const desc = $('#ks-detail-desc');
    if (eyebrow) eyebrow.textContent = `${space.space_type || 'DOMAIN'} · ${statusLabel(space.status)}`;
    if (title) title.textContent = space.name || '';
    if (desc) desc.textContent = space.purpose || '';

    const strip = $('#ks-meta-strip');
    if (strip) {
      strip.innerHTML = `
        <div class="ks-meta-item"><span class="ks-meta-label">Ключ</span><code>${esc(space.key)}</code></div>
        <div class="ks-meta-item"><span class="ks-meta-label">Тип</span><span class="ks-meta-value">${esc(space.space_type)}</span></div>
        <div class="ks-meta-item"><span class="ks-meta-label">Статус</span><span class="ks-status ${statusClass(space.status)}">${esc(statusLabel(space.status))}</span></div>
        <div class="ks-meta-item"><span class="ks-meta-label">Классификация</span><span class="ks-meta-value">${esc(space.classification)}</span></div>
        <div class="ks-meta-item"><span class="ks-meta-label">Владелец</span><span class="ks-meta-value">${esc(space.owner_team)}</span></div>
        <div class="ks-meta-item"><span class="ks-meta-label">Запусков за 30 дн.</span><span class="ks-meta-value">${esc(space.usage_30d)}</span></div>`;
    }

    const meta = $('#ks-meta');
    if (meta) {
      meta.innerHTML = `
        <dt>Ключ</dt><dd><code>${esc(space.key)}</code></dd>
        <dt>Тип</dt><dd>${esc(space.space_type)}</dd>
        <dt>Статус</dt><dd>${esc(statusLabel(space.status))}</dd>
        <dt>Классификация</dt><dd>${esc(space.classification)}</dd>
        <dt>Владелец</dt><dd>${esc(space.owner_team)}</dd>
        <dt>Свежесть</dt><dd>${esc(space.freshness_hours)} ч</dd>`;
    }

    const health = $('#ks-health-box');
    if (health) {
      const pct = detail.health_pct != null ? detail.health_pct : '—';
      const sourceCount = (detail.sources || []).length;
      health.innerHTML = `
        <div class="ks-health-row"><span>Общее состояние</span><span class="ks-meta-value ks-ok">${esc(pct)}%</span></div>
        <div class="ks-health-row"><span>Успех поиска</span><span class="ks-meta-value">${esc(space.search_success_pct)}%</span></div>
        <div class="ks-health-row"><span>Свежесть данных</span><span class="ks-meta-value">${esc(space.freshness_hours)} ч</span></div>
        <div class="ks-health-row"><span>Запусков за 30 дней</span><span class="ks-meta-value">${esc(space.usage_30d)}</span></div>
        <div class="ks-health-row"><span>Источников</span><span class="ks-meta-value">${esc(sourceCount)}</span></div>`;
    }

    const list = $('#ks-source-list');
    if (list) {
      const sources = detail.sources || [];
      list.innerHTML = sources.length
        ? sources.map((s) => {
          const selector = formatSelector(s.selector);
          const provider = s.provider || s.mcp_server || '—';
          return `
          <div class="ks-source" data-source-id="${esc(s.id)}">
            <div class="ks-source-icon">${esc((provider || 'D')[0].toUpperCase())}</div>
            <div class="ks-source-main">
              <span class="ks-source-name">${esc(s.name)}</span>
              <small>${esc(provider)}${selector ? ` · ${esc(selector)}` : ''}</small>
              <small>Приоритет ${esc(s.priority)} · здоровье ${esc(s.health_pct)}%</small>
            </div>
            <div class="ks-source-side">
              <span class="ks-status ${statusClass(s.status)}">${esc(statusLabel(s.status))}</span>
              <div class="ks-source-actions">
                <button type="button" class="ks-btn ghost small" data-action="edit">Изменить</button>
                <button type="button" class="ks-btn danger small" data-action="delete">Удалить</button>
              </div>
            </div>
          </div>`;
        }).join('')
        : '<p style="color:var(--ks-muted);margin:0">Нет подключённых источников</p>';

      list.querySelectorAll('[data-action="edit"]').forEach((btn) => {
        btn.onclick = () => {
          const row = btn.closest('.ks-source');
          openSourceModal(row && row.dataset.sourceId);
        };
      });
      list.querySelectorAll('[data-action="delete"]').forEach((btn) => {
        btn.onclick = () => {
          const row = btn.closest('.ks-source');
          if (row) deleteSource(row.dataset.sourceId).catch((e) => toast(e.message));
        };
      });
    }

    const searchPolicy = $('#ks-search-policy');
    if (searchPolicy) {
      searchPolicy.innerHTML = policyRows(space.search_policy, 'Политика поиска не задана');
    }

    const accessPolicy = $('#ks-access-policy');
    if (accessPolicy) {
      accessPolicy.innerHTML = policyRows(space.access_policy, 'Политика доступа не задана');
    }

    const areas = $('#ks-project-areas');
    const teams = $('#ks-team-names');
    const extra = $('#ks-additional-context');
    if (areas) areas.value = (space.project_areas || []).join(', ');
    if (teams) teams.value = (space.team_names || []).join(', ');
    if (extra) extra.value = space.additional_context || '';

    fillPlaySelect();

    const status = String(space.status || '').toUpperCase();
    const activateBtn = $('#ks-btn-activate');
    if (activateBtn) {
      show(activateBtn, ['DRAFT', 'DISABLED', 'DEGRADED'].includes(status));
    }
    const disableBtn = $('#ks-btn-disable');
    if (disableBtn) {
      show(disableBtn, ['ACTIVE', 'DEGRADED'].includes(status));
    }

    const menuHost = $('#ks-detail-menu');
    if (menuHost && space.id) {
      menuHost.innerHTML = catalogMenu(space.id, spaceMenuActions(space));
      bindCardMenus(menuHost);
    }
  }

  function spaceLabel(spaceId) {
    const item = state.items.find((x) => String(x.id) === String(spaceId));
    return (item && item.name)
      || (state.detail && state.detail.space && String(state.detail.space.id) === String(spaceId) && state.detail.space.name)
      || spaceId;
  }

  async function applyStatusChange(spaceId, path, confirmText, successToast) {
    if (!spaceId) {
      toast('Область знаний не выбрана');
      return;
    }
    if (!window.confirm(confirmText.replace('{label}', spaceLabel(spaceId)))) return;
    const detail = await fetchJSON(path, { method: 'POST' });
    await loadCatalog();
    if (state.detail && state.detail.space && String(state.detail.space.id) === String(spaceId)) {
      state.detail = detail;
      renderDetail();
    }
    toast(successToast);
  }

  async function activateSpace(id) {
    const spaceId = id
      || (state.detail && state.detail.space && state.detail.space.id);
    await applyStatusChange(
      spaceId,
      `/knowledge-spaces/${spaceId}/activate`,
      'Активировать область знаний «{label}»?',
      'Область знаний активирована',
    );
  }

  async function disableSpace(id) {
    const spaceId = id
      || (state.detail && state.detail.space && state.detail.space.id);
    await applyStatusChange(
      spaceId,
      `/knowledge-spaces/${spaceId}/disable`,
      'Отключить область знаний «{label}»?',
      'Область знаний отключена',
    );
  }

  async function saveContext() {
    const detail = state.detail;
    if (!detail || !detail.space) return;
    const split = (v) => String(v || '').split(',').map((x) => x.trim()).filter(Boolean);
    const body = {
      description: detail.space.purpose || '',
      project_areas: split(($('#ks-project-areas') || {}).value),
      team_names: split(($('#ks-team-names') || {}).value),
      additional_context: (($('#ks-additional-context') || {}).value || '').trim(),
    };
    state.detail = await fetchJSON(`/knowledge-spaces/${detail.space.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    renderDetail();
    toast('Контекст сохранён');
  }

  function openModal() {
    mountCreateFormFields();
    state.modalMode = 'create';
    state.editingId = null;
    const title = $('#ks-modal-title');
    const saveBtn = $('#ks-save-space');
    if (title) title.textContent = 'Новая область знаний';
    if (saveBtn) saveBtn.textContent = 'Создать черновик';
    resetCreateForm();
    show($('#ks-modal'), true);
  }

  async function openEditModal(id) {
    mountCreateFormFields();
    const detail = (state.detail && state.detail.space && String(state.detail.space.id) === String(id))
      ? state.detail
      : await fetchJSON(`/knowledge-spaces/${id}`);
    const space = detail.space || {};
    state.modalMode = 'edit';
    state.editingId = space.id || id;
    state.detail = detail;
    const title = $('#ks-modal-title');
    const saveBtn = $('#ks-save-space');
    const name = $('#ks-new-name');
    const key = $('#ks-new-key');
    const type = $('#ks-new-type');
    const classification = $('#ks-new-class');
    const purpose = $('#ks-new-purpose');
    if (title) title.textContent = 'Редактировать область знаний';
    if (saveBtn) saveBtn.textContent = 'Сохранить';
    if (name) name.value = space.name || '';
    if (key) {
      key.value = space.key || '';
      key.disabled = true;
      key.title = 'Ключ нельзя изменить';
    }
    if (type) type.value = space.space_type || 'DOMAIN';
    if (classification) classification.value = space.classification || 'INTERNAL';
    if (purpose) purpose.value = space.purpose || '';
    show($('#ks-modal'), true);
  }

  function closeModal() {
    show($('#ks-modal'), false);
    state.modalMode = 'create';
    state.editingId = null;
    if (window.HelpUI && HelpUI.hidePopover) HelpUI.hidePopover();
    if (window.HelpUI && HelpUI.hideTooltip) HelpUI.hideTooltip();
    const key = $('#ks-new-key');
    if (key) {
      key.disabled = false;
      key.title = '';
    }
  }
  function openInfo() { show($('#ks-info'), true); }
  function closeInfo() { show($('#ks-info'), false); }
  function openPlay() {
    fillPlaySelect();
    show($('#ks-play'), true);
  }
  function closePlay() { show($('#ks-play'), false); }

  function updateSourceHint() {
    const provider = (($('#ks-source-provider') || {}).value || 'other');
    const hint = $('#ks-source-selector-hint');
    if (hint) hint.textContent = PROVIDER_HINTS[provider] || PROVIDER_HINTS.other;
  }

  function openSourceModal(sourceId) {
    state.editingSourceId = sourceId || null;
    const title = $('#ks-source-modal-title');
    const idField = $('#ks-source-edit-id');
    const name = $('#ks-source-name');
    const provider = $('#ks-source-provider');
    const status = $('#ks-source-status');
    const priority = $('#ks-source-priority');
    const selector = $('#ks-source-selector');

    const existing = (state.detail && state.detail.sources || [])
      .find((s) => String(s.id) === String(sourceId));

    if (title) title.textContent = existing ? 'Изменить источник' : 'Добавить источник';
    if (idField) idField.value = existing ? String(existing.id) : '';
    if (name) name.value = existing ? (existing.name || '') : '';
    if (provider) provider.value = existing ? (existing.provider || 'other') : 'jira';
    if (status) status.value = existing ? (existing.status || 'ACTIVE') : 'ACTIVE';
    if (priority) priority.value = existing ? String(existing.priority ?? 50) : '50';
    if (selector) selector.value = existing ? selectorToText(existing.selector) : '';
    updateSourceHint();
    show($('#ks-source-modal'), true);
  }

  function closeSourceModal() {
    state.editingSourceId = null;
    show($('#ks-source-modal'), false);
  }

  async function saveSource() {
    const detail = state.detail;
    if (!detail || !detail.space) return;
    const name = (($('#ks-source-name') || {}).value || '').trim();
    if (!name) {
      toast('Укажите название источника');
      return;
    }
    const priorityRaw = (($('#ks-source-priority') || {}).value || '50');
    const priority = Math.max(0, Math.min(100, Number(priorityRaw) || 50));
    const body = {
      name,
      provider: (($('#ks-source-provider') || {}).value || 'other'),
      status: (($('#ks-source-status') || {}).value || 'ACTIVE'),
      priority,
      selector: parseSelectorText((($('#ks-source-selector') || {}).value || '')),
    };
    const sourceId = state.editingSourceId || (($('#ks-source-edit-id') || {}).value || '');
    const path = sourceId
      ? `/knowledge-spaces/${detail.space.id}/sources/${sourceId}`
      : `/knowledge-spaces/${detail.space.id}/sources`;
    state.detail = await fetchJSON(path, {
      method: sourceId ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    closeSourceModal();
    renderDetail();
    loadCatalog().catch(() => {});
    toast(sourceId ? 'Источник обновлён' : 'Источник добавлен');
  }

  async function deleteSource(sourceId) {
    const detail = state.detail;
    if (!detail || !detail.space || !sourceId) return;
    const src = (detail.sources || []).find((s) => String(s.id) === String(sourceId));
    const label = src ? src.name : 'источник';
    if (!window.confirm(`Удалить «${label}»?`)) return;
    state.detail = await fetchJSON(`/knowledge-spaces/${detail.space.id}/sources/${sourceId}`, {
      method: 'DELETE',
    });
    renderDetail();
    loadCatalog().catch(() => {});
    toast('Источник удалён');
  }

  async function createSpace() {
    const name = ($('#ks-new-name') || {}).value || '';
    const key = ($('#ks-new-key') || {}).value || '';
    const type = ($('#ks-new-type') || {}).value || 'DOMAIN';
    const classification = ($('#ks-new-class') || {}).value || 'INTERNAL';
    const purpose = ($('#ks-new-purpose') || {}).value || '';
    if (!name.trim()) {
      toast('Укажите название');
      return;
    }
    if (state.modalMode === 'edit' && state.editingId) {
      const detail = await fetchJSON(`/knowledge-spaces/${state.editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          type,
          classification,
          purpose,
        }),
      });
      closeModal();
      await loadCatalog();
      state.detail = detail;
      show($('#ks-catalog-view'), false);
      show($('#ks-detail-view'), true);
      renderDetail();
      toast('Область знаний обновлена');
      return;
    }
    const detail = await fetchJSON('/knowledge-spaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        key: key.trim() || undefined,
        type,
        classification,
        purpose,
      }),
    });
    closeModal();
    await loadCatalog();
    state.detail = detail;
    show($('#ks-catalog-view'), false);
    show($('#ks-detail-view'), true);
    renderDetail();
    toast('Черновик области знаний создан');
  }

  async function deleteSpace(id) {
    const item = state.items.find((x) => String(x.id) === String(id));
    const label = (item && item.name)
      || (state.detail && state.detail.space && String(state.detail.space.id) === String(id) && state.detail.space.name)
      || id;
    if (!window.confirm(`Удалить область знаний «${label}»?`)) return;
    await fetchJSON(`/knowledge-spaces/${id}`, { method: 'DELETE' });
    if (state.detail && state.detail.space && String(state.detail.space.id) === String(id)) {
      backToCatalog();
      return;
    }
    await loadCatalog();
    toast('Область знаний удалена');
  }

  async function runSearch() {
    const spaceId = ($('#ks-play-space') || {}).value || (state.items[0] && state.items[0].id);
    if (!spaceId) {
      toast('Нет области знаний');
      return;
    }
    const query = ($('#ks-play-query') || {}).value || '';
    const need = ($('#ks-play-need') || {}).value || 'Architecture context';
    const result = await fetchJSON(`/knowledge-spaces/${spaceId}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, information_need: need }),
    });
    $('#ks-sum-sources').textContent = String(result.sources_considered || 0);
    $('#ks-sum-raw').textContent = String(result.raw_results || 0);
    $('#ks-sum-evidence').textContent = String(result.evidence_count || 0);
    $('#ks-sum-excluded').textContent = String(result.excluded || 0);
    const box = $('#ks-results');
    if (box) {
      box.innerHTML = (result.evidence || []).map((r) => `
        <article class="ks-result">
          <div class="ks-result-head"><b>${esc(r.title)}</b><span class="ks-score">${esc(r.score)}</span></div>
          <p>${esc(r.snippet)}</p>
          <footer><span>${esc(r.source)}</span><span>Свежесть: ${esc(r.freshness)}</span><span>${esc(r.classification)}</span></footer>
        </article>`).join('') || '<p class="empty" style="color:var(--ks-muted)">Нет evidence</p>';
    }
  }

  function bindUI() {
    mountCreateFormFields();
    const search = $('#ks-search');
    const type = $('#ks-type-filter');
    const status = $('#ks-status-filter');
    if (search) search.oninput = () => { state.filters.search = search.value; loadCatalog().catch((e) => toast(e.message)); };
    if (type) type.onchange = () => { state.filters.type = type.value; loadCatalog().catch((e) => toast(e.message)); };
    if (status) status.onchange = () => { state.filters.status = status.value; loadCatalog().catch((e) => toast(e.message)); };

    [
      ['#ks-btn-create', openModal],
      ['#ks-btn-explain', openInfo],
      ['#ks-btn-playground', openPlay],
      ['#ks-btn-playground-detail', openPlay],
      ['#ks-btn-activate', () => activateSpace().catch((e) => toast(e.message))],
      ['#ks-btn-disable', () => disableSpace().catch((e) => toast(e.message))],
      ['#ks-btn-back', backToCatalog],
      ['#ks-close-modal', closeModal],
      ['#ks-cancel-modal', closeModal],
      ['#ks-save-space', () => createSpace().catch((e) => toast(e.message))],
      ['#ks-close-info', closeInfo],
      ['#ks-close-play', closePlay],
      ['#ks-run-search', () => runSearch().catch((e) => toast(e.message))],
      ['#ks-add-source', () => openSourceModal()],
      ['#ks-close-source-modal', closeSourceModal],
      ['#ks-cancel-source-modal', closeSourceModal],
      ['#ks-save-source', () => saveSource().catch((e) => toast(e.message))],
      ['#ks-save-context', () => saveContext().catch((e) => toast(e.message))],
    ].forEach(([sel, fn]) => {
      const el = $(sel);
      if (el) el.onclick = fn;
    });

    const provider = $('#ks-source-provider');
    if (provider) provider.onchange = updateSourceHint;
  }

  async function load(openId) {
    if (!root()) return;
    show($('#ks-detail-view'), false);
    show($('#ks-catalog-view'), true);
    show($('#ks-modal'), false);
    show($('#ks-source-modal'), false);
    show($('#ks-play'), false);
    show($('#ks-info'), false);
    bindUI();
    await loadCatalog();
    if (openId) {
      const byKey = state.items.find((i) => i.key === openId || String(i.id) === String(openId));
      await openDetail(byKey ? byKey.id : openId);
    }
  }

  window.KnowledgeModule = { load, openDetail, backToCatalog };
})();
