// Only a display preference is stored; no user or CRM data enters browser storage.
(() => {
  let preference;
  try { preference = localStorage.getItem('service-theme'); } catch (_) { /* unavailable storage */ }
  const dark = preference ? preference === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
})();
