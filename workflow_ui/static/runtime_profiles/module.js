/**
 * Профили исполнения — Catalog / Detail / Editor / Effective preview.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const LIMIT_LABELS = {
    maxExecutionSeconds: 'Max execution seconds',
    maxOutputTokens: 'Max output tokens',
    maxRetries: 'Max retries',
    maxConcurrentRuns: 'Max concurrent runs',
  };

  const state = {
    items: [],
    metrics: null,
    detail: null,
    filters: { search: '', type: '', provider: '', status: '' },
    editorSection: 'general',
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
      toast('Профиль не выбран');
      return;
    }
    if (action === 'edit') {
      if (!state.detail || String(state.detail.profile?.id) !== String(id)) {
        await openDetail(id);
      }
      openEditor();
      return;
    }
    if (action === 'delete') {
      await deleteProfile(id);
    }
  }

  function root() {
    return document.getElementById('runtime-profiles-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('rp-hidden', !visible);
  }

  function statusClass(status) {
    const s = (status || '').toLowerCase();
    if (s === 'active') return 'active-status';
    if (s === 'degraded') return 'degraded-status';
    return 'draft-status';
  }

  function val(sel) {
    const el = $(sel);
    return el ? el.value : '';
  }

  function setVal(sel, value) {
    const el = $(sel);
    if (!el) return;
    el.value = value == null ? '' : String(value);
  }

  function parseCsv(text) {
    return String(text || '')
      .split(/[,;\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function csv(list) {
    return (list || []).join(', ');
  }

  function editableVersion(detail) {
    if (!detail) return null;
    return detail.draft_version || detail.current_version || null;
  }

  function dlRows(pairs) {
    return pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v == null || v === '' ? '—' : v)}</dd>`).join('');
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    if (state.filters.search) q.set('search', state.filters.search);
    if (state.filters.type) q.set('type', state.filters.type);
    if (state.filters.provider) q.set('provider', state.filters.provider);
    if (state.filters.status) q.set('status', state.filters.status);
    const data = await fetchJSON(`/runtime-profiles?${q.toString()}`);
    state.items = data.runtime_profiles || [];
    state.metrics = data.metrics || null;
    renderMetrics();
    renderCards();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const healthy = m.total_providers
      ? `${m.healthy_providers}/${m.total_providers}`
      : String(m.healthy_providers || '—');
    const map = {
      '#rp-metric-active': m.active_profiles,
      '#rp-metric-healthy': healthy,
      '#rp-metric-runs': m.runs_30d,
    };
    Object.entries(map).forEach(([sel, v]) => {
      const el = $(sel);
      if (el) el.textContent = v == null ? '—' : String(v);
    });
  }

  function renderCards() {
    const grid = $('#rp-cards');
    if (!grid) return;
    if (!state.items.length) {
      grid.innerHTML = '<p style="color:var(--rp-muted)">Профили исполнения не найдены</p>';
      return;
    }
    grid.innerHTML = state.items.map((x) => `
      <article class="rp-card" data-id="${esc(x.id)}" tabindex="0" role="button">
        <div class="card-head-row">
          <span class="rp-status ${statusClass(x.status)}">${esc(x.status)}</span>
          ${catalogMenu(x.id)}
        </div>
        <h3>${esc(x.name)}</h3>
        <p>${esc(x.description || '')}</p>
        <div class="rp-badges">
          <span class="rp-badge">${esc(x.provider)}</span>
          <span class="rp-badge">${esc(x.model)}</span>
          <span class="rp-badge">${esc(x.sandbox)}</span>
        </div>
        <hr />
        <small>${esc(x.profile_type)} · ${esc(x.supervision)} · ${esc(x.runs_30d)} запусков</small>
      </article>`).join('');
    bindCardMenus(grid);
    grid.querySelectorAll('.rp-card').forEach((card) => {
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
    state.detail = await fetchJSON(`/runtime-profiles/${id}`);
    show($('#rp-drawer'), true);
    renderDetail();
    showTab('overview');
  }

  function closeDrawer() {
    show($('#rp-drawer'), false);
    state.detail = null;
  }

  function renderDetail() {
    const detail = state.detail;
    if (!detail) return;
    const profile = detail.profile || {};
    const ver = detail.current_version || detail.draft_version || {};
    const name = $('#rp-drawer-name');
    if (name) name.textContent = profile.name || '';
    const desc = $('#rp-description');
    if (desc) desc.textContent = profile.description || '';

    const meta = $('#rp-meta');
    if (meta) {
      meta.innerHTML = dlRows([
        ['Тип', ver.profile_type],
        ['Провайдер', ver.provider],
        ['Модель', ver.model],
        ['Версия', ver.semantic_version ? `v${ver.semantic_version}` : '—'],
        ['Владелец', profile.owner_team],
        ['Здоровье', profile.health_status],
        ['Запуски', profile.runs_30d],
      ]);
    }

    const health = $('#rp-health');
    const h = detail.health || {};
    if (health) {
      health.innerHTML = `
        <div class="rp-health-row"><span>Провайдер</span><b class="rp-ok">${esc(h.provider || '—')}</b></div>
        <div class="rp-health-row"><span>Модель</span><b class="rp-ok">${esc(h.model || '—')}</b></div>
        <div class="rp-health-row"><span>Секрет</span><b class="rp-ok">${esc(h.secret || '—')}</b></div>`;
    }

    const runtime = $('#rp-runtime-grid');
    const eff = detail.effective_runtime || {};
    if (runtime) {
      runtime.innerHTML = `
        <div><small>Провайдер</small><b>${esc(eff.provider)}</b></div>
        <div><small>Модель</small><b>${esc(eff.model)}</b></div>
        <div><small>Песочница</small><b>${esc(eff.sandbox)}</b></div>
        <div><small>Надзор</small><b>${esc(eff.supervision)}</b></div>`;
    }

    const providerBody = $('#rp-provider-body');
    if (providerBody) {
      providerBody.innerHTML = dlRows([
        ['Провайдер', ver.provider],
        ['Регион', ver.region],
        ['Сеть', ver.network_policy],
        ['Ссылка на секрет', ver.secret_ref || '(workspace default)'],
      ]);
    }

    const gen = ver.generation_config || {};
    const modelBody = $('#rp-model-body');
    if (modelBody) {
      modelBody.innerHTML = dlRows([
        ['Модель', ver.model],
        ['Температура', gen.temperature],
        ['Max output tokens', gen.maxOutputTokens],
      ]);
    }

    const limitsBody = $('#rp-limits-body');
    if (limitsBody) {
      const limits = ver.limits || {};
      const pairs = Object.keys(limits).length
        ? Object.entries(limits).map(([k, v]) => [LIMIT_LABELS[k] || k, v])
        : [['Лимиты', 'не заданы']];
      limitsBody.innerHTML = dlRows(pairs);
    }

    const securityBody = $('#rp-security-body');
    if (securityBody) {
      const sc = ver.sandbox_config || {};
      securityBody.innerHTML = dlRows([
        ['Песочница', ver.sandbox],
        ['Надзор', ver.supervision],
        ['Сеть', ver.network_policy],
        ['Read-only root FS', sc.readOnlyRootFilesystem == null ? '—' : (sc.readOnlyRootFilesystem ? 'Да' : 'Нет')],
        ['Ephemeral', sc.ephemeral == null ? '—' : (sc.ephemeral ? 'Да' : 'Нет')],
      ]);
    }

    const caps = $('#rp-capabilities');
    if (caps) {
      const policy = (eff.capabilities || ver.capabilities || {});
      const allow = (policy.allow || []).map((c) => `<span class="rp-badge">${esc(c)}</span>`).join('');
      const deny = (policy.deny || []).map((c) => `<span class="rp-badge">${esc(c)} (deny)</span>`).join('');
      const approval = (policy.approval_required || []).map((c) => `<span class="rp-badge">${esc(c)} (согласование)</span>`).join('');
      caps.innerHTML = `${allow}${deny}${approval}` || '<span style="color:var(--rp-muted)">Нет способностей</span>';
    }

    const fallbackBody = $('#rp-fallback-body');
    if (fallbackBody) {
      const key = ver.fallback_profile_key || eff.fallback;
      if (!key) {
        fallbackBody.innerHTML = '<p style="color:var(--rp-muted)">Резервный профиль не задан</p>';
      } else {
        const match = state.items.find((x) => x.key === key);
        fallbackBody.innerHTML = `
          <dl>${dlRows([['Ключ', key], ['Название', match ? match.name : '—']])}</dl>
          ${match ? `<button type="button" class="rp-btn secondary small" id="rp-open-fallback" data-id="${esc(match.id)}">Открыть профиль</button>` : ''}`;
        const btn = $('#rp-open-fallback');
        if (btn) btn.onclick = () => openDetail(btn.dataset.id);
      }
    }

    renderVersionsList();

    const menuHost = $('#rp-drawer-menu');
    if (menuHost && profile.id) {
      menuHost.innerHTML = catalogMenu(profile.id);
      bindCardMenus(menuHost);
    }
  }

  function renderVersionsList() {
    const detail = state.detail;
    const versions = $('#rp-versions-list');
    if (!versions || !detail) return;
    const list = detail.versions || [];
    if (!list.length) {
      versions.innerHTML = '<p style="color:var(--rp-muted)">Нет версий</p>';
      return;
    }
    versions.innerHTML = list.map((v) => `
      <div class="rp-version-row" data-id="${esc(v.id)}">
        <div>
          <b>v${esc(v.semantic_version)}</b>
          <span class="rp-badge">${esc(v.status)}</span>
          <small style="color:var(--rp-muted);margin-left:6px">${esc(v.provider)} · ${esc(v.model)}</small>
        </div>
        ${v.status === 'DRAFT' ? `<button type="button" class="rp-btn small rp-activate-ver" data-id="${esc(v.id)}">Активировать</button>` : ''}
      </div>`).join('');
    versions.querySelectorAll('.rp-activate-ver').forEach((btn) => {
      btn.onclick = () => activateVersion(btn.dataset.id).catch((e) => toast(e.message));
    });
  }

  function showTab(tab) {
    root()?.querySelectorAll('.rp-tabs button').forEach((b) => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    ['overview', 'provider', 'model', 'limits', 'security', 'capabilities', 'fallback', 'versions'].forEach((t) => {
      show($(`#rp-tab-${t}`), t === tab);
    });
  }

  function openModal() { show($('#rp-modal'), true); }
  function closeModal() { show($('#rp-modal'), false); }

  function showEditorSection(section) {
    state.editorSection = section;
    root()?.querySelectorAll('.rp-editor-nav button').forEach((b) => {
      b.classList.toggle('active', b.dataset.section === section);
    });
    root()?.querySelectorAll('.rp-ed-section').forEach((block) => {
      show(block, block.dataset.section === section);
    });
  }

  function fillFallbackOptions(selected) {
    const sel = $('#rp-ed-fallback');
    if (!sel) return;
    const profile = (state.detail && state.detail.profile) || {};
    const options = ['<option value="">— нет —</option>']
      .concat(state.items
        .filter((x) => x.key !== profile.key)
        .map((x) => `<option value="${esc(x.key)}"${x.key === selected ? ' selected' : ''}>${esc(x.name)} (${esc(x.key)})</option>`));
    sel.innerHTML = options.join('');
  }

  function openEditor() {
    const profile = (state.detail && state.detail.profile) || {};
    const ver = editableVersion(state.detail) || {};
    const title = $('#rp-editor-title');
    if (title) {
      title.textContent = profile.name
        ? `${profile.name} · ${ver.status === 'DRAFT' ? `Черновик ${ver.semantic_version || '—'}` : `v${ver.semantic_version || '—'}`}`
        : 'Редактор профиля исполнения';
    }
    fillEditorForm(profile, ver);
    showEditorSection('general');
    updateEditorPreview();
    show($('#rp-editor'), true);
  }

  function closeEditor() { show($('#rp-editor'), false); }

  function fillEditorForm(profile, ver) {
    if (!ver) return;
    const gen = ver.generation_config || {};
    const limits = ver.limits || {};
    const sc = ver.sandbox_config || {};
    const caps = ver.capabilities || {};
    setVal('#rp-ed-name', profile.name);
    setVal('#rp-ed-description', profile.description);
    setVal('#rp-ed-type', ver.profile_type || 'PRODUCTION');
    setVal('#rp-ed-supervision', ver.supervision || 'SUPERVISED');
    setVal('#rp-ed-provider', ver.provider);
    setVal('#rp-ed-region', ver.region || 'ru-central');
    setVal('#rp-ed-network', ver.network_policy || 'ALLOW_CAPABILITY_GATEWAY_ONLY');
    setVal('#rp-ed-model', ver.model);
    setVal('#rp-ed-temp', gen.temperature ?? 0.2);
    setVal('#rp-ed-max-tokens', gen.maxOutputTokens ?? 16000);
    setVal('#rp-ed-max-exec', limits.maxExecutionSeconds ?? 1200);
    setVal('#rp-ed-limit-tokens', limits.maxOutputTokens ?? 16000);
    setVal('#rp-ed-max-retries', limits.maxRetries ?? 3);
    setVal('#rp-ed-max-concurrent', limits.maxConcurrentRuns ?? 4);
    setVal('#rp-ed-sandbox', ver.sandbox || 'CONTAINER');
    setVal('#rp-ed-readonly-fs', sc.readOnlyRootFilesystem === false ? 'false' : 'true');
    setVal('#rp-ed-ephemeral', sc.ephemeral === false ? 'false' : 'true');
    setVal('#rp-ed-cap-allow', csv(caps.allow));
    setVal('#rp-ed-cap-deny', csv(caps.deny));
    setVal('#rp-ed-cap-approval', csv(caps.approval_required));
    setVal('#rp-ed-secret', ver.secret_ref || '');
    fillFallbackOptions(ver.fallback_profile_key || '');
  }

  function collectEditorPayload() {
    return {
      name: val('#rp-ed-name').trim(),
      description: val('#rp-ed-description'),
      profile_type: val('#rp-ed-type'),
      supervision: val('#rp-ed-supervision'),
      provider: val('#rp-ed-provider'),
      region: val('#rp-ed-region'),
      network_policy: val('#rp-ed-network'),
      model: val('#rp-ed-model'),
      temperature: Number(val('#rp-ed-temp') || 0),
      maxOutputTokens: Number(val('#rp-ed-max-tokens') || 0),
      limits: {
        maxExecutionSeconds: Number(val('#rp-ed-max-exec') || 0),
        maxOutputTokens: Number(val('#rp-ed-limit-tokens') || 0),
        maxRetries: Number(val('#rp-ed-max-retries') || 0),
        maxConcurrentRuns: Number(val('#rp-ed-max-concurrent') || 0),
      },
      sandbox: val('#rp-ed-sandbox'),
      sandbox_config: {
        readOnlyRootFilesystem: val('#rp-ed-readonly-fs') === 'true',
        ephemeral: val('#rp-ed-ephemeral') === 'true',
      },
      capabilities: {
        allow: parseCsv(val('#rp-ed-cap-allow')),
        deny: parseCsv(val('#rp-ed-cap-deny')),
        approval_required: parseCsv(val('#rp-ed-cap-approval')),
      },
      secret_ref: val('#rp-ed-secret'),
      fallback_profile_key: val('#rp-ed-fallback') || null,
    };
  }

  function updateEditorPreview() {
    const pre = $('#rp-ed-json');
    const box = $('#rp-ed-validation');
    if (!pre) return;
    const payload = collectEditorPayload();
    pre.textContent = JSON.stringify({
      provider: payload.provider,
      model: payload.model,
      sandbox: payload.sandbox,
      supervision: payload.supervision,
      network: payload.network_policy,
      capabilities: payload.capabilities,
      secret_ref: payload.secret_ref,
      limits: payload.limits,
      fallback: payload.fallback_profile_key,
      region: payload.region,
      generation_config: {
        temperature: payload.temperature,
        maxOutputTokens: payload.maxOutputTokens,
      },
    }, null, 2);

    const report = (state.detail && state.detail.validation) || {};
    if (box) {
      if (report.valid === false && (report.errors || []).length) {
        box.textContent = `✗ ${(report.errors || []).map((e) => e.message || e).join('; ')}`;
        box.className = 'rp-okbox warn';
      } else if ((report.warnings || []).length) {
        box.textContent = `⚠ ${(report.warnings || []).map((w) => w.message || w).join('; ')}`;
        box.className = 'rp-okbox warn';
      } else {
        box.textContent = '✓ Нет блокирующих проблем';
        box.className = 'rp-okbox';
      }
    }
  }

  async function createProfile() {
    const name = ($('#rp-new-name') || {}).value || '';
    const type = ($('#rp-new-type') || {}).value || 'PRODUCTION';
    const provider = ($('#rp-new-provider') || {}).value || 'QWEN_CODE_CLI';
    if (!name.trim()) {
      toast('Укажите имя');
      return;
    }
    const detail = await fetchJSON('/runtime-profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), type, provider }),
    });
    closeModal();
    await loadCatalog();
    state.detail = detail;
    show($('#rp-drawer'), true);
    renderDetail();
    toast('Черновик профиля исполнения создан');
  }

  async function deleteProfile(id) {
    const item = state.items.find((x) => String(x.id) === String(id));
    const label = (item && item.name)
      || (state.detail && state.detail.profile && String(state.detail.profile.id) === String(id) && state.detail.profile.name)
      || id;
    if (!window.confirm(`Удалить профиль «${label}»?`)) return;
    await fetchJSON(`/runtime-profiles/${id}`, { method: 'DELETE' });
    if (state.detail && state.detail.profile && String(state.detail.profile.id) === String(id)) {
      closeDrawer();
    }
    state.detail = null;
    await loadCatalog();
    toast('Профиль удалён');
  }

  async function saveDraft() {
    const id = state.detail && state.detail.profile && state.detail.profile.id;
    if (!id) return;
    const payload = collectEditorPayload();
    if (!payload.name) {
      toast('Укажите название');
      return;
    }
    if (!state.detail.draft_version && state.detail.current_version && state.detail.current_version.status === 'ACTIVE') {
      state.detail = await fetchJSON(`/runtime-profiles/${id}/draft`, { method: 'POST' });
    }
    state.detail = await fetchJSON(`/runtime-profiles/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    renderDetail();
    fillEditorForm(state.detail.profile, editableVersion(state.detail));
    updateEditorPreview();
    await loadCatalog();
    toast('Черновик сохранён');
  }

  async function createDraftFromDetail() {
    const id = state.detail && state.detail.profile && state.detail.profile.id;
    if (!id) return;
    state.detail = await fetchJSON(`/runtime-profiles/${id}/draft`, { method: 'POST' });
    renderDetail();
    toast('Черновик создан');
  }

  async function activateVersion(versionId) {
    const id = state.detail && state.detail.profile && state.detail.profile.id;
    if (!id) return;
    const path = versionId
      ? `/runtime-profiles/${id}/versions/${versionId}/activate`
      : `/runtime-profiles/${id}/activate`;
    state.detail = await fetchJSON(path, { method: 'POST' });
    renderDetail();
    fillEditorForm(state.detail.profile, editableVersion(state.detail) || state.detail.current_version);
    updateEditorPreview();
    await loadCatalog();
    toast('Версия активирована');
  }

  async function testConnection() {
    const id = state.detail && state.detail.profile && state.detail.profile.id;
    if (!id) return;
    const result = await fetchJSON(`/runtime-profiles/${id}/test`, { method: 'POST' });
    toast(result.message || (result.ok ? 'Соединение OK' : 'Соединение не удалось'));
  }

  async function validateProfile() {
    const id = state.detail && state.detail.profile && state.detail.profile.id;
    if (!id) return;
    const result = await fetchJSON(`/runtime-profiles/${id}/validate`, { method: 'POST' });
    toast(result.valid ? 'Проверка пройдена' : `Проверка не пройдена: ${(result.errors || []).map((e) => e.message || e).join(', ')}`);
    state.detail = await fetchJSON(`/runtime-profiles/${id}`);
    updateEditorPreview();
  }

  function bindUI() {
    if (root()?.dataset.bound === '1') return;
    if (root()) root().dataset.bound = '1';

    const search = $('#rp-search');
    const type = $('#rp-type-filter');
    const provider = $('#rp-provider-filter');
    if (search) search.oninput = () => { state.filters.search = search.value; loadCatalog().catch((e) => toast(e.message)); };
    if (type) type.onchange = () => { state.filters.type = type.value; loadCatalog().catch((e) => toast(e.message)); };
    if (provider) provider.onchange = () => { state.filters.provider = provider.value; loadCatalog().catch((e) => toast(e.message)); };

    const createBtn = $('#rp-btn-create');
    if (createBtn) createBtn.onclick = openModal;

    const closeDrawerBtn = $('#rp-close-drawer');
    if (closeDrawerBtn) closeDrawerBtn.onclick = closeDrawer;
    root()?.querySelectorAll('.rp-tabs button').forEach((b) => {
      b.onclick = () => showTab(b.dataset.tab);
    });
    const editBtn = $('#rp-edit-profile');
    if (editBtn) editBtn.onclick = openEditor;

    const createDraftBtn = $('#rp-btn-create-draft');
    if (createDraftBtn) createDraftBtn.onclick = () => createDraftFromDetail().catch((e) => toast(e.message));

    const closeModalBtn = $('#rp-close-modal');
    const cancelModal = $('#rp-cancel-modal');
    const saveBtn = $('#rp-save-profile');
    if (closeModalBtn) closeModalBtn.onclick = closeModal;
    if (cancelModal) cancelModal.onclick = closeModal;
    if (saveBtn) saveBtn.onclick = () => createProfile().catch((e) => toast(e.message));

    const closeEditorBtn = $('#rp-close-editor');
    const testBtn = $('#rp-test');
    const validateBtn = $('#rp-validate');
    const saveDraftBtn = $('#rp-save-draft');
    const activateBtn = $('#rp-activate');
    if (closeEditorBtn) closeEditorBtn.onclick = closeEditor;
    if (testBtn) testBtn.onclick = () => testConnection().catch((e) => toast(e.message));
    if (validateBtn) validateBtn.onclick = () => validateProfile().catch((e) => toast(e.message));
    if (saveDraftBtn) saveDraftBtn.onclick = () => saveDraft().catch((e) => toast(e.message));
    if (activateBtn) activateBtn.onclick = () => {
      const draft = state.detail && state.detail.draft_version;
      activateVersion(draft && draft.id).catch((e) => toast(e.message));
    };

    root()?.querySelectorAll('.rp-editor-nav button').forEach((b) => {
      b.onclick = () => showEditorSection(b.dataset.section);
    });
    root()?.querySelectorAll('.rp-editor-form input, .rp-editor-form select, .rp-editor-form textarea').forEach((el) => {
      el.addEventListener('input', updateEditorPreview);
      el.addEventListener('change', updateEditorPreview);
    });
  }

  async function load(id) {
    bindUI();
    await loadCatalog();
    if (id) await openDetail(id);
  }

  window.RuntimeProfilesModule = { load, openDetail };
})();
