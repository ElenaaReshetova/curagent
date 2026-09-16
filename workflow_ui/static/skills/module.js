/**
 * Навыки (skills) — каталог / карточка / редактор.
 * No Agents / MCP tool pickers. Uses /api/v1/skills*.
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
    interfaces: [],
    contracts: [],
    filters: { q: '', skillType: '', status: '' },
    interfaceFilters: { q: '', source: '' },
    contractFilters: { q: '', kind: '' },
    interfaceTab: 'interfaces',
    modalMode: 'create',
    interfaceModalMode: 'create',
    editingInterfaceId: null,
    activeFile: 'SKILL.md',
    selectedFolder: '',
    selectionKind: 'file',
    collapsed: {},
    addKind: null,
    editingId: null,
  };

  function catalogMenu(id, actions) {
    return CardMenu().markup(id, actions || CardMenu().defaultActions());
  }

  function skillMenuActions(item) {
    return [
      { id: 'edit', label: 'Редактировать' },
      { id: 'delete', label: 'Удалить', danger: true, hidden: !!item.immutable },
    ];
  }

  function bindCardMenus(scope) {
    CardMenu().bind(scope || root(), (id, action) => {
      handleCardAction(action, id).catch((e) => toast(e.message));
    });
  }

  async function handleCardAction(action, id) {
    if (!id) {
      toast('Навык не выбран');
      return;
    }
    if (action === 'edit') {
      const item = state.items.find((s) => String(s.id) === String(id));
      if (item && item.immutable) {
        toast('Corporate/Core навыки нельзя редактировать — наследуйте');
        return;
      }
      await openDetailAndEdit(id);
      return;
    }
    if (action === 'delete') {
      await deleteSkill(id);
    }
  }

  function root() {
    return document.getElementById('skills-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('sk-hidden', !visible);
  }

  function currentVersion(detail) {
    if (!detail) return null;
    return detail.published_version || detail.draft_version || detail.current_version;
  }

  function editableVersion(detail) {
    if (!detail) return null;
    if (detail.skill && detail.skill.immutable) return null;
    return detail.draft_version || null;
  }

  function isImmutable(detail) {
    return !!(detail && detail.skill && detail.skill.immutable);
  }

  function pillClass(status) {
    if (status === 'PUBLISHED') return 'green';
    if (status === 'DRAFT') return 'amber';
    return 'gray';
  }

  function typeLabel(type) {
    const map = {
      CORE: 'CORE · платформенный',
      CORPORATE: 'CORPORATE · корпоративный',
      TEAM: 'TEAM · командный',
      IMPORTED: 'IMPORTED · импорт',
    };
    return map[type] || type || 'TEAM';
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    if (state.filters.q) q.set('q', state.filters.q);
    if (state.filters.skillType) q.set('skillType', state.filters.skillType);
    if (state.filters.status) q.set('status', state.filters.status);
    const data = await fetchJSON(`/skills?${q.toString()}`);
    state.items = data.skills || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderCards();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#sk-metric-skills': m.skills,
      '#sk-metric-published': m.published_versions,
      '#sk-metric-interfaces': m.interfaces,
      '#sk-metric-validation': m.validation_pass_pct != null ? `${m.validation_pass_pct}%` : '—',
    };
    Object.entries(map).forEach(([sel, val]) => {
      const el = $(sel);
      if (el) el.textContent = val == null ? '—' : String(val);
    });
  }

  function renderCards() {
    const wrap = $('#sk-cards');
    if (!wrap) return;
    try { CardMenu().closeAll(); } catch (_) { /* ignore */ }
    if (!state.items.length) {
      wrap.innerHTML = '<p style="color:var(--sk-muted)">Навыки не найдены</p>';
      return;
    }
    wrap.innerHTML = state.items.map((s) => `
      <article class="sk-card${s.immutable ? ' immutable' : ''}" data-id="${esc(s.id)}" tabindex="0" role="button">
        <div class="card-head-row">
          <div class="sk-card-top">
            <div class="sk-icon">S</div>
            <span class="sk-pill ${pillClass(s.status)}">${esc(s.status)}</span>
          </div>
          ${catalogMenu(s.id, skillMenuActions(s))}
        </div>
        <h3>${esc(s.name)}${s.immutable ? '<span class="sk-seal">только чтение</span>' : ''}</h3>
        <p>${esc(s.description || '')}</p>
        <div class="sk-chips">${(s.interfaces || []).map((i) => `<span>${esc(i)}</span>`).join('')}</div>
        <div class="sk-card-foot">
          <span>${esc(s.skill_type)} · v${esc(s.version || '—')}${s.parent_key ? ` · ← ${esc(s.parent_key)}` : ''}</span>
          <span>${esc(s.runs_30d)} запусков / 30д</span>
        </div>
      </article>`).join('');
    bindCardMenus(wrap);
    wrap.querySelectorAll('.sk-card').forEach((card) => {
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
    state.detail = await fetchJSON(`/skills/${id}`);
    show($('#sk-catalog-view'), false);
    show($('#sk-detail-view'), true);
    show($('#sk-editor-view'), false);
    renderDetail();
    showTab('overview');
  }

  function backToCatalog() {
    state.detail = null;
    show($('#sk-detail-view'), false);
    show($('#sk-editor-view'), false);
    show($('#sk-interfaces-view'), false);
    show($('#sk-catalog-view'), true);
    loadCatalog().catch((e) => toast(e.message));
  }

  function contractByKey(key) {
    return state.contracts.find((c) => c.key === key) || null;
  }

  function examplePayload(contract) {
    if (!contract || !contract.json_schema) return null;
    const schema = contract.json_schema;
    const required = schema.required || [];
    const sample = { type: (contract.key || '').split('@')[0] };
    required.forEach((field) => {
      if (field === 'title') sample.title = 'Пример задачи';
      else if (field === 'type') sample.type = (contract.key || '').split('@')[0];
      else sample[field] = '…';
    });
    return sample;
  }

  function contractPreviewHtml(contract) {
    if (!contract) return '<span>Контракт не выбран</span>';
    const example = examplePayload(contract);
    return `
      <div><b>${esc(contract.name)}</b> · <span class="sk-contract-kind">${esc(contract.kind)}</span></div>
      <div>${esc(contract.description || '')}</div>
      ${contract.satisfies && contract.satisfies.length ? `<div>Подходит для: ${contract.satisfies.map((k) => `<code>${esc(k)}</code>`).join(', ')}</div>` : ''}
      ${contract.accepts && contract.accepts.length ? `<div>Принимает: ${contract.accepts.map((k) => `<code>${esc(k)}</code>`).join(', ')}</div>` : ''}
      ${example ? `<pre>${esc(JSON.stringify(example, null, 2))}</pre>` : ''}`;
  }

  function contractLink(key) {
    if (!key || key === '—') return '—';
    return `<button type="button" class="sk-contract-link" data-contract-key="${esc(key)}">${esc(key)}</button>`;
  }

  function bindContractLinks(scope) {
    (scope || root()).querySelectorAll('.sk-contract-link').forEach((btn) => {
      btn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        openContractModal(btn.dataset.contractKey).catch((err) => toast(err.message));
      };
    });
  }

  async function openContractModal(contractKey) {
    let contract = contractByKey(contractKey);
    if (!contract) {
      contract = await fetchJSON(`/artifact-contracts/${encodeURIComponent(contractKey)}`);
    }
    const title = $('#sk-contract-modal-title');
    const body = $('#sk-contract-modal-body');
    if (title) title.textContent = contract.key || 'Контракт';
    if (body) {
      const example = examplePayload(contract);
      body.innerHTML = `
        <dl class="sk-contract-detail-grid">
          <dt>Название</dt><dd>${esc(contract.name || '—')}</dd>
          <dt>Тип</dt><dd><span class="sk-contract-kind">${esc(contract.kind || 'artifact')}</span></dd>
          <dt>Описание</dt><dd>${esc(contract.description || '—')}</dd>
          <dt>Satisfies</dt><dd>${(contract.satisfies || []).map((k) => `<code>${esc(k)}</code>`).join(', ') || '—'}</dd>
          <dt>Accepts</dt><dd>${(contract.accepts || []).map((k) => `<code>${esc(k)}</code>`).join(', ') || '—'}</dd>
        </dl>
        <label>Схема (JSON Schema)</label>
        <pre>${esc(JSON.stringify(contract.json_schema || {}, null, 2))}</pre>
        ${example ? `<label>Пример payload</label><pre>${esc(JSON.stringify(example, null, 2))}</pre>` : ''}`;
    }
    show($('#sk-contract-modal'), true);
  }

  function closeContractModal() {
    show($('#sk-contract-modal'), false);
  }

  function updateInterfaceContractPreviews() {
    const inputKey = ($('#sk-if-input-contract') || {}).value || '';
    const outputKey = ($('#sk-if-output-contract') || {}).value || '';
    const inputPreview = $('#sk-if-input-preview');
    const outputPreview = $('#sk-if-output-preview');
    if (inputPreview) inputPreview.innerHTML = contractPreviewHtml(contractByKey(inputKey));
    if (outputPreview) outputPreview.innerHTML = contractPreviewHtml(contractByKey(outputKey));
  }

  function showInterfaceTab(tab) {
    state.interfaceTab = tab;
    root()?.querySelectorAll('.sk-if-tabs button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.ifTab === tab);
    });
    show($('#sk-if-panel-interfaces'), tab === 'interfaces');
    show($('#sk-if-panel-contracts'), tab === 'contracts');
    show($('#sk-if-create-inline'), tab === 'interfaces');
  }

  function filteredContracts() {
    const q = (state.contractFilters.q || '').trim().toLowerCase();
    const kind = state.contractFilters.kind || '';
    return state.contracts.filter((item) => {
      if (kind && item.kind !== kind) return false;
      if (!q) return true;
      const hay = [
        item.key,
        item.name,
        item.description,
        item.kind,
        ...(item.satisfies || []),
        ...(item.accepts || []),
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }

  function renderContractStats() {
    const el = $('#sk-ct-stats');
    if (!el) return;
    const items = state.contracts;
    el.innerHTML = `
      <span><b>${items.length}</b> всего</span>
      <span><b>${items.filter((c) => c.kind === 'artifact').length}</b> artifact</span>
      <span><b>${items.filter((c) => c.kind === 'patch').length}</b> patch</span>
      <span><b>${items.filter((c) => c.kind === 'work_item').length}</b> work_item</span>`;
  }

  function renderContractsList() {
    const wrap = $('#sk-ct-list');
    if (!wrap) return;
    const items = filteredContracts();
    if (!items.length) {
      wrap.innerHTML = '<p style="color:var(--sk-muted);padding:16px">Контракты не найдены</p>';
      return;
    }
    wrap.innerHTML = `
      <div class="sk-if-table-wrap">
        <table class="sk-table">
          <thead>
            <tr>
              <th>Ключ</th>
              <th>Название</th>
              <th>Тип</th>
              <th>Описание</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${contractLink(item.key)}</td>
                <td>${esc(item.name || '—')}</td>
                <td><span class="sk-contract-kind">${esc(item.kind || 'artifact')}</span></td>
                <td>${esc(item.description || '—')}</td>
                <td class="sk-if-actions">
                  <button type="button" class="sk-btn ghost sk-mini sk-ct-view" data-contract-key="${esc(item.key)}">Подробнее</button>
                </td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
    bindContractLinks(wrap);
    wrap.querySelectorAll('.sk-ct-view').forEach((btn) => {
      btn.onclick = () => openContractModal(btn.dataset.contractKey).catch((e) => toast(e.message));
    });
  }

  async function loadInterfacesData() {
    const [ifaceData, contractData] = await Promise.all([
      fetchJSON('/skill-interfaces'),
      fetchJSON('/artifact-contracts').catch(() => ({ contracts: [] })),
    ]);
    state.interfaces = ifaceData.skill_interfaces || [];
    state.contracts = contractData.contracts || [];
    populateCreateSkillInterfaceSelect();
    return ifaceData;
  }

  function populateCreateSkillInterfaceSelect() {
    const sel = $('#sk-create-interface');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '';
    state.interfaces
      .filter((i) => (i.status || 'active') !== 'deprecated')
      .forEach((i) => {
        const opt = document.createElement('option');
        opt.value = i.key;
        opt.textContent = `${i.key}${i.name ? ` — ${i.name}` : ''}`;
        sel.appendChild(opt);
      });
    if (current) sel.value = current;
  }

  function filteredInterfaces() {
    const q = (state.interfaceFilters.q || '').trim().toLowerCase();
    const source = state.interfaceFilters.source || '';
    return state.interfaces.filter((item) => {
      if (source && item.source !== source) return false;
      if (!q) return true;
      const hay = [
        item.key,
        item.name,
        item.description,
        item.input_contract_key,
        item.output_contract_key,
        ...(item.required_capabilities || []),
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }

  function renderInterfaceStats(counts) {
    const el = $('#sk-if-stats');
    if (!el) return;
    const c = counts || {
      total: state.interfaces.length,
      platform: state.interfaces.filter((i) => i.source === 'platform').length,
      custom: state.interfaces.filter((i) => i.source === 'custom').length,
    };
    el.innerHTML = `
      <span><b>${c.total}</b> всего</span>
      <span><b>${c.platform}</b> платформа</span>
      <span><b>${c.custom}</b> свои</span>`;
  }

  function renderInterfacesList() {
    const wrap = $('#sk-if-list');
    if (!wrap) return;
    const items = filteredInterfaces();
    if (!items.length) {
      wrap.innerHTML = '<p style="color:var(--sk-muted);padding:16px">Интерфейсы не найдены</p>';
      return;
    }
    wrap.innerHTML = `
      <div class="sk-if-table-wrap">
        <table class="sk-table">
          <thead>
            <tr>
              <th>Ключ</th>
              <th>Название</th>
              <th>Вход</th>
              <th>Выход</th>
              <th>Capabilities</th>
              <th>Источник</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${items.map((item) => {
              const platform = item.source === 'platform';
              return `
              <tr data-id="${esc(item.id)}">
                <td><code>${esc(item.key)}</code></td>
                <td>${esc(item.name || '—')}</td>
                <td>${contractLink(item.input_contract_key || '—')}</td>
                <td>${contractLink(item.output_contract_key || '—')}</td>
                <td>${(item.required_capabilities || []).slice(0, 3).map((c) => `<span class="sk-chip">${esc(c)}</span>`).join(' ') || '—'}</td>
                <td>${platform ? '<span class="sk-seal">platform</span>' : '<span class="sk-pill amber">custom</span>'}</td>
                <td class="sk-if-actions">
                  <button type="button" class="sk-btn ghost sk-mini sk-if-view" data-id="${esc(item.id)}">${platform ? 'Открыть' : 'Изменить'}</button>
                  ${platform ? '' : `<button type="button" class="sk-btn ghost sk-mini danger sk-if-delete" data-id="${esc(item.id)}">Удалить</button>`}
                </td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>`;
    wrap.querySelectorAll('.sk-if-view').forEach((btn) => {
      btn.onclick = () => {
        const item = state.interfaces.find((i) => String(i.id) === String(btn.dataset.id));
        const mode = item && item.source === 'custom' ? 'edit' : 'view';
        openInterfaceModal(mode, btn.dataset.id).catch((e) => toast(e.message));
      };
    });
    wrap.querySelectorAll('.sk-if-delete').forEach((btn) => {
      btn.onclick = () => deleteInterface(btn.dataset.id).catch((e) => toast(e.message));
    });
    bindContractLinks(wrap);
  }

  async function openInterfacesView() {
    show($('#sk-catalog-view'), false);
    show($('#sk-detail-view'), false);
    show($('#sk-editor-view'), false);
    show($('#sk-interfaces-view'), true);
    showInterfaceTab(state.interfaceTab || 'interfaces');
    const data = await loadInterfacesData();
    renderInterfaceStats(data.counts);
    renderContractsList();
    renderContractStats();
    renderInterfacesList();
  }

  function backFromInterfaces() {
    show($('#sk-interfaces-view'), false);
    show($('#sk-catalog-view'), true);
  }

  function fillContractSelects() {
    const inputSel = $('#sk-if-input-contract');
    const outputSel = $('#sk-if-output-contract');
    [inputSel, outputSel].forEach((sel) => {
      if (!sel) return;
      const current = sel.value;
      sel.innerHTML = state.contracts.map((c) =>
        `<option value="${esc(c.key)}">${esc(c.key)} — ${esc(c.name)}</option>`
      ).join('');
      if (current) sel.value = current;
    });
    updateInterfaceContractPreviews();
  }

  function setInterfaceFormReadOnly(readOnly) {
    ['#sk-if-key', '#sk-if-name', '#sk-if-desc', '#sk-if-input-contract', '#sk-if-output-contract', '#sk-if-caps'].forEach((sel) => {
      const el = $(sel);
      if (el) el.disabled = !!readOnly;
    });
    show($('#sk-if-readonly-note'), readOnly);
    show($('#sk-if-submit-modal'), !readOnly);
    show($('#sk-if-delete-modal'), !readOnly && state.interfaceModalMode === 'edit');
  }

  async function openInterfaceModal(mode, id) {
    if (!state.contracts.length) {
      await loadInterfacesData();
    }
    fillContractSelects();
    state.interfaceModalMode = mode;
    state.editingInterfaceId = id || null;
    const item = id ? state.interfaces.find((i) => String(i.id) === String(id)) : null;
    const platform = item && item.source === 'platform';
    const title = $('#sk-if-modal-title');
    const keyEl = $('#sk-if-key');
    const nameEl = $('#sk-if-name');
    const descEl = $('#sk-if-desc');
    const capsEl = $('#sk-if-caps');
    if (title) {
      title.textContent = platform
        ? 'Интерфейс (просмотр)'
        : (mode === 'edit' ? 'Редактировать интерфейс' : 'Новый интерфейс');
    }
    if (keyEl) {
      keyEl.value = item ? item.key : '';
      keyEl.readOnly = mode !== 'create';
    }
    if (nameEl) nameEl.value = item ? (item.name || '') : '';
    if (descEl) descEl.value = item ? (item.description || '') : '';
    if ($('#sk-if-input-contract')) {
      $('#sk-if-input-contract').value = item
        ? (item.input_contract_key || 'WorkItem@1')
        : 'WorkItem@1';
    }
    if ($('#sk-if-output-contract')) {
      $('#sk-if-output-contract').value = item
        ? (item.output_contract_key || 'ArtifactPatch@1')
        : 'ArtifactPatch@1';
    }
    if (capsEl) {
      capsEl.value = item ? (item.required_capabilities || []).join(', ') : '';
    }
    setInterfaceFormReadOnly(platform);
    const inputSel = $('#sk-if-input-contract');
    const outputSel = $('#sk-if-output-contract');
    if (inputSel) inputSel.onchange = updateInterfaceContractPreviews;
    if (outputSel) outputSel.onchange = updateInterfaceContractPreviews;
    updateInterfaceContractPreviews();
    show($('#sk-if-modal'), true);
  }

  function closeInterfaceModal() {
    show($('#sk-if-modal'), false);
    state.editingInterfaceId = null;
    state.interfaceModalMode = 'create';
  }

  function parseCapabilities(raw) {
    return String(raw || '')
      .split(/[,;\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  async function submitInterfaceModal() {
    const name = ($('#sk-if-name') || {}).value || '';
    const key = ($('#sk-if-key') || {}).value || '';
    const description = ($('#sk-if-desc') || {}).value || '';
    const input_contract_key = ($('#sk-if-input-contract') || {}).value || '';
    const output_contract_key = ($('#sk-if-output-contract') || {}).value || '';
    const required_capabilities = parseCapabilities(($('#sk-if-caps') || {}).value);
    if (!name.trim()) {
      toast('Укажите название');
      return;
    }
    const payload = {
      name: name.trim(),
      description: description.trim(),
      input_contract_key,
      output_contract_key,
      required_capabilities,
      status: 'active',
    };
    if (state.interfaceModalMode === 'create') {
      if (!key.trim()) {
        toast('Укажите ключ интерфейса');
        return;
      }
      await fetchJSON('/skill-interfaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, key: key.trim() }),
      });
      toast('Интерфейс создан');
    } else if (state.editingInterfaceId) {
      await fetchJSON(`/skill-interfaces/${state.editingInterfaceId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      toast('Интерфейс обновлён');
    } else {
      return;
    }
    closeInterfaceModal();
    const data = await loadInterfacesData();
    renderInterfaceStats(data.counts);
    renderContractStats();
    renderContractsList();
    renderInterfacesList();
  }

  async function deleteInterface(id) {
    const item = state.interfaces.find((i) => String(i.id) === String(id));
    if (!item) return;
    if (item.source === 'platform') {
      toast('Платформенный интерфейс нельзя удалить');
      return;
    }
    if (!window.confirm(`Удалить интерфейс «${item.key}»?`)) return;
    await fetchJSON(`/skill-interfaces/${id}`, { method: 'DELETE' });
    toast('Интерфейс удалён');
    if (state.editingInterfaceId && String(state.editingInterfaceId) === String(id)) {
      closeInterfaceModal();
    }
    const data = await loadInterfacesData();
    renderInterfaceStats(data.counts);
    renderContractStats();
    renderContractsList();
    renderInterfacesList();
  }

  function renderDetail() {
    const detail = state.detail;
    if (!detail) return;
    const skill = detail.skill || {};
    const ver = currentVersion(detail) || {};
    const status = detail.published_version ? 'PUBLISHED' : (detail.draft_version ? 'DRAFT' : (skill.status || '').toUpperCase());
    const immutable = !!skill.immutable;

    const eyebrow = $('#sk-detail-eyebrow');
    const title = $('#sk-detail-title');
    const desc = $('#sk-detail-desc');
    if (eyebrow) eyebrow.textContent = (typeLabel(skill.skill_type) + ' · навык').toUpperCase();
    if (title) title.textContent = skill.name || '';
    if (desc) {
      const parent = detail.parent;
      const parentNote = parent
        ? ` Наследует: ${parent.name} (${parent.skill_type}).`
        : '';
      const sealNote = immutable
        ? ' Пакет запечатан — изменения только через наследование.'
        : '';
      desc.textContent = `${skill.description || ''}${parentNote}${sealNote}`;
    }

    const strip = $('#sk-meta-strip');
    if (strip) {
      strip.innerHTML = `
        <span class="sk-pill ${pillClass(status)}">${esc(status)}</span>
        <span>v${esc(ver.semantic_version || '—')}</span>
        <span>Владелец: ${esc(skill.owner_team || '—')}</span>
        <span>${esc(skill.runs_30d || 0)} запусков / 30д</span>
        <span>${esc(skill.runs_30d ? (((skill.success_rate || 0) * 100).toFixed(1) + '% успех') : 'нет запусков')}</span>
        ${immutable ? '<span class="sk-seal">неизменяемый</span>' : ''}
        ${detail.parent ? `<span>← ${esc(detail.parent.name)}</span>` : ''}`;
    }

    const editBtn = $('#sk-btn-edit');
    const versionBtn = $('#sk-btn-create-version');
    if (editBtn) {
      editBtn.disabled = immutable;
      editBtn.title = immutable
        ? 'Corporate/Core навыки нельзя редактировать — наследуйте'
        : (!detail.draft_version ? 'Создаст draft и откроет редактор' : '');
      editBtn.classList.toggle('sk-hidden', immutable);
    }
    if (versionBtn) {
      versionBtn.classList.toggle('sk-hidden', immutable);
    }

    const menuHost = $('#sk-detail-menu');
    if (menuHost && skill.id) {
      menuHost.innerHTML = catalogMenu(skill.id, skillMenuActions({ immutable }));
      bindCardMenus(menuHost);
    }
  }

  function formatPackageTree(files) {
    const root = buildTreeNodes(files || []);
    const lines = [];
    function walk(node, prefix, isLast, isRoot) {
      if (!isRoot) {
        const branch = isLast ? '└── ' : '├── ';
        const label = node.kind === 'folder' ? `${node.name}/` : node.name;
        lines.push(`${prefix}${branch}${label}`);
      }
      const keys = sortedChildKeys(node.children);
      keys.forEach((key, idx) => {
        const child = node.children[key];
        const last = idx === keys.length - 1;
        const nextPrefix = isRoot ? '' : `${prefix}${isLast ? '    ' : '│   '}`;
        walk(child, nextPrefix, last, false);
      });
    }
    walk(root, '', true, true);
    return lines.join('\n') || '(пусто)';
  }

  function showTab(tab) {
    root()?.querySelectorAll('.sk-tabs button').forEach((b) => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    const content = $('#sk-tab-content');
    if (!content || !state.detail) return;
    const skill = state.detail.skill || {};
    const ver = currentVersion(state.detail) || {};
    const report = ver.validation_report || {};
    const files = ver.files || [];
    const views = {
      overview: `
        <div class="sk-panel-grid">
          <div class="sk-panel">
            <h3>Обзор навыка</h3>
            <div class="sk-kv"><span>Реализует</span><b>${esc(ver.interface_key || '—')}</b></div>
            <div class="sk-kv"><span>Входной контракт</span><span>${esc(ver.input_contract_key || '—')}</span></div>
            <div class="sk-kv"><span>Выходной контракт</span><span>${esc(ver.output_contract_key || '—')}</span></div>
            <div class="sk-kv"><span>Runtime</span><span>${esc(ver.runtime_type || '—')}</span></div>
            <div class="sk-kv"><span>Checksum пакета</span><span>${esc((ver.package_checksum || '').slice(0, 16))}…</span></div>
            <div class="sk-kv"><span>Родитель</span><span>${esc((state.detail.parent && state.detail.parent.name) || '—')}</span></div>
          </div>
          <div class="sk-panel">
            <h3>Способности</h3>
            <div class="sk-chips">${(ver.allowed_capabilities || []).map((c) => (
              window.PlatformUtil && window.PlatformUtil.entityLink
                ? window.PlatformUtil.entityLink('capabilities-platform', c, { id: c, key: c })
                : `<span>${esc(c)}</span>`
            )).join('') || '—'}
            </div>
            <p style="margin-top:8px;font-size:11px;color:#748096">Навыки (skills) запрашивают способности — MCP-инструменты привязываются в реестре способностей.</p>
            <h3 style="margin-top:22px">Качество</h3>
            <div class="sk-kv"><span>Валидация</span><b style="color:${report.valid ? '#1f9d66' : '#d84848'}">${esc(ver.validation_status || 'unknown')}</b></div>
            <div class="sk-kv"><span>Тест-кейсы</span><span>${esc((ver.test_cases || []).filter((t) => t.status === 'PASSED').length)} / ${esc((ver.test_cases || []).length)} пройдено</span></div>
            <div class="sk-kv"><span>Успешность</span><span>${esc(skill.runs_30d ? (((skill.success_rate || 0) * 100).toFixed(1) + '%') : '—')}</span></div>
          </div>
        </div>`,
      instructions: `
        <div class="sk-panel"><h3>SKILL.md</h3>
          <pre class="sk-pre">${esc(ver.skill_markdown || '')}</pre>
        </div>`,
      package: `
        <div class="sk-panel">
          <h3>Файлы и папки пакета</h3>
          <p style="color:var(--sk-muted);font-size:13px;margin-top:0">Дерево пакета: шаблоны, скрипты, субагенты и примеры. В редакторе файлы добавляются внутрь выбранной папки.</p>
          <pre class="sk-pre">${esc(formatPackageTree(files))}</pre>
        </div>`,
      manifest: `
        <div class="sk-panel"><h3>Манифест</h3>
          <pre class="sk-pre">${esc(JSON.stringify(ver.manifest || {}, null, 2))}</pre>
        </div>`,
      interfaces: `
        <div class="sk-panel">
          <table class="sk-table"><thead><tr><th>Интерфейс</th><th>Совместимость</th><th>Вход</th><th>Выход</th></tr></thead>
          <tbody><tr>
            <td>${esc(ver.interface_key || '—')}</td>
            <td><span class="sk-pill green">COMPATIBLE</span></td>
            <td>${esc(ver.input_contract_key || '—')}</td>
            <td>${esc(ver.output_contract_key || '—')}</td>
          </tr></tbody></table>
        </div>`,
      tests: `
        <div class="sk-panel">
          <table class="sk-table"><thead><tr><th>Тест</th><th>Режим</th><th>Статус</th><th>Длительность</th></tr></thead>
          <tbody>${(ver.test_cases || []).map((t) => `<tr>
            <td>${esc(t.name)}</td><td>${esc(t.mode)}</td>
            <td><span class="sk-pill ${t.status === 'PASSED' ? 'green' : 'amber'}">${esc(t.status)}</span></td>
            <td>${t.duration_s != null ? esc(t.duration_s) + 's' : '—'}</td>
          </tr>`).join('') || '<tr><td colspan="4">Нет тестов</td></tr>'}</tbody></table>
        </div>`,
      bindings: `
        <div class="sk-panel">
          <table class="sk-table"><thead><tr><th>Scope</th><th>Target</th><th>Priority</th><th>Status</th></tr></thead>
          <tbody>${(skill.bindings || []).map((b) => `<tr>
            <td>${esc(b.scope)}</td><td>${esc(b.target)}</td>
            <td>${esc(b.priority)}</td>
            <td><span class="sk-pill green">${esc(b.status)}</span></td>
          </tr>`).join('') || '<tr><td colspan="4">Нет привязок</td></tr>'}</tbody></table>
        </div>`,
      versions: `
        <div class="sk-panel">
          <table class="sk-table"><thead><tr><th>Версия</th><th>Статус</th><th>Валидация</th><th>Опубликовано</th></tr></thead>
          <tbody>${(state.detail.versions || []).map((v) => `<tr>
            <td>${esc(v.semantic_version)}</td>
            <td><span class="sk-pill ${pillClass(v.status)}">${esc(v.status)}</span></td>
            <td>${esc(v.validation_status)}</td>
            <td>${esc(v.published_at ? new Date(v.published_at).toLocaleDateString('ru-RU') : '—')}</td>
          </tr>`).join('')}</tbody></table>
        </div>`,
      validation: `
        <div class="sk-panel-grid">
          <div class="sk-panel"><h3>Отчёт валидации</h3>
            ${['package', 'manifest', 'contracts', 'security'].map((k) => {
              const val = (report.checks || {})[k] || (report.valid ? 'passed' : 'failed');
              const color = val === 'passed' ? '#1f9d66' : (val === 'warning' ? '#d58b18' : '#d84848');
              return `<div class="sk-kv"><span>${esc(k)}</span><b style="color:${color}">${esc(String(val).charAt(0).toUpperCase() + String(val).slice(1))}</b></div>`;
            }).join('')}
          </div>
          <div class="sk-panel"><h3>Предупреждения / ошибки</h3>
            ${(report.errors || []).map((e) => `<div class="sk-problem err">${esc(e.message || e.code)}</div>`).join('')}
            ${(report.warnings || []).map((e) => `<div class="sk-problem warn">${esc(e.message || e.code)}</div>`).join('')}
            ${!(report.errors || []).length && !(report.warnings || []).length ? '<div class="sk-problem ok">Замечаний нет</div>' : ''}
          </div>
        </div>`,
    };
    content.innerHTML = views[tab] || views.overview;
    if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
      window.PlatformUtil.bindEntityLinks(content);
    }
  }

  async function openEditor() {
    const detail = state.detail;
    if (isImmutable(detail)) {
      toast('Corporate/Core навыки нельзя редактировать. Создайте наследника.');
      return;
    }
    if (!detail) return;
    let ver = editableVersion(detail);
    if (!ver) {
      await createDraft();
      ver = editableVersion(state.detail);
    }
    if (!ver) {
      toast('Не удалось создать draft-версию');
      return;
    }
    const current = state.detail;
    show($('#sk-editor-view'), true);
    const title = $('#sk-editor-title');
    const pill = $('#sk-editor-pill');
    if (title) title.textContent = current.skill.name;
    if (pill) {
      pill.textContent = `${ver.status} v${ver.semantic_version}`;
      pill.className = `sk-pill ${pillClass(ver.status)}`;
    }
    state.activeFile = 'SKILL.md';
    state.selectedFolder = '';
    hideAddForm();
    renderFileTree(ver);
    loadActiveFile(ver);
    fillInspector(ver);
  }

  async function openDetailAndEdit(id) {
    if (!state.detail || !state.detail.skill || String(state.detail.skill.id) !== String(id)) {
      state.detail = await fetchJSON(`/skills/${id}`);
    }
    show($('#sk-catalog-view'), false);
    show($('#sk-detail-view'), true);
    renderDetail();
    showTab('overview');
    await openEditor();
  }

  function closeEditor() {
    show($('#sk-editor-view'), false);
    hideAddForm();
  }

  function normalizeFolder(path) {
    if (!path) return '';
    const cleaned = String(path).replace(/\\/g, '/').replace(/^\/+/, '');
    if (!cleaned) return '';
    return cleaned.endsWith('/') ? cleaned : `${cleaned}/`;
  }

  function isFolderEntry(entry) {
    return !!(entry && (entry.kind === 'folder' || String(entry.path || '').endsWith('/')));
  }

  function entryName(path, isFolder) {
    const cleaned = String(path || '').replace(/\/+$/, '');
    const parts = cleaned.split('/').filter(Boolean);
    return parts[parts.length - 1] || path;
  }

  function buildTreeNodes(files) {
    const root = { name: '', path: '', kind: 'folder', children: {} };
    (files || []).forEach((entry) => {
      const folder = isFolderEntry(entry);
      const raw = String(entry.path || '').replace(/^\/+/, '');
      if (!raw) return;
      const parts = (folder ? raw.replace(/\/+$/, '') : raw).split('/').filter(Boolean);
      if (!parts.length) return;
      let node = root;
      parts.forEach((part, idx) => {
        const isLast = idx === parts.length - 1;
        const asFolder = !isLast || folder;
        const childPath = asFolder
          ? `${parts.slice(0, idx + 1).join('/')}/`
          : parts.slice(0, idx + 1).join('/');
        if (!node.children[part]) {
          node.children[part] = {
            name: part,
            path: childPath,
            kind: asFolder ? 'folder' : 'file',
            entry: null,
            children: {},
          };
        }
        if (isLast) {
          node.children[part].kind = asFolder ? 'folder' : 'file';
          node.children[part].path = childPath;
          node.children[part].entry = entry;
        } else {
          node.children[part].kind = 'folder';
          node.children[part].path = `${parts.slice(0, idx + 1).join('/')}/`;
        }
        node = node.children[part];
      });
    });
    return root;
  }

  function sortedChildKeys(children) {
    return Object.keys(children || {}).sort((a, b) => {
      const aFolder = children[a].kind === 'folder';
      const bFolder = children[b].kind === 'folder';
      if (aFolder !== bFolder) return aFolder ? -1 : 1;
      return a.localeCompare(b);
    });
  }

  function renderTreeRows(node, depth, rows) {
    sortedChildKeys(node.children).forEach((key) => {
      const child = node.children[key];
      const isFolder = child.kind === 'folder';
      const collapsed = !!state.collapsed[child.path];
      const active = !isFolder && child.path === state.activeFile;
      const selected = isFolder && normalizeFolder(child.path) === normalizeFolder(state.selectedFolder);
      rows.push({
        path: child.path,
        kind: child.kind,
        depth,
        name: entryName(child.path, isFolder),
        collapsed,
        active,
        selected,
        locked: child.path === 'SKILL.md',
        hasChildren: isFolder && Object.keys(child.children || {}).length > 0,
      });
      if (isFolder && !collapsed) {
        renderTreeRows(child, depth + 1, rows);
      }
    });
  }

  function formatManifest(manifest) {
    if (!manifest || typeof manifest !== 'object' || !Object.keys(manifest).length) return '';
    try {
      return JSON.stringify(manifest, null, 2);
    } catch (_) {
      return '';
    }
  }

  function packageFiles(ver) {
    const files = (ver && ver.files) ? ver.files.slice() : [];
    if (!files.some((f) => f.path === 'SKILL.md')) {
      files.unshift({ path: 'SKILL.md', kind: 'file', content_text: (ver && ver.skill_markdown) || '' });
    }
    const manifestText = formatManifest(ver && ver.manifest);
    const mi = files.findIndex((f) => f.path === 'manifest.yaml');
    if (mi >= 0) {
      if (!(files[mi].content_text || '').trim() && manifestText) {
        files[mi] = Object.assign({}, files[mi], { content_text: manifestText });
      }
    } else if (manifestText) {
      files.splice(Math.min(1, files.length), 0, {
        path: 'manifest.yaml',
        kind: 'file',
        media_type: 'text/yaml',
        content_text: manifestText,
      });
    }
    return files;
  }

  function clearDropTargets() {
    root()?.querySelectorAll('.drop-target').forEach((el) => el.classList.remove('drop-target'));
    root()?.querySelectorAll('.dragging').forEach((el) => el.classList.remove('dragging'));
  }

  function bindDropTarget(el, destFolder, ver) {
    el.ondragover = (ev) => {
      ev.preventDefault();
      el.classList.add('drop-target');
      if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
    };
    el.ondragleave = () => el.classList.remove('drop-target');
    el.ondrop = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      clearDropTargets();
      const fromPath = ev.dataTransfer && ev.dataTransfer.getData('text/plain');
      if (!fromPath) return;
      moveEntry(fromPath, destFolder).catch((e) => toast(e.message));
    };
  }

  function renderFileTree(ver) {
    const tree = $('#sk-filetree-list');
    const rootDrop = $('#sk-filetree-root');
    if (!tree) return;
    const rootNode = buildTreeNodes(packageFiles(ver));
    const rows = [];
    renderTreeRows(rootNode, 0, rows);

    if (rootDrop) {
      const rootSelected = !state.selectedFolder;
      rootDrop.classList.toggle('selected-folder', rootSelected);
      rootDrop.onclick = () => {
        state.selectedFolder = '';
        state.selectionKind = 'folder';
        renderFileTree(ver);
      };
      bindDropTarget(rootDrop, '', ver);
    }

    if (!rows.length) {
      tree.innerHTML = '<p style="color:var(--sk-muted);font-size:12px">Пакет пуст</p>';
      return;
    }
    tree.innerHTML = rows.map((row) => {
      const pad = 6 + row.depth * 14;
      const twist = row.kind === 'folder'
        ? `<span class="sk-tree-twist" data-twist="${esc(row.path)}">${row.hasChildren ? (row.collapsed ? '▸' : '▾') : ''}</span>`
        : '<span class="sk-tree-twist"></span>';
      const mark = `<span class="sk-tree-mark ${row.kind === 'folder' ? 'folder' : 'file'}"></span>`;
      const draggable = row.locked ? '' : ' draggable="true"';
      return `<div class="sk-tree-row${row.active ? ' active' : ''}${row.kind === 'folder' ? ' folder' : ''}${row.selected ? ' selected-folder' : ''}"
        data-path="${esc(row.path)}" data-kind="${esc(row.kind)}" style="padding-left:${pad}px"${draggable}>
        ${twist}${mark}<span class="sk-tree-name" title="${esc(row.path)}">${esc(row.name)}</span>
      </div>`;
    }).join('');

    tree.querySelectorAll('.sk-tree-row').forEach((el) => {
      const path = el.dataset.path;
      const kind = el.dataset.kind;
      el.onclick = (ev) => {
        const twist = ev.target.closest('[data-twist]');
        if (twist) {
          const twistPath = twist.dataset.twist;
          state.collapsed[twistPath] = !state.collapsed[twistPath];
          renderFileTree(ver);
          return;
        }
        if (kind === 'folder') {
          state.selectedFolder = normalizeFolder(path);
          state.selectionKind = 'folder';
          renderFileTree(ver);
          return;
        }
        state.activeFile = path;
        state.selectionKind = 'file';
        state.selectedFolder = path.includes('/')
          ? normalizeFolder(path.split('/').slice(0, -1).join('/'))
          : '';
        loadActiveFile(ver);
        renderFileTree(ver);
      };

      if (el.getAttribute('draggable') === 'true') {
        el.ondragstart = (ev) => {
          el.classList.add('dragging');
          if (ev.dataTransfer) {
            ev.dataTransfer.setData('text/plain', path);
            ev.dataTransfer.effectAllowed = 'move';
          }
        };
        el.ondragend = () => clearDropTargets();
      }

      if (kind === 'folder') {
        bindDropTarget(el, normalizeFolder(path), ver);
      }
    });
  }

  async function moveEntry(fromPath, destFolder) {
    const detail = state.detail;
    const ver = editableVersion(detail);
    if (!detail || !ver) {
      toast('Нет draft-версии');
      return;
    }
    if (fromPath === 'SKILL.md') {
      toast('SKILL.md нельзя перемещать');
      return;
    }
    const fromFolder = fromPath.endsWith('/');
    const base = fromPath.replace(/\/+$/, '').split('/').pop();
    const parentOfFrom = fromPath.includes('/')
      ? normalizeFolder(fromPath.replace(/\/+$/, '').split('/').slice(0, -1).join('/'))
      : '';
    const targetFolder = normalizeFolder(destFolder);
    if (targetFolder === parentOfFrom) {
      return;
    }
    if (fromFolder && targetFolder.startsWith(fromPath)) {
      toast('Нельзя переместить папку внутрь себя');
      return;
    }
    const toPath = targetFolder ? `${targetFolder}${base}${fromFolder ? '/' : ''}` : `${base}${fromFolder ? '/' : ''}`;
    const payload = await fetchJSON(`/skills/${detail.skill.id}/versions/${ver.id}/files/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_path: fromPath,
        to_path: toPath,
        revision: ver.revision,
      }),
    });
    if (state.detail.draft_version) {
      state.detail.draft_version.files = payload.files || state.detail.draft_version.files;
      state.detail.draft_version.revision = payload.revision;
    }
    if (state.activeFile === fromPath || (fromFolder && String(state.activeFile || '').startsWith(fromPath))) {
      if (fromFolder) {
        state.activeFile = `${toPath}${String(state.activeFile).slice(fromPath.length)}`;
      } else {
        state.activeFile = toPath;
      }
    }
    state.selectedFolder = targetFolder;
    if (fromFolder) {
      delete state.collapsed[fromPath];
      state.collapsed[toPath] = false;
    }
    toast('Перемещено');
    await refreshEditorDetail();
  }

  async function deleteSelectedEntry() {
    const detail = state.detail;
    const ver = editableVersion(detail);
    if (!detail || !ver) {
      toast('Нет draft-версии');
      return;
    }
    let path = '';
    if (state.selectionKind === 'folder') {
      path = state.selectedFolder || '';
    } else {
      path = state.activeFile || '';
    }
    if (!path) {
      toast('Выберите файл или папку для удаления');
      return;
    }
    if (path === 'SKILL.md') {
      toast('SKILL.md нельзя удалить');
      return;
    }
    const label = path.replace(/\/+$/, '').split('/').pop() || path;
    if (!window.confirm(`Удалить «${label}»?`)) return;
    const parts = path.replace(/\/+$/, '').split('/').filter(Boolean).map(encodeURIComponent);
    const encoded = parts.join('/') + (path.endsWith('/') ? '/' : '');
    const q = new URLSearchParams({ revision: String(ver.revision) });
    const payload = await fetchJSON(
      `/skills/${detail.skill.id}/versions/${ver.id}/files/${encoded}?${q.toString()}`,
      { method: 'DELETE' }
    );
    if (state.detail.draft_version) {
      state.detail.draft_version.files = payload.files || [];
      state.detail.draft_version.revision = payload.revision;
    }
    if (path.endsWith('/') || state.activeFile === path || String(state.activeFile || '').startsWith(path)) {
      state.activeFile = 'SKILL.md';
      state.selectionKind = 'file';
    }
    if (path.endsWith('/')) {
      const parent = path.replace(/\/+$/, '').split('/').slice(0, -1).join('/');
      state.selectedFolder = parent ? normalizeFolder(parent) : '';
    }
    toast('Удалено');
    await refreshEditorDetail();
  }

  function loadActiveFile(ver) {
    const ta = $('#sk-editor-text');
    const pathLabel = $('#sk-active-path');
    if (pathLabel) pathLabel.textContent = state.activeFile || 'SKILL.md';
    if (!ta) return;
    if (state.activeFile === 'SKILL.md') {
      ta.value = ver.skill_markdown || '';
      ta.readOnly = ver.status === 'PUBLISHED';
      return;
    }
    const file = packageFiles(ver).find((f) => f.path === state.activeFile);
    ta.value = (file && file.content_text) || '';
    ta.readOnly = ver.status === 'PUBLISHED' || isFolderEntry(file);
  }

  function fillInspector(ver) {
    const iface = $('#sk-insp-interface');
    const input = $('#sk-insp-input');
    const output = $('#sk-insp-output');
    const caps = $('#sk-insp-caps');
    const problems = $('#sk-insp-problems');
    if (iface) iface.textContent = ver.interface_key || '—';
    if (input) input.textContent = ver.input_contract_key || '—';
    if (output) output.textContent = ver.output_contract_key || '—';
    if (caps) {
      caps.innerHTML = (ver.allowed_capabilities || []).map((c) => `<span>${esc(c)}</span>`).join('');
    }
    const report = ver.validation_report || {};
    const warns = report.warnings || [];
    const errs = report.errors || [];
    if (problems) {
      const count = $('#sk-problem-count');
      if (count) count.textContent = String(warns.length + errs.length);
      problems.innerHTML = [
        ...errs.map((e) => `<div class="sk-problem err">${esc(e.message || e.code)}</div>`),
        ...warns.map((e) => `<div class="sk-problem warn">${esc(e.message || e.code)}</div>`),
      ].join('') || '<div class="sk-problem ok">Блокирующих проблем нет</div>';
    }
  }

  function hideAddForm() {
    state.addKind = null;
    show($('#sk-add-form'), false);
  }

  function openAddForm(kind) {
    const detail = state.detail;
    const ver = editableVersion(detail);
    if (!detail || !ver) {
      toast('Нет draft-версии');
      return;
    }
    state.addKind = kind;
    const form = $('#sk-add-form');
    const title = $('#sk-add-form-title');
    const parent = $('#sk-add-parent');
    const name = $('#sk-add-name');
    if (title) title.textContent = kind === 'folder' ? 'Новая папка' : 'Новый файл';
    if (parent) parent.value = state.selectedFolder || '/ (корень пакета)';
    if (name) {
      name.value = '';
      name.placeholder = kind === 'folder' ? 'domain' : 'example.md';
      name.focus();
    }
    show(form, true);
  }

  function resolveAddPath(kind, parentFolder, rawName) {
    let name = String(rawName || '').trim().replace(/\\/g, '/').replace(/^\/+/, '');
    if (!name) throw new Error('Укажите имя');
    if (name.includes('..')) throw new Error('Недопустимый путь');
    // Allow typing a full relative path in the name field.
    let full = name;
    if (!name.includes('/') && parentFolder) {
      full = `${normalizeFolder(parentFolder)}${name}`;
    }
    if (kind === 'folder') {
      full = normalizeFolder(full);
    } else if (full.endsWith('/')) {
      throw new Error('Для файла укажите имя с расширением, не папку');
    }
    return full;
  }

  async function submitAddForm() {
    const detail = state.detail;
    const ver = editableVersion(detail);
    const kind = state.addKind;
    if (!detail || !ver || !kind) return;
    const nameInput = $('#sk-add-name');
    let path;
    try {
      path = resolveAddPath(kind, state.selectedFolder, nameInput && nameInput.value);
    } catch (err) {
      toast(err.message || String(err));
      return;
    }
    const existing = packageFiles(ver).some((f) => f.path === path);
    if (existing && kind === 'folder') {
      toast('Такая папка уже есть — выберите её в дереве');
      hideAddForm();
      state.selectedFolder = path;
      renderFileTree(ver);
      return;
    }
    const payload = await fetchJSON(`/skills/${detail.skill.id}/versions/${ver.id}/files`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path,
        kind: kind === 'folder' ? 'folder' : 'file',
        content: '',
        revision: ver.revision,
      }),
    });
    if (state.detail.draft_version) {
      state.detail.draft_version.files = payload.files || state.detail.draft_version.files;
      state.detail.draft_version.revision = payload.revision;
    }
    if (path.endsWith('/')) {
      state.selectedFolder = path;
      state.collapsed[path] = false;
    } else {
      state.activeFile = path;
      state.selectedFolder = path.includes('/')
        ? normalizeFolder(path.split('/').slice(0, -1).join('/'))
        : '';
    }
    hideAddForm();
    toast(kind === 'folder' ? 'Папка добавлена' : 'Файл добавлен');
    await refreshEditorDetail();
  }

  async function refreshEditorDetail() {
    const skillId = state.detail && state.detail.skill && state.detail.skill.id;
    if (!skillId) return null;
    state.detail = await fetchJSON(`/skills/${skillId}`);
    const next = editableVersion(state.detail);
    if (next) {
      fillInspector(next);
      renderFileTree(next);
      loadActiveFile(next);
      const pill = $('#sk-editor-pill');
      if (pill) pill.textContent = `${next.status} v${next.semantic_version} · rev ${next.revision}`;
    }
    renderDetail();
    return next;
  }

  async function saveDraft() {
    const detail = state.detail;
    const ver = editableVersion(detail);
    if (!detail || !ver) return;
    const ta = $('#sk-editor-text');
    const content = ta ? ta.value : '';
    const path = state.activeFile || 'SKILL.md';
    if (path.endsWith('/')) {
      toast('Выберите файл, а не папку');
      return;
    }
    if (path === 'SKILL.md') {
      await fetchJSON(
        `/skills/${detail.skill.id}/versions/${ver.id}/files/SKILL.md`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, revision: ver.revision }),
        }
      );
    } else {
      await fetchJSON(
        `/skills/${detail.skill.id}/versions/${ver.id}/files/${path.split('/').map(encodeURIComponent).join('/')}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, kind: 'file', revision: ver.revision }),
        }
      );
    }
    toast('Draft сохранён');
    await refreshEditorDetail();
  }

  async function addPackageEntry(kind) {
    openAddForm(kind);
  }

  async function validateCurrent() {
    const detail = state.detail;
    const ver = editableVersion(detail) || currentVersion(detail);
    if (!detail || !ver) return;
    const report = await fetchJSON(
      `/skills/${detail.skill.id}/versions/${ver.id}/validate`,
      { method: 'POST' }
    );
    toast(report.valid ? 'Валидация пройдена' : 'Валидация не пройдена');
    state.detail = await fetchJSON(`/skills/${detail.skill.id}`);
    const next = editableVersion(state.detail) || currentVersion(state.detail);
    if (next) fillInspector(next);
    renderDetail();
    showTab('validation');
  }

  async function createDraft() {
    const detail = state.detail;
    if (!detail) return;
    if (isImmutable(detail)) {
      toast('Для Corporate/Core создайте наследника вместо новой версии');
      return;
    }
    state.detail = await fetchJSON(`/skills/${detail.skill.id}/versions`, { method: 'POST' });
    toast('Draft-версия создана');
    renderDetail();
  }

  async function publishCurrent() {
    const detail = state.detail;
    const ver = editableVersion(detail);
    if (!detail || !ver) return;
    state.detail = await fetchJSON(
      `/skills/${detail.skill.id}/versions/${ver.id}/publish`,
      { method: 'POST' }
    );
    toast('Опубликовано');
    closeEditor();
    renderDetail();
  }

  function openModal(mode, id) {
    state.modalMode = mode;
    state.editingId = id || null;
    const title = $('#sk-modal-title');
    const createFields = $('#sk-create-fields');
    if (title) {
      title.textContent = mode === 'edit' ? 'Редактировать навык' : 'Создать навык';
    }
    show(createFields, true);
    if (mode === 'edit' && id) {
      const item = state.items.find((s) => String(s.id) === String(id));
      const fromDetail = state.detail && state.detail.skill
        && String(state.detail.skill.id) === String(id)
        ? state.detail.skill
        : null;
      const skill = item || fromDetail || {};
      const nameEl = $('#sk-create-name');
      const descEl = $('#sk-create-desc');
      if (nameEl) nameEl.value = skill.name || '';
      if (descEl) descEl.value = skill.description || '';
      show($('#sk-mode-wrap'), false);
      show($('#sk-inherit-wrap'), false);
      show($('#sk-type-wrap'), false);
      show($('#sk-interface-wrap'), false);
      show($('#sk-modal'), true);
      return;
    }
    show($('#sk-mode-wrap'), true);
    const baseSel = $('#sk-create-base');
    if (baseSel) {
      const bases = state.items.filter((s) => s.status === 'PUBLISHED');
      baseSel.innerHTML = bases.map((s) =>
        `<option value="${esc(s.id)}">${esc(s.name || s.key)} (${esc(s.skill_type)})</option>`
      ).join('') || '<option value="">Нет опубликованных навыков</option>';
    }
    const modeSel = $('#sk-create-mode');
    if (modeSel) {
      modeSel.onchange = () => {
        const inherit = modeSel.value === 'inherit';
        show($('#sk-inherit-wrap'), inherit);
        show($('#sk-type-wrap'), !inherit);
        show($('#sk-interface-wrap'), !inherit);
      };
      const inherit = modeSel.value === 'inherit';
      show($('#sk-inherit-wrap'), inherit);
      show($('#sk-type-wrap'), !inherit);
      show($('#sk-interface-wrap'), !inherit);
    }
    show($('#sk-modal'), true);
  }

  function closeModal() {
    show($('#sk-modal'), false);
    state.editingId = null;
  }

  async function deleteSkill(id) {
    const item = state.items.find((s) => String(s.id) === String(id));
    if (item && item.immutable) {
      toast('Corporate/Core навыки нельзя удалить');
      return;
    }
    const label = (item && item.name)
      || (state.detail && state.detail.skill && String(state.detail.skill.id) === String(id) && state.detail.skill.name)
      || id;
    if (!window.confirm(`Удалить навык «${label}»?`)) return;
    await fetchJSON(`/skills/${id}`, { method: 'DELETE' });
    toast('Навык удалён');
    if (state.detail && state.detail.skill && String(state.detail.skill.id) === String(id)) {
      backToCatalog();
      return;
    }
    await loadCatalog();
  }

  async function submitModal() {
    const name = ($('#sk-create-name') || {}).value || '';
    const skillType = ($('#sk-create-type') || {}).value || 'TEAM';
    const interfaceKey = ($('#sk-create-interface') || {}).value || '';
    const inputContractKey = ($('#sk-create-input-contract') || {}).value || '';
    const outputContractKey = ($('#sk-create-output-contract') || {}).value || '';
    const description = ($('#sk-create-desc') || {}).value || '';
    const mode = ($('#sk-create-mode') || {}).value || 'new';
    if (!name.trim()) {
      toast('Укажите имя');
      return;
    }
    if (state.modalMode === 'edit' && state.editingId) {
      const detail = await fetchJSON(`/skills/${state.editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), description }),
      });
      closeModal();
      await loadCatalog();
      state.detail = detail;
      show($('#sk-catalog-view'), false);
      show($('#sk-detail-view'), true);
      renderDetail();
      toast('Навык обновлён');
      return;
    }
    let detail;
    if (mode === 'inherit') {
      const baseId = ($('#sk-create-base') || {}).value;
      if (!baseId) {
        toast('Выберите базовый навык');
        return;
      }
      detail = await fetchJSON(`/skills/${baseId}/inherit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          description,
        }),
      });
    } else {
      detail = await fetchJSON('/skills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          skill_type: skillType,
          interface_key: interfaceKey || undefined,
          description,
          input_contract_key: inputContractKey || undefined,
          output_contract_key: outputContractKey || undefined,
        }),
      });
    }
    closeModal();
    state.detail = detail;
    show($('#sk-catalog-view'), false);
    show($('#sk-detail-view'), true);
    renderDetail();
    showTab('overview');
    if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
      window.PlatformUtil.bindEntityLinks($('#sk-tab-content'));
    }
    toast(mode === 'inherit' ? 'Навык унаследован' : 'Навык создан');
  }

  async function inheritCurrent() {
    const detail = state.detail;
    if (!detail || !detail.skill) return;
    if (!detail.published_version) {
      toast('Наследовать можно только от опубликованной версии');
      return;
    }
    const name = prompt('Имя нового навыка (наследник)', `${detail.skill.name} (наследник)`);
    if (!name) return;
    const created = await fetchJSON(`/skills/${detail.skill.id}/inherit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() }),
    });
    state.detail = created;
    renderDetail();
    showTab('overview');
    toast('Создан наследник навыка');
  }

  async function showInterfaces() {
    await openInterfacesView();
  }

  function bindUI() {
    const search = $('#sk-search');
    const typeFilter = $('#sk-type-filter');
    const statusFilter = $('#sk-status-filter');
    if (search) {
      search.oninput = () => {
        state.filters.q = search.value;
        loadCatalog().catch((e) => toast(e.message));
      };
    }
    if (typeFilter) {
      typeFilter.onchange = () => {
        state.filters.skillType = typeFilter.value;
        loadCatalog().catch((e) => toast(e.message));
      };
    }
    if (statusFilter) {
      statusFilter.onchange = () => {
        state.filters.status = statusFilter.value;
        loadCatalog().catch((e) => toast(e.message));
      };
    }

    const ifSearch = $('#sk-if-search');
    const ifSource = $('#sk-if-source-filter');
    if (ifSearch) {
      ifSearch.oninput = () => {
        state.interfaceFilters.q = ifSearch.value;
        renderInterfacesList();
      };
    }
    if (ifSource) {
      ifSource.onchange = () => {
        state.interfaceFilters.source = ifSource.value;
        renderInterfacesList();
      };
    }

    const ctSearch = $('#sk-ct-search');
    const ctKind = $('#sk-ct-kind-filter');
    if (ctSearch) {
      ctSearch.oninput = () => {
        state.contractFilters.q = ctSearch.value;
        renderContractsList();
      };
    }
    if (ctKind) {
      ctKind.onchange = () => {
        state.contractFilters.kind = ctKind.value;
        renderContractsList();
      };
    }

    root()?.querySelectorAll('.sk-if-tabs button').forEach((btn) => {
      btn.onclick = () => showInterfaceTab(btn.dataset.ifTab);
    });

    root()?.querySelectorAll('.sk-tabs button').forEach((b) => {
      b.onclick = () => showTab(b.dataset.tab);
    });

    const actions = [
      ['#sk-btn-back', backToCatalog],
      ['#sk-btn-create', () => openModal('create')],
      ['#sk-btn-interfaces', () => showInterfaces().catch((e) => toast(e.message))],
      ['#sk-if-back', backFromInterfaces],
      ['#sk-if-create', () => openInterfaceModal('create').catch((e) => toast(e.message))],
      ['#sk-if-create-inline', () => openInterfaceModal('create').catch((e) => toast(e.message))],
      ['#sk-if-close-modal', closeInterfaceModal],
      ['#sk-if-cancel-modal', closeInterfaceModal],
      ['#sk-contract-close-modal', closeContractModal],
      ['#sk-contract-close-btn', closeContractModal],
      ['#sk-if-submit-modal', () => submitInterfaceModal().catch((e) => toast(e.message))],
      ['#sk-if-delete-modal', () => {
        if (state.editingInterfaceId) {
          deleteInterface(state.editingInterfaceId).catch((e) => toast(e.message));
        }
      }],
      ['#sk-btn-edit', () => openEditor().catch((e) => toast(e.message))],
      ['#sk-btn-test', () => showTab('tests')],
      ['#sk-btn-inherit', () => inheritCurrent().catch((e) => toast(e.message))],
      ['#sk-btn-create-version', () => createDraft().catch((e) => toast(e.message))],
      ['#sk-editor-back', closeEditor],
      ['#sk-btn-save-draft', () => saveDraft().catch((e) => toast(e.message))],
      ['#sk-btn-validate', () => validateCurrent().catch((e) => toast(e.message))],
      ['#sk-btn-publish', () => publishCurrent().catch((e) => toast(e.message))],
      ['#sk-btn-add-file', () => addPackageEntry('file')],
      ['#sk-btn-add-folder', () => addPackageEntry('folder')],
      ['#sk-btn-delete-entry', () => deleteSelectedEntry().catch((e) => toast(e.message))],
      ['#sk-add-submit', () => submitAddForm().catch((e) => toast(e.message))],
      ['#sk-add-cancel', hideAddForm],
      ['#sk-close-modal', closeModal],
      ['#sk-cancel-modal', closeModal],
      ['#sk-submit-modal', () => submitModal().catch((e) => toast(e.message))],
    ];
    actions.forEach(([sel, fn]) => {
      const el = $(sel);
      if (el) el.onclick = fn;
    });
    const addName = $('#sk-add-name');
    if (addName) {
      addName.onkeydown = (ev) => {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          submitAddForm().catch((e) => toast(e.message));
        } else if (ev.key === 'Escape') {
          hideAddForm();
        }
      };
    }
  }

  async function load(openId, opts) {
    if (!root()) return;
    show($('#sk-catalog-view'), true);
    show($('#sk-interfaces-view'), false);
    show($('#sk-detail-view'), false);
    show($('#sk-editor-view'), false);
    show($('#sk-modal'), false);
    show($('#sk-if-modal'), false);
    show($('#sk-contract-modal'), false);
    bindUI();
    try {
      await loadInterfacesData();
    } catch (_) { /* optional */ }
    await loadCatalog();
    if (openId) {
      const byKey = state.items.find((i) => i.key === openId || String(i.id) === String(openId));
      await openDetail(byKey ? byKey.id : openId);
      if (opts && opts.tab) {
        const tabBtn = root().querySelector(`[data-tab="${opts.tab}"]`);
        if (tabBtn) tabBtn.click();
      }
    }
  }

  window.SkillsModule = { load, openDetail, backToCatalog };
})();
