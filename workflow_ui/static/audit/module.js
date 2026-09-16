/**
 * Audit — immutable control plane journal.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);

  const state = {
    items: [],
    filters: { search: '', entity_type: '', action: '' },
  };

  function root() { return document.getElementById('audit-module'); }
  function $(sel) { return root() ? root().querySelector(sel) : null; }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('ru-RU');
  }

  function isToday(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return false;
    const now = new Date();
    return date.toDateString() === now.toDateString();
  }

  function filteredItems() {
    const q = state.filters.search.toLowerCase();
    return state.items.filter((item) => {
      const blob = `${item.actor} ${item.action} ${item.entity_type} ${item.entity_id} ${item.summary}`.toLowerCase();
      if (q && !blob.includes(q)) return false;
      if (state.filters.entity_type && item.entity_type !== state.filters.entity_type) return false;
      if (state.filters.action && item.action !== state.filters.action) return false;
      return true;
    });
  }

  function renderMetrics() {
    const items = state.items;
    const today = items.filter((i) => isToday(i.occurred_at)).length;
    const actors = new Set(items.map((i) => i.actor)).size;
    const entities = new Set(items.map((i) => i.entity_type)).size;
    const map = {
      '#au-metric-total': items.length,
      '#au-metric-today': today,
      '#au-metric-actors': actors,
      '#au-metric-entities': entities,
    };
    Object.entries(map).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value;
    });
    const subs = {
      '#au-metric-total-sub': 'Записанные события',
      '#au-metric-today-sub': 'С полуночи',
      '#au-metric-actors-sub': 'Уникальные акторы',
      '#au-metric-entities-sub': 'Типы сущностей',
    };
    Object.entries(subs).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value;
    });
  }

  function populateFilters() {
    const entitySelect = $('#au-entity-type');
    const actionSelect = $('#au-action');
    if (entitySelect) {
      const current = entitySelect.value;
      const types = [...new Set(state.items.map((i) => i.entity_type).filter(Boolean))].sort();
      entitySelect.innerHTML = '<option value="">Все типы сущностей</option>' + types.map((t) =>
        `<option value="${esc(t)}">${esc(t)}</option>`).join('');
      entitySelect.value = current;
    }
    if (actionSelect) {
      const current = actionSelect.value;
      const actions = [...new Set(state.items.map((i) => i.action).filter(Boolean))].sort();
      actionSelect.innerHTML = '<option value="">Все действия</option>' + actions.map((a) =>
        `<option value="${esc(a)}">${esc(a)}</option>`).join('');
      actionSelect.value = current;
    }
  }

  function entityViewForType(entityType) {
    const t = String(entityType || '').toLowerCase();
    if (t.includes('flow')) return 'flows';
    if (t.includes('playbook') || t.includes('graph')) return 'flows';
    if (t.includes('skill')) return 'skills';
    if (t.includes('rule')) return 'rules';
    if (t.includes('knowledge')) return 'knowledge';
    if (t.includes('capacit')) return 'capabilities-platform';
    if (t.includes('integration') || t.includes('mcp')) return 'integrations';
    if (t.includes('control')) return 'controls';
    if (t.includes('execution')) return 'inspector';
    if (t.includes('checkpoint')) return 'checkpoints';
    return null;
  }

  function renderTable() {
    const body = $('#au-table-body');
    if (!body) return;
    const items = filteredItems();
    body.innerHTML = items.length ? items.map((item) => {
      const view = entityViewForType(item.entity_type);
      const entityCell = view && item.entity_id && window.PlatformUtil && window.PlatformUtil.entityLink
        ? `${esc(item.entity_type)}<div>${window.PlatformUtil.entityLink(view, item.entity_id, { id: item.entity_id })}</div>`
        : `<div>${esc(item.entity_type)}</div>${item.entity_id ? `<div class="au-entity">${esc(item.entity_id)}</div>` : ''}`;
      return `
      <tr>
        <td class="au-time">${esc(formatDate(item.occurred_at))}</td>
        <td class="au-actor">${esc(item.actor)}</td>
        <td><span class="au-action">${esc(item.action)}</span></td>
        <td>${entityCell}</td>
        <td>${esc(item.summary || '—')}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="5" class="au-empty">Нет событий аудита по выбранным фильтрам.</td></tr>';
    if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
      window.PlatformUtil.bindEntityLinks(body);
    }
  }

  async function loadCatalog() {
    const data = await fetchJSON('/audit?limit=200');
    state.items = data.audit || [];
    populateFilters();
    renderMetrics();
    renderTable();
  }

  function bindUI() {
    ['#au-search', '#au-entity-type', '#au-action'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      const key = sel === '#au-search' ? 'search' : sel.replace('#au-', '').replace('-type', '_type');
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
        state.filters[key] = el.value;
        renderTable();
      });
    });
    const refreshBtn = $('#au-refresh-btn');
    if (refreshBtn) {
      refreshBtn.onclick = () => loadCatalog().catch((e) => toast(e.message));
    }
  }

  async function load() {
    bindUI();
    await loadCatalog();
  }

  window.AuditModule = { load };
})();
