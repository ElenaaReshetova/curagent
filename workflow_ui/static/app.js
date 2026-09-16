/* Platform shell — nav + module routing only. */

let activeViewKey = null;

const MODULE_LOADERS = {
  overview: (opts) => window.loadOverview && window.loadOverview(opts),
  flows: (opts) => window.FlowsModule && window.FlowsModule.load(opts && (opts.id || opts.key), opts),
  skills: (opts) => window.SkillsModule && window.SkillsModule.load(opts && (opts.id || opts.key), opts),
  rules: (opts) => window.RulesModule && window.RulesModule.load(opts && (opts.id || opts.key), opts),
  knowledge: (opts) => window.KnowledgeModule && window.KnowledgeModule.load(opts && (opts.id || opts.key), opts),
  'runtime-profiles': (opts) => window.RuntimeProfilesModule && window.RuntimeProfilesModule.load(opts && (opts.id || opts.key), opts),
  checkpoints: (opts) => window.HumanCheckpointsModule && window.HumanCheckpointsModule.load(opts && (opts.id || opts.key), opts),
  controls: (opts) => window.ControlsModule && window.ControlsModule.load(opts && (opts.id || opts.key), opts),
  integrations: (opts) => window.IntegrationsModule && window.IntegrationsModule.load(opts && (opts.id || opts.key), opts),
  'capabilities-platform': (opts) => window.CapabilitiesPlatformModule && window.CapabilitiesPlatformModule.load(opts && (opts.id || opts.key || opts.keyName), opts),
  audit: (opts) => window.AuditModule && window.AuditModule.load(opts && (opts.id || opts.key), opts),
  executions: (opts) => window.LaunchesModule && window.LaunchesModule.load(opts),
  inspector: (opts) => window.ExecutionsModule && window.ExecutionsModule.load(opts && (opts.id || opts.key), opts),
};

function activateView(viewId, options) {
  const opts = options || {};
  const key = viewId.replace(/^view-/, '');

  if (activeViewKey && activeViewKey !== key) {
    const prevUnload = {
      inspector: () => window.ExecutionsModule && window.ExecutionsModule.unload && window.ExecutionsModule.unload(),
    }[activeViewKey];
    if (prevUnload) prevUnload();
  }
  activeViewKey = key;

  document.querySelectorAll('.view').forEach((v) => {
    v.classList.remove('active');
    v.classList.add('hidden');
  });

  const view = document.getElementById(viewId);
  if (view) {
    view.classList.remove('hidden');
    view.classList.add('active');
  }

  document.querySelectorAll('.global-nav [data-view]').forEach((li) => {
    li.classList.toggle('active', li.dataset.view === key);
  });

  const loader = MODULE_LOADERS[key];
  if (!loader) return;
  const toastFn = (window.PlatformUtil && window.PlatformUtil.toast) || ((m) => console.warn(m));
  Promise.resolve(loader(opts)).catch((e) => {
    toastFn(`Не удалось загрузить (${key}): ${e.message}`);
    console.error(`Module load failed (${key}):`, e);
  });
}

async function platformNavigate(view, options) {
  const opts = options || {};
  activateView('view-' + view, opts);
}

window.PlatformNavigate = platformNavigate;

function setupNav() {
  document.querySelectorAll('.global-nav [data-view]').forEach((li) => {
    li.onclick = () => {
      // Avoid invisible/open dropdown overlays blocking navigation.
      try {
        if (window.PlatformCardMenu && typeof window.PlatformCardMenu.closeAll === 'function') {
          window.PlatformCardMenu.closeAll();
        }
      } catch (_) { /* optional */ }
      activateView('view-' + li.dataset.view);
    };
  });
}

async function init() {
  try {
    const fetchJSON = window.PlatformUtil && window.PlatformUtil.fetchJSON;
    const cfg = fetchJSON
      ? await fetchJSON('/api/config')
      : await (await fetch('/api/config')).json();
    const brand = document.getElementById('platform-name');
    if (brand) brand.textContent = 'AI PDLC Platform';
    const temporal = document.getElementById('nav-temporal');
    if (temporal && cfg.temporal_ui_url) temporal.href = cfg.temporal_ui_url;
  } catch (e) {
    console.warn('config load failed', e);
  }
  setupNav();
  activateView('view-overview');
}

document.addEventListener('DOMContentLoaded', init);
