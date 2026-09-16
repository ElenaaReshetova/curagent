/** Contextual Help Content Registry client. */
(function (global) {
  const cache = { locale: 'ru-RU', byKey: null, loading: null };

  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function ensureLoaded(locale) {
    const loc = locale || cache.locale || 'ru-RU';
    if (cache.byKey && cache.locale === loc) return cache.byKey;
    if (cache.loading) return cache.loading;
    cache.loading = (async () => {
      const fetchJSON = (global.PlatformUtil && PlatformUtil.fetchJSON)
        ? PlatformUtil.fetchJSON.bind(PlatformUtil)
        : async (path) => {
          const res = await fetch(path.startsWith('/api/') ? path : `/api/v1${path}`);
          if (!res.ok) throw new Error(String(res.status));
          return res.json();
        };
      const data = await fetchJSON(`/help?locale=${encodeURIComponent(loc)}`);
      const map = {};
      (data.concepts || []).forEach((c) => {
        map[c.conceptKey] = c;
      });
      cache.locale = loc;
      cache.byKey = map;
      cache.loading = null;
      return map;
    })();
    try {
      return await cache.loading;
    } catch (err) {
      cache.loading = null;
      throw err;
    }
  }

  async function get(conceptKey, locale) {
    const map = await ensureLoaded(locale);
    return map[conceptKey] || null;
  }

  function clear() {
    cache.byKey = null;
    cache.loading = null;
  }

  global.HelpRegistry = {
    ensureLoaded,
    get,
    clear,
    esc,
    DEFAULT_LOCALE: 'ru-RU',
  };
})(window);
