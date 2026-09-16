/** FieldHelp, HelpTooltip, HelpPopover, ContextHelpDrawer. */
(function (global) {
  let tooltipEl = null;
  let popoverEl = null;
  let drawerHost = null;
  let activeAnchor = null;

  function esc(v) {
    return (global.HelpRegistry && HelpRegistry.esc) ? HelpRegistry.esc(v) : String(v == null ? '' : v);
  }

  function ensureTooltip() {
    if (tooltipEl) return tooltipEl;
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'help-tooltip';
    tooltipEl.hidden = true;
    tooltipEl.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltipEl);
    return tooltipEl;
  }

  function ensurePopover() {
    if (popoverEl) return popoverEl;
    popoverEl = document.createElement('div');
    popoverEl.className = 'help-popover';
    popoverEl.hidden = true;
    popoverEl.setAttribute('role', 'dialog');
    popoverEl.setAttribute('aria-modal', 'false');
    document.body.appendChild(popoverEl);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hidePopover();
    });
    document.addEventListener('mousedown', (e) => {
      if (!popoverEl || popoverEl.hidden) return;
      if (popoverEl.contains(e.target)) return;
      if (activeAnchor && activeAnchor.contains(e.target)) return;
      hidePopover();
    });
    return popoverEl;
  }

  function placeNear(el, anchor, offset = 8) {
    const r = anchor.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    el.style.left = '0px';
    el.style.top = '0px';
    el.hidden = false;
    const er = el.getBoundingClientRect();
    let left = r.left;
    let top = r.bottom + offset;
    if (left + er.width > vw - 8) left = Math.max(8, vw - er.width - 8);
    if (top + er.height > vh - 8) top = Math.max(8, r.top - er.height - offset);
    el.style.left = `${Math.max(8, left)}px`;
    el.style.top = `${Math.max(8, top)}px`;
  }

  function showTooltip(anchor, text) {
    if (!text) return;
    const el = ensureTooltip();
    el.textContent = text;
    placeNear(el, anchor, 6);
  }

  function hideTooltip() {
    if (tooltipEl) tooltipEl.hidden = true;
  }

  function renderConceptBody(concept) {
    if (!concept) return '<p>Справка недоступна.</p>';
    const parts = [];
    parts.push(`<h4>${esc(concept.title)}</h4>`);
    if (concept.shortDescription) {
      parts.push(`<p>${esc(concept.shortDescription)}</p>`);
    }
    if (concept.fullDescription) {
      parts.push(`<div class="help-section"><strong>Подробнее</strong><p>${esc(concept.fullDescription)}</p></div>`);
    }
    if (concept.recommendedValue) {
      parts.push(`<div class="help-section"><strong>Рекомендуется</strong><p>${esc(concept.recommendedValue)}</p></div>`);
    }
    if (concept.example && concept.example.value != null) {
      const val = typeof concept.example.value === 'string'
        ? concept.example.value
        : JSON.stringify(concept.example.value, null, 2);
      parts.push(`<div class="help-section"><strong>${esc(concept.example.title || 'Пример')}</strong><pre style="white-space:pre-wrap;margin:0;font-size:0.72rem">${esc(val)}</pre></div>`);
    }
    if (concept.consequences && concept.consequences.length) {
      parts.push(`<div class="help-section"><strong>Последствия</strong><ul>${concept.consequences.map((c) => `<li>${esc(c)}</li>`).join('')}</ul></div>`);
    }
    if (concept.warnings && concept.warnings.length) {
      parts.push(`<div class="help-warn">${concept.warnings.map((w) => esc(w)).join('<br/>')}</div>`);
    }
    if (concept.relatedConcepts && concept.relatedConcepts.length) {
      parts.push(`<div class="help-section"><strong>Связанные понятия</strong><div class="help-related">${
        concept.relatedConcepts.map((k) => `<button type="button" data-help-related="${esc(k)}">${esc(k)}</button>`).join('')
      }</div></div>`);
    }
    if (concept.missingTranslation) {
      parts.push('<p class="help-short">Перевод отсутствует — показан fallback.</p>');
    }
    return parts.join('');
  }

  async function showPopover(anchor, conceptKey) {
    hideTooltip();
    const concept = await HelpRegistry.get(conceptKey);
    const el = ensurePopover();
    activeAnchor = anchor;
    el.innerHTML = `<button type="button" class="help-popover-close" aria-label="Закрыть">×</button>${renderConceptBody(concept)}`;
    el.querySelector('.help-popover-close').onclick = () => hidePopover();
    el.querySelectorAll('[data-help-related]').forEach((btn) => {
      btn.addEventListener('click', () => {
        showPopover(anchor, btn.getAttribute('data-help-related'));
      });
    });
    placeNear(el, anchor, 10);
    el.querySelector('.help-popover-close').focus();
  }

  function hidePopover() {
    if (popoverEl) popoverEl.hidden = true;
    activeAnchor = null;
  }

  function mountDrawer(host) {
    drawerHost = host;
    if (!host) return;
    if (host.querySelector('.help-drawer')) return;
    const drawer = document.createElement('div');
    drawer.className = 'help-drawer';
    drawer.id = 'pb-help-drawer';
    drawer.innerHTML = `
      <div class="help-drawer-head">
        <h3 id="pb-help-drawer-title">Справка</h3>
        <button type="button" class="pb-text-btn" id="pb-help-drawer-close" aria-label="Закрыть справку">Закрыть</button>
      </div>
      <div class="help-drawer-body" id="pb-help-drawer-body"></div>
    `;
    host.appendChild(drawer);
    host.querySelector('#pb-help-drawer-close').addEventListener('click', () => closeDrawer());
  }

  async function openDrawer(conceptKey) {
    if (!drawerHost) return;
    const drawer = drawerHost.querySelector('.help-drawer');
    const body = drawerHost.querySelector('#pb-help-drawer-body');
    const title = drawerHost.querySelector('#pb-help-drawer-title');
    const concept = await HelpRegistry.get(conceptKey);
    if (title) title.textContent = (concept && concept.title) || 'Справка';
    if (body) {
      body.innerHTML = renderConceptBody(concept);
      body.querySelectorAll('[data-help-related]').forEach((btn) => {
        btn.addEventListener('click', () => openDrawer(btn.getAttribute('data-help-related')));
      });
    }
    if (drawer) drawer.classList.add('open');
  }

  function closeDrawer() {
    if (!drawerHost) return;
    const drawer = drawerHost.querySelector('.help-drawer');
    if (drawer) drawer.classList.remove('open');
  }

  /**
   * Render a labeled field with Level-1 short text + Level-2/3 help controls.
   * @returns {HTMLElement}
   */
  function renderFieldHelp(options) {
    const {
      conceptKey,
      label,
      controlHtml,
      shortDescription,
    } = options;
    const wrap = document.createElement('div');
    wrap.className = 'help-field';
    wrap.dataset.conceptKey = conceptKey || '';
    wrap.innerHTML = `
      <div class="help-field-label-row">
        <span class="help-label">${esc(label)}</span>
        <button type="button" class="help-q" aria-label="Подсказка: ${esc(label)}" data-help-tip="${esc(conceptKey || '')}">?</button>
      </div>
      <p class="help-short" data-help-short></p>
      ${controlHtml || ''}
      <button type="button" class="help-learn" data-help-learn="${esc(conceptKey || '')}">Подробнее</button>
    `;
    const shortEl = wrap.querySelector('[data-help-short]');
    if (shortDescription) shortEl.textContent = shortDescription;

    const tipBtn = wrap.querySelector('[data-help-tip]');
    const learnBtn = wrap.querySelector('[data-help-learn]');

    const bindConcept = async () => {
      if (!conceptKey) return null;
      const concept = await HelpRegistry.get(conceptKey);
      if (concept && !shortDescription && shortEl) {
        shortEl.textContent = concept.shortDescription || '';
      }
      return concept;
    };
    bindConcept();

    const showTip = async () => {
      const concept = await bindConcept();
      const text = shortDescription || (concept && concept.shortDescription) || '';
      if (!text) return;
      showTooltip(tipBtn, text);
    };

    tipBtn.addEventListener('mouseenter', showTip);
    tipBtn.addEventListener('focus', showTip);
    tipBtn.addEventListener('mouseleave', hideTooltip);
    tipBtn.addEventListener('blur', hideTooltip);
    tipBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      hideTooltip();
      await showPopover(tipBtn, conceptKey);
    });
    learnBtn.addEventListener('click', async () => {
      await showPopover(learnBtn, conceptKey);
    });

    return wrap;
  }

  global.HelpUI = {
    renderFieldHelp,
    showTooltip,
    hideTooltip,
    showPopover,
    hidePopover,
    mountDrawer,
    openDrawer,
    closeDrawer,
    renderConceptBody,
  };
})(window);
