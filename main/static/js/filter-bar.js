// Fix: Issue 4 — reusable table filter bar.
//
// Generic over any table whose <thead> cells carry data-key attributes.
// The bar filters and sorts the LIVE tbody rows in place (display:none),
// so per-row event listeners (checkboxes, locate links, MRM buttons) survive.
// Re-call initFilterBar after each fetch/re-render to repopulate dropdowns.
//
//   initFilterBar('hold-table', {
//     search: ['account', 'bank', 'branch'],   // keys matched by the text box
//     dropdowns: ['bank', 'state'],            // one <select> per key
//     amountRange: true,                       // Min/Max inputs on `amountKey`
//     amountKey: 'amount',                     // default 'amount'
//     customRange: { key: 'count', label: 'Cases (min/max)' },
//     sortable: true,                          // click-to-sort on data-key headers
//     countLabel: 'Showing {x} of {y} entries'
//   });
//
// Headers with data-key="sno" are excluded from sorting; visible rows whose
// cell sits under that header are renumbered 1..n after every filter pass.
function initFilterBar(tableId, config) {
  const table = document.getElementById(tableId);
  if (!table) return null;
  const cfg = config || {};
  const thead = table.tHead;
  const tbody = table.tBodies && table.tBodies[0];
  if (!thead || !tbody || !thead.rows.length) return null;

  const headerRow = thead.rows[thead.rows.length - 1];
  const keyIndex = {};
  const keyTitle = {};
  for (let i = 0; i < headerRow.cells.length; i++) {
    const k = headerRow.cells[i].dataset.key;
    if (k) {
      keyIndex[k] = i;
      keyTitle[k] = (headerRow.cells[i].textContent || k).replace(/[▲▼]\s*$/, '').trim();
    }
  }

  const cellText = (tr, key) => {
    const idx = keyIndex[key];
    if (idx == null || !tr.cells[idx]) return '';
    return (tr.cells[idx].textContent || '').trim();
  };
  const cellNum = (tr, key) => {
    const raw = cellText(tr, key).replace(/[^0-9.\-]/g, '');
    if (!raw) return null;
    const n = Number.parseFloat(raw);
    return Number.isNaN(n) ? null : n;
  };
  const rows = () => Array.prototype.slice.call(tbody.rows);

  // Replace any bar from a previous call (re-init after fetch).
  const barId = tableId + '-filter-bar';
  const oldBar = document.getElementById(barId);
  if (oldBar) oldBar.remove();

  const state = {
    term: '',
    selects: {},          // key -> selected value ('' = all)
    amtMin: null, amtMax: null,
    rngMin: null, rngMax: null,
    sortKey: null, sortDir: null,
    originalOrder: rows() // restore order when Reset clicked
  };

  const bar = document.createElement('div');
  bar.className = 'filter-bar';
  bar.id = barId;

  const addField = (labelText, el) => {
    const wrap = document.createElement('label');
    wrap.className = 'filter-bar-field';
    const span = document.createElement('span');
    span.textContent = labelText;
    wrap.appendChild(span);
    wrap.appendChild(el);
    bar.appendChild(wrap);
    return el;
  };

  // ── Search box ────────────────────────────────────────────────────────
  let searchInput = null;
  if (Array.isArray(cfg.search) && cfg.search.length) {
    searchInput = document.createElement('input');
    searchInput.type = 'search';
    searchInput.placeholder = 'Search ' + cfg.search.map(k => keyTitle[k] || k).join(' / ');
    addField('Search', searchInput);
    searchInput.addEventListener('input', () => {
      state.term = searchInput.value.trim().toLowerCase();
      apply();
    });
  }

  // ── Dropdowns ─────────────────────────────────────────────────────────
  const selectEls = {};
  (cfg.dropdowns || []).forEach(key => {
    if (keyIndex[key] == null) return;
    const sel = document.createElement('select');
    const optAll = document.createElement('option');
    optAll.value = '';
    optAll.textContent = 'All';
    sel.appendChild(optAll);
    const values = [...new Set(rows().map(tr => cellText(tr, key)).filter(v => v !== ''))]
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    });
    addField(keyTitle[key] || key, sel);
    sel.addEventListener('change', () => {
      state.selects[key] = sel.value;
      apply();
    });
    selectEls[key] = sel;
  });

  // ── Amount range ──────────────────────────────────────────────────────
  const amountKey = cfg.amountKey || 'amount';
  let amtMinEl = null, amtMaxEl = null;
  if (cfg.amountRange && keyIndex[amountKey] != null) {
    amtMinEl = document.createElement('input');
    amtMinEl.type = 'number';
    amtMinEl.placeholder = 'Min';
    amtMinEl.className = 'filter-bar-num';
    amtMaxEl = document.createElement('input');
    amtMaxEl.type = 'number';
    amtMaxEl.placeholder = 'Max';
    amtMaxEl.className = 'filter-bar-num';
    const pair = document.createElement('div');
    pair.className = 'filter-bar-range';
    pair.appendChild(amtMinEl);
    pair.appendChild(amtMaxEl);
    addField((keyTitle[amountKey] || 'Amount') + ' (min/max)', pair);
    const onAmt = () => {
      state.amtMin = amtMinEl.value === '' ? null : Number(amtMinEl.value);
      state.amtMax = amtMaxEl.value === '' ? null : Number(amtMaxEl.value);
      apply();
    };
    amtMinEl.addEventListener('input', onAmt);
    amtMaxEl.addEventListener('input', onAmt);
  }

  // ── Custom numeric range (e.g. case count) ────────────────────────────
  let rngMinEl = null, rngMaxEl = null;
  if (cfg.customRange && cfg.customRange.key && keyIndex[cfg.customRange.key] != null) {
    rngMinEl = document.createElement('input');
    rngMinEl.type = 'number';
    rngMinEl.placeholder = 'Min';
    rngMinEl.className = 'filter-bar-num';
    rngMaxEl = document.createElement('input');
    rngMaxEl.type = 'number';
    rngMaxEl.placeholder = 'Max';
    rngMaxEl.className = 'filter-bar-num';
    const pair = document.createElement('div');
    pair.className = 'filter-bar-range';
    pair.appendChild(rngMinEl);
    pair.appendChild(rngMaxEl);
    addField(cfg.customRange.label || cfg.customRange.key, pair);
    const onRng = () => {
      state.rngMin = rngMinEl.value === '' ? null : Number(rngMinEl.value);
      state.rngMax = rngMaxEl.value === '' ? null : Number(rngMaxEl.value);
      apply();
    };
    rngMinEl.addEventListener('input', onRng);
    rngMaxEl.addEventListener('input', onRng);
  }

  // ── Reset + count ─────────────────────────────────────────────────────
  const resetBtn = document.createElement('button');
  resetBtn.type = 'button';
  resetBtn.className = 'filter-bar-reset';
  resetBtn.textContent = 'Reset';
  bar.appendChild(resetBtn);

  const countEl = document.createElement('span');
  countEl.className = 'filter-bar-count';
  bar.appendChild(countEl);

  resetBtn.addEventListener('click', () => {
    state.term = '';
    state.selects = {};
    state.amtMin = state.amtMax = state.rngMin = state.rngMax = null;
    state.sortKey = state.sortDir = null;
    if (searchInput) searchInput.value = '';
    Object.values(selectEls).forEach(sel => { sel.value = ''; });
    [amtMinEl, amtMaxEl, rngMinEl, rngMaxEl].forEach(el => { if (el) el.value = ''; });
    // restore original row order
    state.originalOrder.forEach(tr => tbody.appendChild(tr));
    updateSortIndicators();
    apply();
  });

  table.parentNode.insertBefore(bar, table);

  // ── Sorting ───────────────────────────────────────────────────────────
  function updateSortIndicators() {
    Object.keys(keyIndex).forEach(k => {
      const th = headerRow.cells[keyIndex[k]];
      th.classList.remove('fb-sort-asc', 'fb-sort-desc');
      if (k === state.sortKey) {
        th.classList.add(state.sortDir === 'asc' ? 'fb-sort-asc' : 'fb-sort-desc');
      }
    });
  }

  if (cfg.sortable) {
    Object.keys(keyIndex).forEach(k => {
      if (k === 'sno') return;
      const th = headerRow.cells[keyIndex[k]];
      th.classList.add('fb-sortable');
      // Re-init after a fetch must not stack duplicate listeners on a static thead
      if (th._fbSortHandler) th.removeEventListener('click', th._fbSortHandler);
      th._fbSortHandler = () => {
        if (state.sortKey === k) {
          state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          state.sortKey = k;
          state.sortDir = 'asc';
        }
        const dir = state.sortDir === 'asc' ? 1 : -1;
        const sorted = rows().sort((a, b) => {
          const na = cellNum(a, k), nb = cellNum(b, k);
          if (na != null && nb != null) return (na - nb) * dir;
          return cellText(a, k).localeCompare(cellText(b, k), undefined, { numeric: true }) * dir;
        });
        sorted.forEach(tr => tbody.appendChild(tr));
        updateSortIndicators();
        apply();
      };
      th.addEventListener('click', th._fbSortHandler);
    });
  }

  // ── Filter predicate (AND across all active controls) ─────────────────
  function rowVisible(tr) {
    if (state.term && Array.isArray(cfg.search) && cfg.search.length) {
      const hit = cfg.search.some(k => cellText(tr, k).toLowerCase().includes(state.term));
      if (!hit) return false;
    }
    for (const [key, val] of Object.entries(state.selects)) {
      if (val && cellText(tr, key) !== val) return false;
    }
    if (state.amtMin != null || state.amtMax != null) {
      const n = cellNum(tr, amountKey);
      if (n == null) return false;
      if (state.amtMin != null && n < state.amtMin) return false;
      if (state.amtMax != null && n > state.amtMax) return false;
    }
    if (cfg.customRange && (state.rngMin != null || state.rngMax != null)) {
      const n = cellNum(tr, cfg.customRange.key);
      if (n == null) return false;
      if (state.rngMin != null && n < state.rngMin) return false;
      if (state.rngMax != null && n > state.rngMax) return false;
    }
    return true;
  }

  function apply() {
    const all = rows();
    let shown = 0;
    all.forEach(tr => {
      const vis = rowVisible(tr);
      tr.style.display = vis ? '' : 'none';
      if (vis) {
        shown++;
        if (keyIndex.sno != null && tr.cells[keyIndex.sno]) {
          tr.cells[keyIndex.sno].textContent = String(shown);
        }
      }
    });
    const tpl = cfg.countLabel || 'Showing {x} of {y} entries';
    countEl.textContent = tpl.replace('{x}', String(shown)).replace('{y}', String(all.length));
  }

  apply();
  return { apply, reset: () => resetBtn.click() };
}

// Support plain <script> usage and (potential) module import alike.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initFilterBar };
}
