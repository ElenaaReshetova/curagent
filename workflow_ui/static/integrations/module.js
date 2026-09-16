/**
 * Integrations — MCP / A2A / ACP connections from backend.
 * Card view + standard config.json (mcpServers) editor.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const state = {
    connections: [],
    metrics: null,
    config: null,
    detail: null,
    view: 'cards',
    jsonScope: 'all',
    filters: { search: '', protocol: '', status: '' },
    bound: false,
    wizardMode: 'create',
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
      toast('Подключение не выбрано');
      return;
    }
    if (action === 'edit') {
      if (!state.detail || String(state.detail.connection?.id) !== String(id)) {
        await openDetail(id);
      }
      openWizardForEdit();
      return;
    }
    if (action === 'delete') {
      await deleteConnection(id);
    }
  }

  function root() { return document.getElementById('integrations-module'); }
  function $(sel) { return root() ? root().querySelector(sel) : null; }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('in-hidden', !visible);
  }

  function showCatalog() {
    show($('#in-catalog-view'), true);
    show($('#in-detail-view'), false);
    show($('#in-wizard-view'), false);
  }

  function showDetailPane() {
    show($('#in-catalog-view'), false);
    show($('#in-wizard-view'), false);
    show($('#in-detail-view'), true);
  }

  function showWizardPane() {
    show($('#in-catalog-view'), false);
    show($('#in-detail-view'), false);
    show($('#in-wizard-view'), true);
  }

  function statusLabel(s) {
    const map = {
      ready: 'Готов',
      misconfigured: 'Не настроен',
      disabled: 'Выкл',
      unknown: '—',
    };
    return map[s] || s || '—';
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    Object.entries(state.filters).forEach(([k, v]) => { if (v) q.set(k, v); });
    const data = await fetchJSON(`/integrations?${q.toString()}`);
    state.connections = data.connections || [];
    state.metrics = data.metrics || null;
    state.config = data.config || null;
    renderMetrics();
    renderGrid();
    if (state.view === 'json') renderJsonEditor();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#in-metric-total': m.total,
      '#in-metric-mcp': m.mcp,
      '#in-metric-a2a': m.a2a,
      '#in-metric-acp': m.acp,
      '#in-metric-total-sub': `${m.ready || 0} готовы · ${m.misconfigured || 0} требуют настройки`,
      '#in-metric-mcp-sub': 'stdio / SSE / HTTP',
      '#in-metric-a2a-sub': 'agent ↔ agent',
      '#in-metric-acp-sub': 'agent servers',
    };
    Object.entries(map).forEach(([sel, value]) => {
      const el = $(sel);
      if (el) el.textContent = value == null ? '—' : String(value);
    });
  }

  function renderGrid() {
    const grid = $('#in-grid');
    if (!grid) return;
    if (!state.connections.length) {
      grid.innerHTML = '<div class="in-empty">Нет подключений MCP / A2A / ACP по выбранным фильтрам.</div>';
      return;
    }
    grid.innerHTML = state.connections.map((x) => {
      const tools = (x.tools || []).slice(0, 4).map((t) => `<span class="in-badge">${esc(t)}</span>`).join('');
      return `<article class="in-card" data-id="${esc(x.id)}" tabindex="0" role="button">
        <div class="card-head-row">
          <div class="in-card-head">
            <div class="in-icon in-proto-${esc(String(x.protocol || '').toLowerCase())}">${esc((x.protocol || '?')[0])}</div>
            <span class="in-health ${esc(String(x.status || '').toLowerCase())}">${esc(statusLabel(x.status))}</span>
          </div>
          ${catalogMenu(x.id)}
        </div>
        <h3>${esc(x.name)}</h3>
        <p>${esc(x.description || '')}</p>
        <div class="in-badges">
          <span class="in-badge">${esc(x.protocol)}</span>
          <span class="in-badge">${esc(x.transport || '—')}</span>
          <span class="in-badge">${esc(x.key)}</span>
        </div>
        <div class="in-badges">${tools || '<span class="in-badge">—</span>'}</div>
      </article>`;
    }).join('');
    bindCardMenus(grid);
    grid.querySelectorAll('.in-card').forEach((card) => {
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

  function scopedDocument() {
    const full = state.config || {};
    if (state.jsonScope === 'mcp') return { mcpServers: full.mcpServers || {} };
    if (state.jsonScope === 'a2a') return { servers: full.servers || {} };
    if (state.jsonScope === 'acp') return { agent_servers: full.agent_servers || {} };
    return {
      mcpServers: full.mcpServers || {},
      servers: full.servers || {},
      agent_servers: full.agent_servers || {},
    };
  }

  function renderJsonEditor() {
    const editor = $('#in-json-editor');
    if (!editor) return;
    editor.value = JSON.stringify(scopedDocument(), null, 2);
    const err = $('#in-json-error');
    if (err) {
      err.textContent = '';
      err.classList.add('in-hidden');
    }
  }

  function setView(view) {
    state.view = view;
    const cardsBtn = $('#in-view-cards');
    const jsonBtn = $('#in-view-json');
    if (cardsBtn) cardsBtn.classList.toggle('active', view === 'cards');
    if (jsonBtn) jsonBtn.classList.toggle('active', view === 'json');
    show($('#in-grid'), view === 'cards');
    show($('#in-cards-toolbar'), view === 'cards');
    show($('#in-json-panel'), view === 'json');
    if (view === 'json') renderJsonEditor();
  }

  async function openDetail(id) {
    state.detail = await fetchJSON(`/integrations/${encodeURIComponent(id)}`);
    renderDetail();
    showDetailPane();
  }

  function closeDetail() {
    state.detail = null;
    showCatalog();
  }

  function renderDetail() {
    const conn = (state.detail && state.detail.connection) || {};
    const doc = (state.detail && state.detail.config_document) || {};
    const caps = (state.detail && state.detail.linked_capabilities) || [];
    $('#in-detail-protocol').textContent = conn.protocol || 'ПОДКЛЮЧЕНИЕ';
    $('#in-detail-title').textContent = conn.name || '—';
    $('#in-detail-description').textContent = conn.description || '—';
    $('#in-detail-meta').innerHTML = `
      <dt>Ключ</dt><dd>${esc(conn.key)}</dd>
      <dt>Протокол</dt><dd>${esc(conn.protocol)}</dd>
      <dt>Транспорт</dt><dd>${esc(conn.transport || '—')}</dd>
      <dt>Статус</dt><dd>${esc(statusLabel(conn.status))}</dd>
      <dt>Включено</dt><dd>${conn.enabled ? 'да' : 'нет'}</dd>`;
    $('#in-detail-health').innerHTML = `
      <div class="in-health-row"><span>Состояние</span><b class="${conn.status === 'ready' ? 'in-ok' : ''}">${esc(statusLabel(conn.status))}</b></div>
      <div class="in-health-row"><span>Протокол</span><b>${esc(conn.protocol)}</b></div>
      <div class="in-health-row"><span>Инструментов</span><b>${esc((conn.tools || []).length)}</b></div>`;
    $('#in-detail-config').textContent = JSON.stringify(doc, null, 2);
    const tools = (conn.tools || []).map((t) => `<span>${esc(t)}</span>`).join('');
    const capLinks = caps.map((c) => {
      const key = c.capability_id || c.key || '';
      if (window.PlatformUtil && window.PlatformUtil.entityLink) {
        return window.PlatformUtil.entityLink('capabilities-platform', key, { id: key, key });
      }
      return `<span>${esc(key)}</span>`;
    }).join('');
    $('#in-capabilities').innerHTML = tools || capLinks || '<span>Нет привязанных инструментов</span>';
    if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
      window.PlatformUtil.bindEntityLinks($('#in-capabilities'));
    }

    const menuHost = $('#in-detail-menu');
    if (menuHost && conn.id) {
      menuHost.innerHTML = catalogMenu(conn.id);
      bindCardMenus(menuHost);
    }
  }

  function openWizard() {
    state.wizardMode = 'create';
    const keyEl = $('#in-wizard-key');
    if (keyEl) {
      keyEl.disabled = false;
      keyEl.title = '';
    }
    updateWizardFields();
    updateWizardPreview();
    showWizardPane();
  }

  function openWizardForEdit() {
    const conn = (state.detail && state.detail.connection) || {};
    const doc = (state.detail && state.detail.config_document) || {};
    state.wizardMode = 'edit';
    const keyEl = $('#in-wizard-key');
    if (keyEl) {
      keyEl.disabled = true;
      keyEl.title = 'Ключ нельзя изменить';
    }
    const protocol = conn.protocol || 'MCP';
    setVal('#in-wizard-protocol', protocol);
    setVal('#in-wizard-key', conn.key || '');
    setVal('#in-wizard-name', conn.name || '');
    setVal('#in-wizard-description', conn.description || '');
    if (protocol === 'MCP') {
      const entry = doc.mcpServers && doc.mcpServers[conn.key];
      const transport = entry && entry.url ? 'url' : 'stdio';
      setVal('#in-wizard-transport', transport);
      if (entry) {
        if (transport === 'url') setVal('#in-wizard-url', entry.url || '');
        else {
          setVal('#in-wizard-command', entry.command || '');
          setVal('#in-wizard-args', (entry.args || []).join(' '));
        }
      }
    } else if (protocol === 'A2A') {
      const servers = doc.servers || {};
      setVal('#in-wizard-a2a-url', servers[conn.key] || '');
    } else {
      const agents = doc.agent_servers || {};
      const entry = agents[conn.key] || {};
      setVal('#in-wizard-acp-command', entry.command || '');
      setVal('#in-wizard-acp-args', (entry.args || []).join(' '));
    }
    updateWizardFields();
    updateWizardPreview();
    showWizardPane();
  }

  function setVal(sel, value) {
    const el = $(sel);
    if (el) el.value = value == null ? '' : String(value);
  }
  function closeWizard() { showCatalog(); }

  function updateWizardFields() {
    const protocol = ($('#in-wizard-protocol') || {}).value || 'MCP';
    show($('#in-wizard-mcp-fields'), protocol === 'MCP');
    show($('#in-wizard-a2a-fields'), protocol === 'A2A');
    show($('#in-wizard-acp-fields'), protocol === 'ACP');
    if (protocol === 'MCP') {
      const transport = ($('#in-wizard-transport') || {}).value || 'stdio';
      show($('#in-wizard-stdio-row'), transport === 'stdio');
      show($('#in-wizard-url-row'), transport === 'url');
    }
  }

  function splitArgs(raw) {
    return String(raw || '').trim().split(/\s+/).filter(Boolean);
  }

  function wizardPayloadPreview() {
    const protocol = ($('#in-wizard-protocol') || {}).value || 'MCP';
    const key = ($('#in-wizard-key') || {}).value || 'server';
    if (protocol === 'MCP') {
      const transport = ($('#in-wizard-transport') || {}).value || 'stdio';
      const entry = transport === 'url'
        ? { url: ($('#in-wizard-url') || {}).value || '' }
        : {
          command: ($('#in-wizard-command') || {}).value || '',
          args: splitArgs(($('#in-wizard-args') || {}).value),
        };
      if (!entry.args || !entry.args.length) delete entry.args;
      return { mcpServers: { [key]: entry } };
    }
    if (protocol === 'A2A') {
      return { servers: { [key]: ($('#in-wizard-a2a-url') || {}).value || '' } };
    }
    const entry = {
      command: ($('#in-wizard-acp-command') || {}).value || '',
      args: splitArgs(($('#in-wizard-acp-args') || {}).value),
    };
    if (!entry.args.length) delete entry.args;
    return { agent_servers: { [key]: entry } };
  }

  function updateWizardPreview() {
    const preview = $('#in-wizard-preview');
    if (preview) preview.textContent = JSON.stringify(wizardPayloadPreview(), null, 2);
  }

  async function saveWizard() {
    const protocol = ($('#in-wizard-protocol') || {}).value || 'MCP';
    const key = (($('#in-wizard-key') || {}).value || '').trim();
    if (!key) {
      toast('Укажите ключ подключения');
      return;
    }
    const body = {
      protocol,
      key,
      name: ($('#in-wizard-name') || {}).value || key,
      description: ($('#in-wizard-description') || {}).value || '',
    };
    if (protocol === 'MCP') {
      const transport = ($('#in-wizard-transport') || {}).value || 'stdio';
      body.config = transport === 'url'
        ? { url: ($('#in-wizard-url') || {}).value || '' }
        : {
          command: ($('#in-wizard-command') || {}).value || '',
          args: splitArgs(($('#in-wizard-args') || {}).value),
        };
      if (body.config.args && !body.config.args.length) delete body.config.args;
    } else if (protocol === 'A2A') {
      body.url = ($('#in-wizard-a2a-url') || {}).value || '';
    } else {
      body.config = {
        command: ($('#in-wizard-acp-command') || {}).value || '',
        args: splitArgs(($('#in-wizard-acp-args') || {}).value),
      };
      if (!body.config.args.length) delete body.config.args;
    }
    const conn = (state.detail && state.detail.connection) || {};
    const editId = state.wizardMode === 'edit' && conn.id ? conn.id : null;
    state.detail = await fetchJSON(editId ? `/integrations/${encodeURIComponent(editId)}` : '/integrations', {
      method: editId ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    closeWizard();
    await loadCatalog();
    renderDetail();
    showDetailPane();
    toast(editId ? 'Подключение обновлено' : 'Подключение сохранено');
  }

  async function deleteConnection(id) {
    const item = state.connections.find((x) => String(x.id) === String(id));
    const label = (item && item.name)
      || (state.detail && state.detail.connection && String(state.detail.connection.id) === String(id) && state.detail.connection.name)
      || id;
    if (!window.confirm(`Удалить подключение «${label}»?`)) return;
    await fetchJSON(`/integrations/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (state.detail && state.detail.connection && String(state.detail.connection.id) === String(id)) {
      closeDetail();
    }
    state.detail = null;
    await loadCatalog();
    toast('Подключение удалено');
  }

  async function saveJson() {
    const editor = $('#in-json-editor');
    const err = $('#in-json-error');
    if (!editor) return;
    let parsed;
    try {
      parsed = JSON.parse(editor.value);
    } catch (e) {
      if (err) {
        err.textContent = `Невалидный JSON: ${e.message}`;
        err.classList.remove('in-hidden');
      }
      toast('Исправьте JSON перед сохранением');
      return;
    }
    let document = parsed;
    if (state.jsonScope === 'mcp') {
      document = { ...(state.config || {}), mcpServers: parsed.mcpServers || parsed };
    } else if (state.jsonScope === 'a2a') {
      document = { ...(state.config || {}), servers: parsed.servers || parsed };
    } else if (state.jsonScope === 'acp') {
      document = { ...(state.config || {}), agent_servers: parsed.agent_servers || parsed };
    }
    const result = await fetchJSON('/integrations/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document }),
    });
    state.config = result.document || document;
    await loadCatalog();
    renderJsonEditor();
    toast('config.json сохранён');
  }

  async function copyJson() {
    const editor = $('#in-json-editor');
    if (!editor) return;
    try {
      await navigator.clipboard.writeText(editor.value);
      toast('Скопировано в буфер');
    } catch (_) {
      editor.select();
      toast('Выделите и скопируйте вручную');
    }
  }

  function bindUI() {
    if (state.bound) return;
    state.bound = true;

    ['#in-search', '#in-protocol', '#in-status'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      const key = sel.replace('#in-', '');
      el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
        state.filters[key] = el.value;
        loadCatalog().catch((e) => toast(e.message));
      });
    });

    const cardsBtn = $('#in-view-cards');
    const jsonBtn = $('#in-view-json');
    if (cardsBtn) cardsBtn.onclick = () => setView('cards');
    if (jsonBtn) jsonBtn.onclick = () => setView('json');

    const refresh = $('#in-refresh-btn');
    if (refresh) refresh.onclick = () => loadCatalog().catch((e) => toast(e.message));

    const createBtn = $('#in-create-btn');
    if (createBtn) createBtn.onclick = openWizard;

    const backBtn = $('#in-btn-back');
    if (backBtn) backBtn.onclick = closeDetail;

    const closeWizardBtn = $('#in-close-wizard');
    if (closeWizardBtn) closeWizardBtn.onclick = closeWizard;

    const saveWizardBtn = $('#in-wizard-save');
    if (saveWizardBtn) saveWizardBtn.onclick = () => saveWizard().catch((e) => toast(e.message));

    ['#in-wizard-protocol', '#in-wizard-transport', '#in-wizard-key', '#in-wizard-command',
      '#in-wizard-args', '#in-wizard-url', '#in-wizard-a2a-url', '#in-wizard-acp-command',
      '#in-wizard-acp-args'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      el.addEventListener('input', () => { updateWizardFields(); updateWizardPreview(); });
      el.addEventListener('change', () => { updateWizardFields(); updateWizardPreview(); });
    });

    const scope = $('#in-json-scope');
    if (scope) {
      scope.onchange = () => {
        state.jsonScope = scope.value;
        renderJsonEditor();
      };
    }
    const copyBtn = $('#in-json-copy');
    if (copyBtn) copyBtn.onclick = () => copyJson().catch((e) => toast(e.message));
    const saveJsonBtn = $('#in-json-save');
    if (saveJsonBtn) saveJsonBtn.onclick = () => saveJson().catch((e) => toast(e.message));
  }

  async function load(openId) {
    bindUI();
    setView(state.view);
    showCatalog();
    await loadCatalog();
    if (openId) await openDetail(openId);
  }

  window.IntegrationsModule = { load, openDetail };
})();
