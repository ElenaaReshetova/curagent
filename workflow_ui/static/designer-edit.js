/**
 * DesignerEdit — shared Canvas | DSL editing shell for Playbook and Flow.
 */
(function (global) {
  'use strict';

  const DEFAULT_HINTS = {
    canvas: 'Перетаскивайте узлы · колесо — zoom · связь — от ручки',
    dsl: 'JSON DSL графа · Применить DSL, затем Сохранить',
  };

  function defaultValidate(parsed) {
    if (!parsed || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
      return 'DSL должен содержать nodes[] и edges[]';
    }
    return null;
  }

  function toast(message) {
    if (global.PlatformUtil && typeof global.PlatformUtil.toast === 'function') {
      return global.PlatformUtil.toast(message);
    }
    if (typeof global.toast === 'function') return global.toast(message);
    console.log(message);
  }

  function create(opts) {
    const options = opts || {};
    const root = options.root || document;
    const sel = options.selectors || {};
    const confirmLeaveDsl = options.confirmLeaveDsl !== false;
    const validate = typeof options.validate === 'function' ? options.validate : defaultValidate;
    const hints = Object.assign({}, DEFAULT_HINTS, options.hints || {});

    let viewMode = 'canvas';
    let dslDirty = false;
    let bound = false;

    function $(selector) {
      if (!selector) return null;
      if (typeof selector !== 'string') return selector;
      return root.querySelector ? root.querySelector(selector) : document.querySelector(selector);
    }

    function elToggle() {
      return $(sel.toggle || '[data-de-toggle]');
    }

    function elCanvas() {
      return $(sel.canvas || '[data-de-canvas]');
    }

    function elDslPanel() {
      return $(sel.dslPanel || '[data-de-dsl-panel]');
    }

    function elEditor() {
      return $(sel.editor || '[data-de-dsl-editor]');
    }

    function elApplyBtn() {
      return $(sel.applyBtn || '[data-de-apply-dsl]');
    }

    function elHint() {
      return $(sel.hint || '[data-de-hint]');
    }

    function isReadOnly() {
      return typeof options.isReadOnly === 'function' ? !!options.isReadOnly() : false;
    }

    function getGraph() {
      return typeof options.getGraph === 'function' ? options.getGraph() : null;
    }

    function getCanvas() {
      return typeof options.getCanvas === 'function' ? options.getCanvas() : null;
    }

    function syncFromGraph(syncOpts) {
      const force = syncOpts && syncOpts.force;
      const editor = elEditor();
      const graph = getGraph();
      if (!editor || !graph) return;
      if (!force) {
        if (dslDirty) return;
        if (document.activeElement === editor) return;
      }
      editor.value = JSON.stringify(graph, null, 2);
      editor.readOnly = isReadOnly();
      dslDirty = false;
    }

    function syncViewModeUi() {
      const mode = viewMode || 'canvas';
      const toggle = elToggle();
      if (toggle) {
        toggle.querySelectorAll('[data-view-mode]').forEach((btn) => {
          btn.classList.toggle('active', btn.dataset.viewMode === mode);
        });
      }
      const canvas = elCanvas();
      const dsl = elDslPanel();
      if (canvas) canvas.classList.toggle('is-active', mode === 'canvas');
      if (dsl) dsl.classList.toggle('is-active', mode === 'dsl');
      const hint = elHint();
      if (hint) hint.textContent = mode === 'dsl' ? hints.dsl : hints.canvas;
      if (mode === 'dsl') {
        syncFromGraph({ force: !dslDirty });
        const editor = elEditor();
        if (editor && !editor.readOnly) {
          requestAnimationFrame(() => {
            try { editor.focus(); } catch (_) { /* ignore */ }
          });
        }
      }
    }

    function setViewMode(mode) {
      const next = mode === 'dsl' ? 'dsl' : 'canvas';
      if (viewMode === 'dsl' && next === 'canvas' && dslDirty && !isReadOnly() && confirmLeaveDsl) {
        if (!window.confirm('В DSL есть неприкладённые изменения. Перейти на Canvas без «Применить DSL»?')) {
          syncViewModeUi();
          return false;
        }
        dslDirty = false;
      }
      viewMode = next;
      syncViewModeUi();
      if (viewMode === 'canvas') {
        const canvas = getCanvas();
        if (canvas && typeof canvas.fitView === 'function') {
          requestAnimationFrame(() => {
            try { canvas.fitView(); } catch (_) { /* ignore */ }
          });
        }
      }
      if (typeof options.onViewModeChange === 'function') {
        options.onViewModeChange(viewMode);
      }
      return true;
    }

    function applyDsl() {
      if (isReadOnly()) {
        toast(options.readOnlyMessage || 'Версия только для чтения');
        return false;
      }
      const editor = elEditor();
      if (!editor) return false;
      let parsed;
      try {
        parsed = JSON.parse(editor.value);
      } catch (err) {
        toast(`Некорректный JSON DSL: ${err.message}`);
        return false;
      }
      const errMsg = validate(parsed);
      if (errMsg) {
        toast(errMsg);
        return false;
      }
      if (typeof options.setGraph !== 'function') {
        toast('setGraph не задан');
        return false;
      }
      options.setGraph(parsed);
      dslDirty = false;
      syncFromGraph({ force: true });
      if (typeof options.onApplied === 'function') options.onApplied(parsed);
      toast(options.appliedMessage || 'DSL применён к canvas');
      return true;
    }

    function markDslDirty() {
      if (isReadOnly()) return;
      dslDirty = true;
    }

    function bind() {
      if (bound) return;
      bound = true;
      const toggle = elToggle();
      if (toggle) {
        toggle.querySelectorAll('[data-view-mode]').forEach((btn) => {
          btn.addEventListener('click', () => setViewMode(btn.dataset.viewMode || 'canvas'));
        });
      }
      const applyBtn = elApplyBtn();
      if (applyBtn) applyBtn.addEventListener('click', () => applyDsl());
      const editor = elEditor();
      if (editor && !editor.dataset.deBound) {
        editor.dataset.deBound = '1';
        editor.addEventListener('input', markDslDirty);
        editor.addEventListener('change', markDslDirty);
      }
      syncViewModeUi();
    }

    function reset(mode) {
      viewMode = mode === 'dsl' ? 'dsl' : 'canvas';
      dslDirty = false;
      syncViewModeUi();
    }

    return {
      bind,
      setViewMode,
      syncFromGraph,
      applyDsl,
      reset,
      getViewMode: () => viewMode,
      isDslDirty: () => dslDirty,
      markDslDirty,
      syncViewModeUi,
    };
  }

  global.DesignerEdit = { create, defaultValidate };
})(window);
