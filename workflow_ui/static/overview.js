/*
 * Overview / Dashboard — Build · Run · Govern snapshot.
 * DOM: overview-stats metrics, overview-executions, overview-checkpoints,
 * overview-playbooks, overview-skills, overview-build, overview-controls,
 * overview-integrations, overview-govern, overview-resources, overview-health.
 */
(function () {
  'use strict';

  const esc = (v) => window.PlatformUtil.esc(v);
  const toast = (m) => window.PlatformUtil.toast(m);
  const fetchJSON = (path, options) => window.PlatformUtil.fetchJSON(path, options);


  const STATUS_LABELS = {
    active: 'Активен',
    draft: 'Черновик',
    deprecated: 'Устарел',
    received: 'Получен',
    compiling: 'Компиляция',
    running: 'Выполняется',
    waiting_approval: 'Ожидает',
    blocked: 'Заблокирован',
    failed: 'Ошибка',
    completed: 'Завершён',
    cancelled: 'Отменён',
    paused: 'Пауза',
    online: 'Онлайн',
    degraded: 'Деградация',
    offline: 'Офлайн',
    pending: 'Ожидает',
  };


  function target(id) {
    return document.getElementById(id);
  }

  function badge(status) {
    const key = status || 'draft';
    return `<span class="ov-badge status-${esc(key)}">${esc(STATUS_LABELS[key] || key)}</span>`;
  }

  function relativeTime(value) {
    if (!value) return '—';
    const delta = Math.max(0, Date.now() - new Date(value).getTime());
    const minutes = Math.floor(delta / 60000);
    if (minutes < 1) return 'только что';
    if (minutes < 60) return `${minutes} мин назад`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ч назад`;
    return `${Math.floor(hours / 24)} дн назад`;
  }

  function sparkline(series) {
    if (!series || !series.length) return '';
    const min = Math.min(...series);
    const max = Math.max(...series);
    const span = max - min || 1;
    const points = series.map((value, index) => {
      const x = series.length === 1 ? 50 : index * (100 / (series.length - 1));
      const y = 22 - ((value - min) / span) * 18;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return `<svg class="ov-sparkline" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true"><polyline points="${points}"></polyline></svg>`;
  }

  function navigate(view, opts) {
    if (window.PlatformUtil && typeof window.PlatformUtil.navigateTo === 'function') {
      return window.PlatformUtil.navigateTo(view, opts || {});
    }
    const nav = document.querySelector(`.global-nav [data-view="${view}"]`);
    if (nav) nav.click();
  }

  function renderStats(summary) {
    const s = summary || {};
    const set = (id, value, sub) => {
      const el = target(id);
      if (el) el.textContent = value == null ? '—' : String(value);
      const subEl = target(`${id}-sub`);
      if (subEl && sub) subEl.textContent = sub;
    };
    set('ov-metric-active', s.executions_active ?? 0, `${s.executions_total ?? 0} всего · ${Math.round((s.success_rate || 0) * 100)}% успешно`);
    set('ov-metric-checkpoints', s.pending_approvals ?? 0, 'Ожидают решения человека');
    set('ov-metric-playbooks', s.scenarios_published ?? s.flows_active ?? 0, `${s.scenarios_total ?? s.flows_total ?? 0} в каталоге`);
    set('ov-metric-capabilities', s.capabilities_active ?? 0, `${s.capabilities_total ?? 0} зарегистрировано`);
  }

  function renderExecutions(items) {
    const el = target('overview-executions');
    if (!el) return;
    el.innerHTML = items.length
      ? items.slice(0, 6).map((item) => `
        <button type="button" class="ov-row ov-row-btn" data-execution-id="${esc(item.id)}">
          <div>
            <strong>${esc(item.external_work_item_id || item.id)}</strong>
            <small>${esc(item.playbook_name || '—')} · ${esc(item.external_source || '')}</small>
          </div>
          <div class="ov-row-meta">${badge(item.status)}<span>${esc(relativeTime(item.started_at))}</span></div>
        </button>`).join('')
      : '<div class="ov-empty">Недавних запусков нет</div>';
    el.querySelectorAll('[data-execution-id]').forEach((row) => {
      row.onclick = () => {
        navigate('inspector', { id: row.dataset.executionId });
      };
    });
  }

  function renderCheckpoints(pending, waitingCount) {
    const el = target('overview-checkpoints');
    if (!el) return;
    const items = pending || [];
    if (!items.length) {
      el.innerHTML = waitingCount
        ? `<div class="ov-empty">${esc(waitingCount)} согласований ожидают — откройте очередь</div>`
        : '<div class="ov-empty">Нет ожидающих согласований</div>';
      return;
    }
    el.innerHTML = items.slice(0, 5).map((item) => `
      <button type="button" class="ov-row ov-row-btn" data-view-target="checkpoints">
        <div>
          <strong>${esc(item.subject || item.type || 'Утверждение')}</strong>
          <small>${esc(item.external_work_item_id || item.execution_id || '')}</small>
        </div>
        ${badge(item.status || 'pending')}
      </button>`).join('');
  }

  function renderPlaybooks(items) {
    const el = target('overview-playbooks');
    if (!el) return;
    el.innerHTML = items.length
      ? `<table class="ov-table"><thead><tr><th>Название</th><th>Семейство</th><th>Вер.</th><th>Статус</th></tr></thead><tbody>
        ${items.slice(0, 5).map((item) => `<tr>
          <td><strong>${esc(item.name || item.key)}</strong><span class="ov-sub">${esc(item.key || '')}</span></td>
          <td>${esc(item.family || item.pdlc_family || '—')}</td>
          <td>v${esc(item.version || '1')}</td>
          <td>${badge(item.status || 'draft')}</td>
        </tr>`).join('')}
      </tbody></table>`
      : '<div class="ov-empty">Пока нет сценариев</div>';
  }

  function renderSkills(items) {
    const el = target('overview-skills');
    if (!el) return;
    el.innerHTML = items.length
      ? items.slice(0, 8).map((item) => `
        <article class="ov-mini">
          <span class="ov-logo">${esc((item.name || item.key || 'SK').slice(0, 2))}</span>
          <div>
            <strong>${esc(item.name || item.key)}</strong>
            <small>${esc(item.implements || item.interface_ref || item.interface_key || 'interface')} · v${esc(item.version || '1')}</small>
          </div>
          <span class="ov-dot ${esc(item.status || 'draft')}"></span>
        </article>`).join('')
      : '<div class="ov-empty">Навыков пока нет</div>';
  }

  function renderBuildTiles(summary, data) {
    const el = target('overview-build');
    if (!el) return;
    const s = summary || {};
    const tiles = [
      { view: 'flows', label: 'Е2Е Сценарии', value: s.flows_active ?? (data.flows || []).filter((f) => f.status === 'active').length, hint: `${s.flows_total ?? (data.flows || []).length} всего` },
      { view: 'knowledge', label: 'Знания', value: s.knowledge_spaces ?? (data.knowledge_spaces || []).length, hint: 'Области' },
      { view: 'runtime-profiles', label: 'Профили исполнения', value: s.runtime_profiles ?? (data.runtime_profiles || []).length, hint: 'Конфиги LLM' },
      { view: 'rules', label: 'Правила (rules)', value: s.rules_total ?? 0, hint: 'Наборы правил' },
    ];
    el.innerHTML = tiles.map((t) => `
      <button type="button" class="ov-tile" data-view-target="${esc(t.view)}">
        <strong>${esc(t.value)}</strong>
        <span>${esc(t.label)}</span>
        <small>${esc(t.hint)}</small>
      </button>`).join('');
  }

  function renderControls(items, waitingApprovals) {
    const el = target('overview-controls');
    if (!el) return;
    const warnings = (items || []).filter((item) =>
      ['warning', 'warn', 'blocked', 'failed', 'DISABLED'].includes(String(item.status || ''))
      || item.warning
      || item.violations_count
    );
    const visible = warnings.length ? warnings : (items || []).slice(0, 4);
    const approval = Number(waitingApprovals || 0) > 0
      ? `<div class="ov-row"><span class="ov-icon">!</span><div><strong>Ожидают решения человека</strong><small>Откройте Согласования</small></div><span class="ov-chip">${esc(waitingApprovals)}</span></div>`
      : '';
    el.innerHTML = approval + (visible.length
      ? visible.map((item) => `
        <div class="ov-row">
          <span class="ov-icon">◉</span>
          <div>
            <strong>${esc(item.name || item.key)}</strong>
            <small>${esc(item.warning || item.description || `${item.authority || 'corporate'} · ${item.enforcement || item.severity || 'gate'}`)}</small>
          </div>
          <span class="ov-chip">${esc(item.status || item.enforcement || 'active')}</span>
        </div>`).join('')
      : '<div class="ov-empty">Предупреждений по контролям нет</div>');
  }

  function renderIntegrations(items) {
    const el = target('overview-integrations');
    if (!el) return;
    el.innerHTML = items.length
      ? items.slice(0, 6).map((item) => `
        <article class="ov-mini">
          <span class="ov-logo">${esc((item.name || item.key || 'IN').slice(0, 2))}</span>
          <div>
            <strong>${esc(item.name || item.key)}</strong>
            <small>${esc(item.key)} · ${(item.capabilities || []).length} способностей</small>
          </div>
          <span class="ov-dot ${esc(item.status || 'online')}"></span>
        </article>`).join('')
      : '<div class="ov-empty">Интеграций нет</div>';
  }

  function renderGovernTiles(summary) {
    const el = target('overview-govern');
    if (!el) return;
    const s = summary || {};
    const tiles = [
      { view: 'capabilities-platform', label: 'Способности', value: s.capabilities_active ?? 0, hint: `${s.capabilities_total ?? 0} зарегистрировано` },
      { view: 'integrations', label: 'Интеграции', value: s.integrations_online ?? 0, hint: `${s.integrations_total ?? 0} всего` },
      { view: 'controls', label: 'Контроли', value: s.control_packs ?? 0, hint: 'Пакеты / гейты' },
      { view: 'audit', label: 'События аудита', value: s.audit_events ?? 0, hint: 'Записи журнала' },
    ];
    el.innerHTML = tiles.map((t) => `
      <button type="button" class="ov-tile" data-view-target="${esc(t.view)}">
        <strong>${esc(t.value)}</strong>
        <span>${esc(t.label)}</span>
        <small>${esc(t.hint)}</small>
      </button>`).join('');
  }

  function bindNavigation(root) {
    (root || document).querySelectorAll('[data-view-target]').forEach((button) => {
      if (button.dataset.bound === '1') return;
      button.dataset.bound = '1';
      button.addEventListener('click', () => navigate(button.dataset.viewTarget));
    });
    if (window.PlatformUtil && window.PlatformUtil.bindEntityLinks) {
      window.PlatformUtil.bindEntityLinks(root || document);
    }
  }

  window.renderOverview = function renderOverview(data, summary, pending) {
    data = data || {};
    summary = summary || {};
    renderStats(summary);
    renderExecutions(data.recent_executions || []);
    renderCheckpoints((pending && pending.pending_approvals) || [], summary.pending_approvals || data.waiting_approvals_count);
    renderPlaybooks(data.flows || data.playbooks || []);
    renderSkills(data.skills || []);
    renderBuildTiles(summary, data);
    renderControls(data.controls || [], summary.pending_approvals || data.waiting_approvals_count);
    renderIntegrations(data.integrations || []);
    renderGovernTiles(summary);
    bindNavigation(target('overview-module'));
    const updated = target('overview-updated');
    if (updated) {
      updated.textContent = `Обновлено ${new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
    }
  };

  window.loadOverview = async function loadOverview() {
    try {
      const [overviewRes, summaryRes, pendingRes] = await Promise.all([
        fetch('/api/v1/overview'),
        fetch('/api/v1/dashboard/summary'),
        fetch('/api/v1/dashboard/pending-actions'),
      ]);
      if (!overviewRes.ok) throw new Error(`HTTP ${overviewRes.status}`);
      const data = await overviewRes.json();
      const summary = summaryRes.ok ? await summaryRes.json() : {};
      const pending = pendingRes.ok ? await pendingRes.json() : { pending_approvals: [] };
      window.renderOverview(data, summary, pending);
      return data;
    } catch (error) {
      const updated = target('overview-updated');
      if (updated) updated.textContent = 'Не удалось обновить';
      console.error('Overview load failed:', error);
      return null;
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    bindNavigation(document);
    const refresh = target('ov-refresh-btn');
    if (refresh) refresh.onclick = () => window.loadOverview();
  });
})();
