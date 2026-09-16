/**
 * Capability Registry — catalog, detail drawer, CRUD.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const state = {
    items: [],
    manifests: {},
    detail: null,
    filters: { search: '', group: '', risk: '', status: '' },
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
      toast('Способность не выбрана');
      return;
    }
    if (action === 'edit') {
      await openDetail(id);
      return;
    }
    if (action === 'delete') {
      const item = state.items.find((i) => String(i.id) === String(id) || i.key === id);
      if (item) await deleteCapability(item);
    }
  }

  function root() { return document.getElementById('capabilities-platform-module'); }
  function $(sel) { return root() ? root().querySelector(sel) : null; }

  function showDrawer(visible) {
    const drawer = $('#cr-drawer');
    if (!drawer) return;
    drawer.classList.toggle('cr-hidden', !visible);
    drawer.classList.toggle('open', visible);
  }

  function filteredItems() {
    const q = state.filters.search.toLowerCase();
    return state.items.filter((item) => {
      const blob = `${item.key} ${item.name} ${item.group} ${item.operation}`.toLowerCase();
      if (q && !blob.includes(q)) return false;
      if (state.filters.group && item.group !== state.filters.group) return false;
      if (state.filters.risk && item.risk !== state.filters.risk) return false;
      if (state.filters.status && item.status !== state.filters.status) return false;
      return true;
    });
  }

  function renderMetrics() {
    const items = state.items;
    const active = items.filter((i) => i.status === 'active').length;
    const draft = items.filter((i) => i.status === 'draft').length;
    const highRisk = items.filter((i) => ['high', 'critical'].includes(i.risk)).length;
    const map = {
      '#cr-metric-total': items.length,
      '#cr-metric-active': active,
      '#cr-metric-draft': draft,
      '#cr-metric-high-risk': highRisk,
    };
    Object.entries(map).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value;
    });
    const subs = {
      '#cr-metric-total-sub': 'Зарегистрировано',
      '#cr-metric-active-sub': 'Доступны навыкам',
      '#cr-metric-draft-sub': 'Ожидают проверки',
      '#cr-metric-high-risk-sub': 'Требуют контролей',
    };
    Object.entries(subs).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value;
    });
  }

  function renderGrid() {
    const grid = $('#cr-grid');
    if (!grid) return;
    const items = filteredItems();
    grid.innerHTML = items.length ? items.map((item) => `
      <article class="cr-card" data-id="${esc(item.id)}" tabindex="0" role="button">
        <div class="card-head-row">
          <div class="cr-card-head">
            <span class="cr-badge">${esc(item.group)}</span>
            <span class="cr-status ${esc(item.status)}">${esc(item.status)}</span>
          </div>
          ${catalogMenu(item.id)}
        </div>
        <h3>${esc(item.key)}</h3>
        <p>${esc(item.name)}</p>
        <div class="cr-badges">
          <span class="cr-badge cr-risk ${esc(item.risk)}">риск: ${esc(item.risk)}</span>
          <span class="cr-badge">${esc(item.operation)}</span>
        </div>
      </article>
    `).join('') : '<div class="cr-panel">Нет способностей по выбранным фильтрам.</div>';
    bindCardMenus(grid);
    grid.querySelectorAll('.cr-card').forEach((card) => {
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

  function populateGroupFilter() {
    const select = $('#cr-group');
    if (!select) return;
    const groups = [...new Set(state.items.map((i) => i.group).filter(Boolean))].sort();
    const current = select.value;
    select.innerHTML = '<option value="">Все группы</option>' + groups.map((g) =>
      `<option value="${esc(g)}">${esc(g)}</option>`).join('');
    select.value = current;
  }

  function renderDetailForm(item, isNew) {
    const body = $('#cr-drawer-body');
    if (!body) return;
    const data = item || {
      key: '',
      name: '',
      group: 'platform',
      operation: 'read',
      risk: 'read',
      status: 'draft',
    };
    const manifest = state.manifests[data.key] || null;
    const implementations = (manifest && manifest.implementations) || data.implementations || [];
    const implHtml = implementations.length
      ? `<div class="cr-impl-list">${implementations.map((impl) => `
          <div class="cr-impl">
            <b>${esc(impl.id || impl.tool_name || 'implementation')}</b>
            <small>type: ${esc(impl.type || 'mcp')} · server: ${esc(impl.server_id || '—')} · tool: ${esc(impl.tool_name || '—')} · ${esc(impl.status || '')}</small>
            ${impl.server_id ? `<div style="margin-top:6px">${window.PlatformUtil && window.PlatformUtil.entityLink ? window.PlatformUtil.entityLink('integrations', `MCP ${impl.server_id}`, { id: impl.server_id, key: impl.server_id }) : esc(impl.server_id)}</div>` : ''}
          </div>`).join('')}</div>`
      : '<p style="color:var(--cr-muted);font-size:12px">Нет MCP-реализаций в манифестах способностей для этого ключа.</p>';
    body.innerHTML = `
      <div class="cr-panel">
        <h3>${isNew ? 'Новая способность' : 'Детали способности'}</h3>
        <form id="cr-form" class="cr-form">
          <label>Ключ способности<input id="cr-field-key" required value="${esc(data.key)}" ${isNew ? '' : 'readonly'}></label>
          <label>Название<input id="cr-field-name" required value="${esc(data.name)}"></label>
          <label>Группа<input id="cr-field-group" value="${esc(data.group)}"></label>
          <label>Операция<input id="cr-field-operation" value="${esc(data.operation)}"></label>
          <label>Риск
            <select id="cr-field-risk">
              ${['read', 'low', 'medium', 'high', 'critical'].map((r) =>
                `<option value="${r}" ${data.risk === r ? 'selected' : ''}>${r}</option>`).join('')}
            </select>
          </label>
          <label>Статус
            <select id="cr-field-status">
              ${['draft', 'active', 'disabled'].map((s) =>
                `<option value="${s}" ${data.status === s ? 'selected' : ''}>${s}</option>`).join('')}
            </select>
          </label>
          <div class="cr-form-actions">
            ${isNew ? '' : '<button type="button" class="cr-btn danger" id="cr-delete-btn">Удалить</button>'}
            <button type="button" class="cr-btn secondary" id="cr-cancel-btn">Отмена</button>
            <button type="submit" class="cr-btn">Сохранить</button>
          </div>
        </form>
      </div>
      ${isNew ? '' : `<div class="cr-panel"><h3>MCP-реализации</h3>${implHtml}</div>`}`;
    const form = $('#cr-form');
    if (form) {
      form.onsubmit = (event) => {
        event.preventDefault();
        saveCapability(data, isNew).catch((e) => toast(e.message));
      };
    }
    const del = $('#cr-delete-btn');
    if (del) del.onclick = () => deleteCapability(data).catch((e) => toast(e.message));
    const cancel = $('#cr-cancel-btn');
    if (cancel) cancel.onclick = closeDetail;
    if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
      window.PlatformUtil.bindEntityLinks(body);
    }
  }

  async function openDetail(id) {
    let item = state.items.find((i) => String(i.id) === String(id) || i.key === id);
    if (!item && id) {
      // Resolve by capability key from manifests when registry id differs
      item = state.items.find((i) => i.key === id) || { id, key: id, name: id, group: 'manifest', operation: 'read', risk: 'read', status: 'active' };
    }
    if (!item) return;
    state.detail = item;
    const title = $('#cr-detail-title');
    if (title) title.textContent = item.key;
    if (!state.manifests[item.key]) {
      try {
        const manifest = await fetchJSON(`/capability-manifests/${encodeURIComponent(item.key)}`);
        state.manifests[item.key] = manifest;
      } catch (_) { /* optional */ }
    }
    renderDetailForm(item, false);
    showDrawer(true);
  }

  function openCreate() {
    state.detail = null;
    const title = $('#cr-detail-title');
    if (title) title.textContent = 'Новая способность';
    renderDetailForm(null, true);
    showDrawer(true);
  }

  function closeDetail() {
    state.detail = null;
    showDrawer(false);
  }

  function collectForm() {
    return {
      key: ($('#cr-field-key') || {}).value || '',
      name: ($('#cr-field-name') || {}).value || '',
      group: ($('#cr-field-group') || {}).value || 'platform',
      operation: ($('#cr-field-operation') || {}).value || 'read',
      risk: ($('#cr-field-risk') || {}).value || 'read',
      status: ($('#cr-field-status') || {}).value || 'draft',
    };
  }

  async function saveCapability(existing, isNew) {
    const body = collectForm();
    if (isNew) {
      const saved = await fetchJSON('/capabilities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      state.items.push(saved);
      toast('Способность создана');
      await loadCatalog();
      await openDetail(saved.id);
      return;
    }
    const saved = await fetchJSON(`/capabilities/${encodeURIComponent(existing.id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...existing, ...body, id: existing.id }),
    });
    const idx = state.items.findIndex((i) => String(i.id) === String(existing.id));
    if (idx >= 0) state.items[idx] = saved;
    toast('Способность сохранена');
    renderMetrics();
    renderGrid();
    renderDetailForm(saved, false);
  }

  async function deleteCapability(item) {
    if (!confirm(`Удалить способность ${item.key}?`)) return;
    await fetchJSON(`/capabilities/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
    state.items = state.items.filter((i) => String(i.id) !== String(item.id));
    toast('Способность удалена');
    closeDetail();
    renderMetrics();
    renderGrid();
  }

  async function loadCatalog() {
    const [data, manifestsRes] = await Promise.all([
      fetchJSON('/capabilities'),
      fetchJSON('/capability-manifests').catch(() => ({ manifests: [] })),
    ]);
    state.items = data.capabilities || (Array.isArray(data) ? data : []);
    state.manifests = {};
    (manifestsRes.manifests || []).forEach((m) => {
      if (m.capability_id) state.manifests[m.capability_id] = m;
    });
    // Ensure manifest-only capabilities appear in catalog
    Object.keys(state.manifests).forEach((key) => {
      if (!state.items.some((i) => i.key === key)) {
        const m = state.manifests[key];
        state.items.push({
          id: key,
          key,
          name: m.name || key,
          group: m.group || 'manifest',
          operation: m.operation_type || 'read',
          risk: m.risk_level || 'read',
          status: m.status === 'published' ? 'active' : (m.status || 'active'),
        });
      }
    });
    populateGroupFilter();
    renderMetrics();
    renderGrid();
  }

  function bindUI() {
    ['#cr-search', '#cr-group', '#cr-risk', '#cr-status'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      const key = sel === '#cr-search' ? 'search' : sel.replace('#cr-', '');
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
        state.filters[key] = el.value;
        renderGrid();
      });
    });
    const createBtn = $('#cr-create-btn');
    const closeBtn = $('#cr-close-drawer');
    if (createBtn) createBtn.onclick = openCreate;
    if (closeBtn) closeBtn.onclick = closeDetail;
  }

  async function load(openId) {
    bindUI();
    await loadCatalog();
    if (openId) await openDetail(openId);
  }

  window.CapabilitiesPlatformModule = { load, openDetail };
})();
