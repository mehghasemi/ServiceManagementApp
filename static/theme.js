// Only a display preference is stored; no user or CRM data enters browser storage.
(() => {
  let closed = window.matchMedia('(max-width: 700px)').matches;
  try { const saved = localStorage.getItem('service-sidebar'); if (saved !== null) closed = saved === 'closed'; } catch (_) {}
  document.documentElement.classList.toggle('sidebar-closed', closed);
  let preference;
  try { preference = localStorage.getItem('service-theme'); } catch (_) { /* unavailable storage */ }
  const dark = preference ? preference === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
})();
