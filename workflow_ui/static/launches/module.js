/**
 * Запуски — каталог Е2Е сценариев, которые агент может выполнить.
 * Опубликованные, но не запущенные сценарии системой игнорируются.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);
  const CardMenu = () => window.PlatformUtil.cardMenu();

  const state = {
    launches: [],
    available: [],
    metrics: null,
    filters: { search: '', scope: 'launched' },
  };

  function launchMenuActions(launched) {
    const actions = launched
      ? [{ id: 'stop', label: 'Остановить', danger: true }]
      : [{ id: 'launch', label: 'Запустить' }];
    actions.push({ id: 'open-flow', label: 'Сценарий' });
    actions.push({ id: 'open-inspector', label: 'Инспектор' });
    return actions;
  }

  function catalogMenu(id, launched) {
    return CardMenu().markup(id, launchMenuActions(launched));
  }

  function bindCardMenus(scope) {
    CardMenu().bind(scope || root(), (id, action) => {
      handleCardAction(action, id).catch((e) => toast(e.message));
    });
  }

  async function handleCardAction(action, id) {
    if (!id) return;
    const row = state.launches.find((x) => String(x.id) === String(id));
    if (action === 'launch') {
      await launchScenario(id);
      return;
    }
    if (action === 'stop') {
      await stopScenario(id);
      return;
    }
    if (action === 'open-flow') {
      await window.PlatformUtil.navigateTo('flows', { id });
      return;
    }
    if (action === 'open-inspector') {
      const key = row && row.key;
      await window.PlatformUtil.navigateTo('inspector', key ? { id: key } : {});
    }
  }

  function root() {
    return document.getElementById('launches-module');
  }

  function $(sel) {
    const el = root();
    return el ? el.querySelector(sel) : null;
  }

  function show(el, visible) {
    if (!el) return;
    el.classList.toggle('ln-hidden', !visible);
  }

  async function loadCatalog() {
    const q = new URLSearchParams();
    q.set('kind', 'e2e');
    if (state.filters.search) q.set('q', state.filters.search);
    const data = await fetchJSON(`/scenarios?${q.toString()}`);
    const items = (data.items || []).map((x) => ({
      id: x.id,
      key: x.key,
      name: x.name,
      status: x.status,
      launched: x.status === 'launched',
      version: '',
      stages: [],
      owner: '',
      executions_30d: 0,
      success_rate: 0,
    }));
    const launched = items.filter((x) => x.status === 'launched');
    const published = items.filter((x) => x.status === 'published');
    state.available = published;
    state.launches = state.filters.scope === 'all'
      ? items.filter((x) => x.status !== 'draft')
      : launched;
    state.metrics = {
      launched: launched.length,
      published: published.length + launched.length,
      available: published.length,
      ignored: published.length,
    };
    renderMetrics();
    renderTable();
  }

  function renderMetrics() {
    const m = state.metrics || {};
    const map = {
      '#ln-metric-launched': m.launched,
      '#ln-metric-published': m.published,
      '#ln-metric-available': m.available,
      '#ln-metric-ignored': m.ignored,
    };
    Object.entries(map).forEach(([sel, val]) => {
      const el = $(sel);
      if (el) el.textContent = val == null ? '—' : String(val);
    });
    const sub = $('#ln-metric-launched-sub');
    if (sub) sub.textContent = 'Агент выполняет только их';
    const subPub = $('#ln-metric-published-sub');
    if (subPub) subPub.textContent = 'Есть опубликованный snapshot';
    const subAvail = $('#ln-metric-available-sub');
    if (subAvail) subAvail.textContent = 'Можно запустить';
    const subIgn = $('#ln-metric-ignored-sub');
    if (subIgn) subIgn.textContent = 'Система их пропускает';
  }

  function rowsForTable() {
    if (state.filters.scope === 'all') return state.launches;
    return state.launches;
  }

  function renderTable() {
    const body = $('#ln-table-body');
    if (!body) return;
    const rows = rowsForTable();
    if (!rows.length) {
      const empty = state.filters.scope === 'launched'
        ? 'Нет запущенных сценариев. Опубликуйте Е2Е в Сборке и нажмите «+ Запустить сценарий».'
        : 'Опубликованных сценариев нет.';
      body.innerHTML = `<tr><td colspan="6" style="color:var(--ln-muted)">${empty}</td></tr>`;
      return;
    }
    body.innerHTML = rows.map((x) => {
      const stages = (x.stages || []).slice(0, 4).map((s) =>
        `<span class="stage-chip">${esc(s)}</span>`
      ).join('');
      const more = (x.stages || []).length > 4
        ? `<span class="stage-chip">+${(x.stages || []).length - 4}</span>`
        : '';
      const badge = x.launched
        ? '<span class="status-badge launched">Запущен</span>'
        : '<span class="status-badge ignored">Игнорируется</span>';
      return `
        <tr class="ln-row" data-id="${esc(x.id)}" data-launched="${x.launched ? '1' : '0'}">
          <td>
            <span class="scenario-name">${esc(x.name)}</span>
            <span class="scenario-key">${esc(x.key)}${x.version ? ` · ${esc(x.version)}` : ''}</span>
          </td>
          <td><div class="stage-chips">${stages}${more || (stages ? '' : '—')}</div></td>
          <td>${esc(x.owner || '—')}</td>
          <td>${esc(x.executions_30d || 0)}${x.executions_30d ? ` / ${esc(Math.round((x.success_rate || 0) * 100))}%` : ''}</td>
          <td>${badge}</td>
          <td class="table-actions-cell">${catalogMenu(x.id, x.launched)}</td>
        </tr>`;
    }).join('');

    bindCardMenus(body);
  }

  async function launchScenario(id) {
    const card = await fetchJSON(`/scenarios/${id}`);
    await fetchJSON(`/scenarios/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revision: card.revision, status: 'launched' }),
    });
    toast('Сценарий запущен — агент может его выполнять');
    await loadCatalog();
    closeModal();
  }

  async function stopScenario(id) {
    if (!confirm('Остановить сценарий? Агент перестанет его выполнять.')) return;
    const card = await fetchJSON(`/scenarios/${id}`);
    await fetchJSON(`/scenarios/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revision: card.revision, status: 'published' }),
    });
    toast('Сценарий остановлен — система его игнорирует');
    await loadCatalog();
  }

  function openModal() {
    const select = $('#ln-launch-select');
    if (select) {
      const opts = state.available.length
        ? state.available.map((x) =>
          `<option value="${esc(x.id)}">${esc(x.name)} (${esc(x.version || '—')})</option>`
        ).join('')
        : '<option value="">Нет опубликованных сценариев для запуска</option>';
      select.innerHTML = opts;
      select.disabled = !state.available.length;
    }
    const confirmBtn = $('#ln-confirm-launch');
    if (confirmBtn) confirmBtn.disabled = !state.available.length;
    show($('#ln-launch-modal'), true);
  }

  function closeModal() {
    show($('#ln-launch-modal'), false);
  }

  async function confirmLaunch() {
    const select = $('#ln-launch-select');
    const id = select && select.value;
    if (!id) {
      toast('Выберите опубликованный сценарий');
      return;
    }
    await launchScenario(id);
  }

  function bindUI() {
    const search = $('#ln-search');
    if (search) {
      search.oninput = () => {
        state.filters.search = search.value;
        loadCatalog().catch((e) => toast(e.message));
      };
    }
    const scope = $('#ln-scope-filter');
    if (scope) {
      scope.onchange = () => {
        state.filters.scope = scope.value || 'launched';
        loadCatalog().catch((e) => toast(e.message));
      };
    }
    const refresh = $('#ln-btn-refresh');
    if (refresh) refresh.onclick = () => loadCatalog().catch((e) => toast(e.message));
    const start = $('#ln-btn-launch');
    if (start) start.onclick = () => {
      loadCatalog().then(openModal).catch((e) => toast(e.message));
    };
    const close = $('#ln-close-launch');
    const cancel = $('#ln-cancel-launch');
    const confirm = $('#ln-confirm-launch');
    if (close) close.onclick = closeModal;
    if (cancel) cancel.onclick = closeModal;
    if (confirm) confirm.onclick = () => confirmLaunch().catch((e) => toast(e.message));
  }

  async function load() {
    bindUI();
    await loadCatalog();
  }

  window.LaunchesModule = { load, loadCatalog };
})();
