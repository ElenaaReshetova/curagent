/**
 * Shared helpers for platform UI modules.
 */
(function (global) {
  'use strict';

  function esc(value) {
    const node = document.createElement('div');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
  }

  function toast(message) {
    const el = document.getElementById('toast');
    if (!el) {
      console.log(message);
      return;
    }
    el.textContent = message;
    el.classList.remove('hidden');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add('hidden'), 2800);
  }
  // Back-compat for any leftover window.toast callers
  global.toast = toast;

  class ApiError extends Error {
    constructor(message, { status, detail, body } = {}) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.detail = detail;
      this.body = body;
    }
  }

  async function fetchJSON(path, options) {
    const url = path.startsWith('/api/') || path.startsWith('http') ? path : `/api/v1${path.startsWith('/') ? path : `/${path}`}`;
    let response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      throw new ApiError(err.message || 'Network error', { status: 0, detail: { code: 'OFFLINE' } });
    }
    if (!response.ok) {
      const text = await response.text();
      let parsed = null;
      let message = text || response.statusText;
      try {
        parsed = JSON.parse(text);
        const detail = parsed.detail;
        if (parsed.error && parsed.error.message) message = parsed.error.message;
        else if (typeof detail === 'string') message = detail;
        else if (detail && typeof detail === 'object') {
          message = (detail.error && detail.error.message) || detail.message || detail.code || message;
        } else {
          message = parsed.message || message;
        }
      } catch (_) { /* plain */ }
      throw new ApiError(
        typeof message === 'string' ? message : JSON.stringify(message),
        {
          status: response.status,
          detail: parsed && parsed.detail != null ? parsed.detail : parsed,
          body: parsed,
        }
      );
    }
    return response.status === 204 ? null : response.json();
  }

  /**
   * Cross-module navigation. Options: { id, key, tab, designer, versionId }.
   * View keys match data-view / MODULE_LOADERS (e.g. 'flows', 'skills').
   */
  async function navigateTo(view, options) {
    const opts = options || {};
    if (typeof global.PlatformNavigate === 'function') {
      return global.PlatformNavigate(view, opts);
    }
    const nav = document.querySelector(`.global-nav [data-view="${view}"]`);
    if (nav) {
      nav.click();
    }
    const moduleMap = {
      overview: () => global.loadOverview && global.loadOverview(),
      skills: () => global.SkillsModule,
      rules: () => global.RulesModule,
      knowledge: () => global.KnowledgeModule,
      flows: () => global.FlowsModule,
      'runtime-profiles': () => global.RuntimeProfilesModule,
      checkpoints: () => global.HumanCheckpointsModule,
      controls: () => global.ControlsModule,
      integrations: () => global.IntegrationsModule,
      'capabilities-platform': () => global.CapabilitiesPlatformModule,
      audit: () => global.AuditModule,
      executions: () => global.LaunchesModule,
      inspector: () => global.ExecutionsModule,
    };
    const modOrFn = moduleMap[view];
    if (!modOrFn) return;
    const resolved = typeof modOrFn === 'function' ? modOrFn() : modOrFn;
    if (resolved && typeof resolved.load === 'function') {
      await resolved.load(opts.id || opts.key || null, opts);
    } else if (typeof resolved === 'function') {
      await resolved();
    }
  }

  /** Render a clickable entity chip that calls navigateTo. */
  function entityLink(view, label, options) {
    const opts = options || {};
    const id = opts.id || opts.key || '';
    return `<button type="button" class="entity-link" data-nav-view="${esc(view)}" data-nav-id="${esc(id)}" data-nav-tab="${esc(opts.tab || '')}" data-nav-designer="${opts.designer ? '1' : ''}">${esc(label)}</button>`;
  }

  function bindEntityLinks(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-nav-view]').forEach((btn) => {
      if (btn.dataset.navBound === '1') return;
      btn.dataset.navBound = '1';
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const view = btn.dataset.navView;
        const id = btn.dataset.navId || null;
        const tab = btn.dataset.navTab || undefined;
        const designer = btn.dataset.navDesigner === '1';
        navigateTo(view, { id, tab, designer }).catch((err) => toast(err.message || String(err)));
      });
    });
  }

  function cardMenu() {
    if (!global.PlatformCardMenu) {
      throw new Error('Обновите страницу (Ctrl+Shift+R) — не загружен общий компонент меню');
    }
    return global.PlatformCardMenu;
  }

  global.PlatformUtil = { esc, fetchJSON, toast, ApiError, navigateTo, entityLink, bindEntityLinks, cardMenu };

  const CardMenu = {
    installGlobal() {
      if (!document.body) return;
      if (document.body.dataset.cardMenuBound === '1') return;
      document.body.dataset.cardMenuBound = '1';
      document.addEventListener('click', (e) => {
        if (!e.target.closest) return;
        if (e.target.closest('.card-menu') || e.target.closest('.card-menu-panel')) return;
        CardMenu.closeAll();
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') CardMenu.closeAll();
      });
      window.addEventListener('scroll', () => CardMenu.closeAll(), true);
      window.addEventListener('resize', () => CardMenu.closeAll());
    },

    getPanel(menu) {
      if (!menu) return null;
      const local = menu.querySelector('.card-menu-panel');
      if (local) return local;
      const id = menu.dataset.menuId;
      if (!id) return null;
      return document.querySelector(`.card-menu-panel[data-host-menu-id="${CSS.escape(String(id))}"]`);
    },

    closeAll(except) {
      document.querySelectorAll('.card-menu.is-open').forEach((menu) => {
        if (except && menu === except) return;
        menu.classList.remove('is-open');
        const panel = CardMenu.getPanel(menu);
        const trigger = menu.querySelector('.card-menu-trigger');
        if (panel) {
          panel.classList.add('hidden');
          CardMenu.resetPanel(panel, menu);
        }
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
      });
      // Drop orphaned portaled panels (e.g. after catalog re-render).
      document.querySelectorAll('.card-menu-panel[data-host-menu-id]').forEach((panel) => {
        const hostId = panel.dataset.hostMenuId;
        const host = hostId
          && document.querySelector(`.card-menu[data-menu-id="${CSS.escape(String(hostId))}"]`);
        if (!host || !host.classList.contains('is-open')) {
          panel.remove();
        }
      });
    },

    resetPanel(panel, menu) {
      if (!panel) return;
      const host = menu
        || (panel.dataset.hostMenuId
          && document.querySelector(`.card-menu[data-menu-id="${CSS.escape(String(panel.dataset.hostMenuId))}"]`));
      if (host && panel.parentElement !== host) {
        host.appendChild(panel);
      }
      delete panel.dataset.hostMenuId;
      panel.style.position = '';
      panel.style.left = '';
      panel.style.top = '';
      panel.style.right = '';
      panel.style.zIndex = '';
      panel.style.visibility = '';
      panel.style.minWidth = '';
      panel.style.display = '';
    },

    positionPanel(menu, panel) {
      const trigger = menu && menu.querySelector('.card-menu-trigger');
      if (!trigger || !panel) return;
      // Portal to body so ancestor `transform` (card hover) does not break fixed coords.
      if (panel.parentElement !== document.body) {
        panel.dataset.hostMenuId = menu.dataset.menuId || '';
        document.body.appendChild(panel);
      }
      panel.style.visibility = 'hidden';
      panel.style.display = 'flex';
      const rect = trigger.getBoundingClientRect();
      const width = Math.max(panel.offsetWidth || 0, 188);
      let left = rect.right - width;
      let top = rect.bottom + 4;
      if (left < 8) left = 8;
      if (left + width > window.innerWidth - 8) {
        left = Math.max(8, window.innerWidth - width - 8);
      }
      const panelHeight = panel.offsetHeight || 120;
      if (top + panelHeight > window.innerHeight - 8) {
        top = Math.max(8, rect.top - panelHeight - 4);
      }
      panel.style.position = 'fixed';
      panel.style.left = `${left}px`;
      panel.style.top = `${top}px`;
      panel.style.right = 'auto';
      panel.style.zIndex = '10000';
      panel.style.minWidth = `${width}px`;
      panel.style.visibility = '';
    },

    toggle(menu, event) {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (!menu) return;
      const willOpen = !menu.classList.contains('is-open');
      CardMenu.closeAll(menu);
      const panel = CardMenu.getPanel(menu);
      const trigger = menu.querySelector('.card-menu-trigger');
      menu.classList.toggle('is-open', willOpen);
      if (panel) {
        panel.classList.toggle('hidden', !willOpen);
        if (willOpen) {
          CardMenu.positionPanel(menu, panel);
        } else {
          CardMenu.resetPanel(panel, menu);
        }
      }
      if (trigger) trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    },

    markup(id, actions) {
      const items = (actions || []).map((a) =>
        `<button type="button" role="menuitem"${a.danger ? ' class="danger"' : ''}${a.hidden ? ' hidden' : ''} data-card-action="${esc(a.id)}">${esc(a.label)}</button>`
      ).join('');
      return `<div class="card-menu" data-menu-id="${esc(id)}">
        <button type="button" class="card-menu-trigger" aria-label="Действия" aria-haspopup="true" aria-expanded="false">⋯</button>
        <div class="card-menu-panel hidden" role="menu">${items}</div>
      </div>`;
    },

    defaultActions(extra) {
      return [
        { id: 'edit', label: 'Редактировать' },
        ...(extra || []),
        { id: 'delete', label: 'Удалить', danger: true },
      ];
    },

    bind(scope, handler) {
      const rootEl = scope || document;
      if (!rootEl) return;
      rootEl.querySelectorAll('.card-menu-trigger').forEach((btn) => {
        if (btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';
        btn.onclick = (e) => CardMenu.toggle(btn.closest('.card-menu'), e);
      });
      rootEl.querySelectorAll('[data-card-action]').forEach((btn) => {
        if (btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';
        btn.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          const panel = btn.closest('.card-menu-panel');
          const hostId = panel && panel.dataset.hostMenuId;
          const menu = btn.closest('.card-menu')
            || (hostId && document.querySelector(`.card-menu[data-menu-id="${CSS.escape(String(hostId))}"]`));
          const id = menu && menu.dataset.menuId;
          const action = btn.dataset.cardAction;
          CardMenu.closeAll();
          if (id && handler) handler(id, action, e);
        };
      });
    },
  };

  global.PlatformCardMenu = CardMenu;
  if (document.body) {
    CardMenu.installGlobal();
  } else {
    document.addEventListener('DOMContentLoaded', () => CardMenu.installGlobal());
  }
})(window);
