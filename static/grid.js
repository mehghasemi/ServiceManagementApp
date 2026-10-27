/* Personal, server-persisted column layouts. No record data is stored here. */
(() => {
  const element = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (text, action) => {
    const node = element('button', text, 'small-button');
    node.type = 'button'; node.addEventListener('click', action); return node;
  };
  document.querySelectorAll('table[data-grid]').forEach(async table => {
    const headers = Array.from(table.tHead.rows[0].cells);
    const rows = Array.from(table.tBodies[0].rows);
    const emptyRows = rows.filter(row => row.cells.length === 1 && row.cells[0].colSpan > 1);
    const originals = new Map(headers.map((h, i) => [h.dataset.column, {
      header: h, cells: rows.map(row => row.cells.length === headers.length ? row.cells[i] : null),
      label: h.textContent.replace(/[↕▲▼؟]/g, '').trim()
    }]));
    if (originals.size !== headers.length || originals.has(undefined)) return;
    const defaults = headers.map(h => ({id: h.dataset.column, width: Math.min(300, Math.max(110, Math.round(h.getBoundingClientRect().width || 180))), visible: h.dataset.defaultHidden !== 'true'}));
    let layout = defaults.map(c => ({...c})), pending = Promise.resolve(), timer;
    const toolbar = element('div', null, 'grid-toolbar');
    const status = element('span'); status.setAttribute('role', 'status');
    const endpoint = `/preferences/grids/${table.dataset.grid}/`;
    const apply = () => {
      table.classList.add('personal-grid');
      let colgroup = table.querySelector('colgroup');
      if (!colgroup) { colgroup = element('colgroup'); table.insertBefore(colgroup, table.tHead); }
      colgroup.replaceChildren();
      layout.forEach((c, index) => {
        const original = originals.get(c.id);
        original.header.hidden = !c.visible;
        const headRow = table.tHead.rows[0];
        if (headRow.cells[index] !== original.header) headRow.insertBefore(original.header, headRow.cells[index] || null);
        if (c.visible) { const col = element('col'); col.style.width = `${c.width}px`; colgroup.append(col); }
        original.cells.forEach((cell, i) => {
          if (!cell) return;
          cell.dataset.column = c.id;
          if (['status', 'service', 'sprint', 'release', 'phase'].includes(c.id)) {
            const hash = Array.from(cell.textContent.trim()).reduce((n, ch) => n + ch.charCodeAt(0), 0);
            cell.dataset.tone = String(hash % 5 + 1);
          }
          cell.hidden = !c.visible;
          if (rows[i].cells[index] !== cell) rows[i].insertBefore(cell, rows[i].cells[index] || null);
        });
      });
      const visible = layout.filter(c => c.visible);
      table.style.width = `${visible.reduce((sum, c) => sum + c.width, 0)}px`;
      emptyRows.forEach(row => { row.cells[0].colSpan = visible.length; });
    };
    const save = () => {
      const columns = layout.map(c => ({...c}));
      status.textContent = 'در حال ذخیره…';
      pending = pending.catch(() => {}).then(async () => {
        try {
          const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value || decodeURIComponent(document.cookie.split('; ').find(s => s.startsWith('csrftoken='))?.split('=')[1] || '');
          const response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': token}, body: JSON.stringify({columns})});
          if (!response.ok) throw new Error();
          status.textContent = 'چیدمان ذخیره شد';
        } catch (_) { status.textContent = 'ذخیره نشد؛ اتصال را بررسی و دوباره ذخیره کنید.'; }
      });
    };
    const dialog = element('dialog', null, 'grid-dialog');
    const heading = element('h2', 'تنظیم ستون‌ها');
    heading.id = `grid-title-${table.dataset.grid}`; dialog.setAttribute('aria-labelledby', heading.id);
    const explanation = element('p', 'نمایش، ترتیب و عرض ستون‌ها برای حساب شما ذخیره می‌شود. متن کامل سلول با دوبار کلیک یا فوکوس و Enter دیده می‌شود. عرض را با کشیدن لبه سرستون یا کلیدهای چپ و راست تغییر دهید.');
    const list = element('div', null, 'grid-column-list');
    const render = () => {
      list.replaceChildren();
      layout.forEach((c, index) => {
        const row = element('div', null, 'grid-column-option');
        const label = element('label'); const check = element('input'); check.type = 'checkbox'; check.checked = c.visible;
        check.addEventListener('change', () => {
          if (!check.checked && layout.filter(x => x.visible).length === 1) { check.checked = true; return; }
          c.visible = check.checked; apply(); save();
        });
        label.append(check, document.createTextNode(originals.get(c.id).label));
        const width = element('input'); width.type = 'number'; width.min = 80; width.max = 600; width.value = c.width;
        width.setAttribute('aria-label', `عرض ${originals.get(c.id).label} به پیکسل`);
        width.addEventListener('input', () => { if (!width.validity.valid || !width.value) return; c.width = Math.max(80, Math.min(600, Math.round(Number(width.value) || 80))); width.value = c.width; apply(); save(); });
        row.append(label, width);
        [-1, 1].forEach(direction => {
          const move = button(direction === -1 ? '↑' : '↓', () => {
            [layout[index], layout[index + direction]] = [layout[index + direction], layout[index]];
            apply(); save(); render(); list.children[index + direction].querySelector('input').focus();
          });
          move.setAttribute(direction === -1 ? 'data-up' : 'data-down', '');
          move.setAttribute('aria-label', `${originals.get(c.id).label} ${direction === -1 ? 'یک ستون جلوتر' : 'یک ستون عقب‌تر'}`);
          move.disabled = index + direction < 0 || index + direction >= layout.length;
          row.append(move);
        });
        list.append(row);
      });
    };
    dialog.append(heading, explanation, list, button('بازنشانی ستون‌ها', () => { layout = defaults.map(c => ({...c})); apply(); render(); save(); }), button('بستن', () => dialog.close()));
    document.body.append(dialog);
    const open = button('☷ ستون‌ها', () => { render(); dialog.showModal(); }); open.disabled = true;
    const retry = button('ذخیره چیدمان', save); retry.disabled = true;
    toolbar.append(open, retry, button('؟', () => { render(); dialog.showModal(); }), status);
    table.parentElement.before(toolbar);
    try {
      const response = await fetch(endpoint); if (!response.ok) throw new Error();
      const saved = (await response.json()).columns;
      const valid = saved.filter(c => originals.has(c.id));
      layout = [...valid, ...defaults.filter(c => !valid.some(s => s.id === c.id))];
      if (!layout.some(c => c.visible)) layout[0].visible = true;
    } catch (_) { status.textContent = 'تنظیم قبلی دریافت نشد؛ چیدمان پیش‌فرض نمایش داده می‌شود.'; }
    open.disabled = false; retry.disabled = false;
    originals.forEach((original, id) => {
      original.cells.forEach(cell => {
        if (!cell) return;
        const content = element('div', null, 'grid-cell-content');
        while (cell.firstChild) content.append(cell.firstChild);
        content.tabIndex = 0; content.setAttribute('aria-label', `${original.label}؛ برای متن کامل Enter بزنید`);
        const show = () => {
          const detail = element('dialog', null, 'grid-dialog grid-cell-dialog');
          const title = element('h2', original.label); const body = element('div', content.textContent, 'grid-full-text');
          detail.append(title, body, button('بستن', () => detail.close()));
          detail.setAttribute('aria-label', original.label); document.body.append(detail);
          detail.addEventListener('close', () => { detail.remove(); content.focus(); }); detail.showModal();
        };
        content.addEventListener('keydown', e => { if (e.target === content && e.key === 'Enter') { e.preventDefault(); show(); } });
        content.addEventListener('dblclick', e => { if (!e.target.closest('a,button,input')) show(); });
        cell.append(content);
      });
      const handle = element('button', '', 'grid-resize'); handle.type = 'button';
      handle.setAttribute('aria-label', `تغییر عرض ${original.label}؛ کلید چپ افزایش و راست کاهش`);
      handle.addEventListener('click', e => e.preventDefault());
      handle.addEventListener('keydown', e => {
        if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
        e.preventDefault(); const c = layout.find(c => c.id === id);
        c.width = Math.max(80, Math.min(600, c.width + (e.key === 'ArrowLeft' ? 10 : -10))); apply(); clearTimeout(timer); timer = setTimeout(save, 350);
      });
      handle.addEventListener('pointerdown', e => {
        e.preventDefault(); const c = layout.find(c => c.id === id), start = e.clientX, width = c.width;
        handle.setPointerCapture(e.pointerId);
        const move = event => { c.width = Math.max(80, Math.min(600, Math.round(width + start - event.clientX))); apply(); };
        const end = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', end); handle.removeEventListener('pointercancel', end); save(); };
        handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', end); handle.addEventListener('pointercancel', end);
      });
      original.header.append(handle);
    });
    apply();
  });
})();
