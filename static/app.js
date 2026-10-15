'use strict';
const themeButton = document.querySelector('[data-theme-toggle]');
const refreshThemeButton = () => {
  const dark = document.documentElement.dataset.theme === 'dark';
  themeButton?.setAttribute('aria-pressed', String(dark));
  if (themeButton) themeButton.querySelector('[data-theme-label]').textContent = dark ? 'حالت روشن' : 'حالت تاریک';
};
refreshThemeButton();
themeButton?.addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('service-theme', theme); } catch (_) { /* display still works */ }
  refreshThemeButton();
});
document.querySelectorAll('table').forEach(table => {
  const labels = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
  table.classList.add('responsive-table');
  table.querySelectorAll('tbody tr').forEach(row => {
    Array.from(row.cells).forEach((cell, index) => {
      if (cell.colSpan === 1) cell.dataset.label = labels[index] || '';
      else cell.classList.add('full-row');
    });
  });
});
const helpDialog = document.querySelector('#help-dialog');
let helpTrigger;
document.querySelectorAll('[data-help]').forEach(button => {
  button.addEventListener('click', () => {
    helpTrigger = button;
    document.querySelector('#help-content').textContent = button.dataset.help;
    helpDialog.showModal();
  });
});
document.querySelectorAll('[data-close-help]').forEach(button => button.addEventListener('click', () => helpDialog.close()));
helpDialog?.addEventListener('close', () => helpTrigger?.focus());
document.querySelectorAll('[data-date]').forEach(element => {
  const raw = element.dataset.date;
  const date = new Date(raw.length === 10 ? `${raw}T12:00:00+03:30` : raw);
  if (!Number.isNaN(date.valueOf())) {
    const options = {year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Asia/Tehran'};
    if (raw.length > 10) Object.assign(options, {hour: '2-digit', minute: '2-digit'});
    element.textContent = new Intl.DateTimeFormat('fa-IR', options).format(date);
    element.dateTime = raw;
  }
});
document.querySelectorAll('[data-save-form]').forEach(form => {
  form.addEventListener('submit', () => {
    form.querySelector('[data-save-button]').disabled = true;
    form.querySelector('[data-save-status]').textContent = 'در حال ثبت؛ لطفاً منتظر بمانید…';
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('[data-save-button]').forEach(button => { button.disabled = false; });
});
document.querySelector('#form-errors')?.focus();

const jobPanel = document.querySelector('[data-job-url]');
if (jobPanel && ['queued', 'running'].includes(jobPanel.dataset.jobState)) {
  let failures = 0;
  const pollJob = async () => {
    try {
      const response = await fetch(jobPanel.dataset.jobUrl, {headers: {'Accept': 'application/json'}, signal: AbortSignal.timeout(10000)});
      if (!response.ok) throw new Error('unavailable');
      const state = await response.json();
      jobPanel.querySelector('[data-job-message]').textContent = state.message;
      jobPanel.querySelector('[data-job-count]').textContent = state.progress;
      failures = 0;
      if (['queued', 'running'].includes(state.status)) setTimeout(pollJob, 2500);
    } catch (_) {
      failures += 1;
      jobPanel.querySelector('[data-job-message]').textContent = 'دریافت وضعیت ممکن نشد؛ اتصال را بررسی کنید. آخرین داده موفق حفظ شده است.';
      if (failures < 4) setTimeout(pollJob, 5000);
    }
  };
  setTimeout(pollJob, 1500);
}

const sidebarToggle = document.querySelector('[data-sidebar-toggle]');
const sidebar = document.querySelector('#main-sidebar');
let sidebarClosed = document.documentElement.classList.contains('sidebar-closed');
function refreshSidebar() {
  document.documentElement.classList.toggle('sidebar-closed', sidebarClosed);
  sidebarToggle?.setAttribute('aria-expanded', String(!sidebarClosed));
  sidebarToggle?.setAttribute('aria-label', sidebarClosed ? 'باز کردن منوی کناری' : 'بستن منوی کناری');
  if (sidebar) sidebar.inert = sidebarClosed;
}
refreshSidebar();
sidebarToggle?.addEventListener('click', () => {
  sidebarClosed = !sidebarClosed;
  refreshSidebar();
  try { localStorage.setItem('service-sidebar', sidebarClosed ? 'closed' : 'open'); } catch (_) {}
});
