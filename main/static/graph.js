// Fetching Branch data from IFSC Code. calling Razorpay IFSC API
const branchCache = new Map();
const branchPhoneCache = new Map();
const isViewer = globalThis.window === undefined ? false : Boolean(globalThis.isViewerRole);

// Sanitize HTML to prevent XSS
function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return '';
  return String(unsafe)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchBranchInfo(ifsc) {
  if (!ifsc) return { BRANCH: 'Unknown' };
  const key = String(ifsc).toUpperCase();
  if (branchCache.has(key)) {
    return { BRANCH: branchCache.get(key), PHONE: branchPhoneCache.get(key) || '' };
  }
  let branch = '';
  let phone = '';
  try {
    const res = await fetch(`/ifsc_info/${encodeURIComponent(key)}`);
    if (res.ok) {
      const data = await res.json();
      branch = data?.BRANCH || data?.Branch || data?.BRANCH_NAME || data['Branch Name'] || data?.BranchName || '';
      phone = data?.PHONE || data?.Phone || data?.Contact || data?.Telephone || data['Phone No'] || data['Contact Number'] || data['PhoneNumber'] || '';
    }
  } catch (_) { }
  const finalBranch = branch && String(branch).trim() ? String(branch).trim() : 'Unknown';
  const finalPhone = phone || '';
  branchCache.set(key, finalBranch);
  branchPhoneCache.set(key, finalPhone);
  return { BRANCH: finalBranch, PHONE: finalPhone };
}

async function populateBranchNames(root) {
  if (!root?.descendants) return;
  const nodesWithIfsc = root.descendants().filter(n => n?.data?.ifsc);
  if (nodesWithIfsc.length === 0) return;
  const uniqueIfsc = [...new Set(nodesWithIfsc.map(n => n.data.ifsc))];
  await Promise.all(uniqueIfsc.map(ifsc => fetchBranchInfo(ifsc)));
  nodesWithIfsc.forEach(n => {
    const cachedBranch = branchCache.get(n.data.ifsc);
    n.data.branch = cachedBranch || 'Unknown';
    n.data.branch_phone = branchPhoneCache.get(n.data.ifsc) || '';
  });
}

// Setting layerwise colours of node
const layerColors = {
  1: '#A7F3D0', 2: '#F97316', 3: '#f8f7f5ff',
  4: '#f8f7f5ff', 5: '#f8f7f5ff', 6: '#f8f7f5ff',
  7: '#f8f7f5ff', 8: '#f8f7f5ff', 9: '#f8f7f5ff', 10: '#17b350ff'
};;

const tooltip = d3.select('.tooltip');
const detailsPanel = document.getElementById('detailsPanel');
const detailsContent = document.getElementById('detailsContent');
const closeBtn = document.getElementById('closeDetails');
closeBtn.onclick = () => detailsPanel.style.display = 'none';

const leftPanel = document.getElementById('leftPanel');
const leftContent = document.getElementById('leftContent');
const closeLeft = document.getElementById('closeLeftPanel');
closeLeft.onclick = () => leftPanel.style.display = 'none';

// Put on hold modal elements
const holdModalOverlay = document.getElementById('holdModalOverlay');
const holdTableBody = document.getElementById('holdTableBody');
const holdStatusText = document.getElementById('holdStatusText');
const closeHoldModalBtn = document.getElementById('closeHoldModal');
const holdFilterMenu = document.getElementById('holdFilterMenu');

// Hold table filter state
let holdRowsData = [];
let holdFilters = {};
let holdSort = { column: null, direction: null };
let currentHoldFilterColumn = null;
let holdFilterDocHandler = null;

if (closeHoldModalBtn) {
  closeHoldModalBtn.onclick = closeHoldModal;
}
if (holdModalOverlay) {
  holdModalOverlay.addEventListener('click', (e) => {
    if (e.target === holdModalOverlay) closeHoldModal();
  });
}

let width, height, svg, g, currentRoot = null;
let isFirstDraw = true;
let expandAllActive = false;
svg = d3.select('#treeSvg');
g = svg.append('g').attr('transform', 'translate(80,80)');
// Wider zoom-out range so very wide cases (many sibling accounts) fit on screen.
// Stored on window so the on-screen +/- / fit / pad controls can drive it.
globalThis.zoomBehavior = d3.zoom().scaleExtent([0.04, 4]).on('zoom', e => g.attr('transform', e.transform));
svg.call(globalThis.zoomBehavior);
globalThis.graphSvg = svg;
globalThis.graphG = g;

async function openHoldPopup() {
  if (!holdModalOverlay) return;
  holdModalOverlay.style.display = 'flex';
  if (holdStatusText) holdStatusText.textContent = 'Loading...';
  if (holdTableBody) holdTableBody.textContent = '';
  holdFilters = {};
  holdSort = { column: null, direction: null };
  currentHoldFilterColumn = null;
  if (holdFilterMenu) holdFilterMenu.style.display = 'none';

  try {
    const res = await fetch(`/put_on_hold_transactions/${ackNo}`);
    if (!res.ok) throw new Error('Failed to fetch hold transactions');
    const data = await res.json();

    // Data now already includes branch_name from backend
    renderHoldTable(data || []);
  } catch (err) {
    console.error('Error loading hold transactions', err);
    if (holdStatusText) holdStatusText.textContent = 'Failed to load put-on-hold transactions.';
  }

  // Viewer: make hold modal read-only
  if (isViewer && holdModalOverlay) {
    holdModalOverlay.querySelectorAll('input, select, textarea').forEach(el => el.disabled = true);
    const saveBtn = holdModalOverlay.querySelector('button[type="submit"]');
    if (saveBtn) saveBtn.style.display = 'none';
  }
}

function closeHoldModal() {
  if (holdModalOverlay) holdModalOverlay.style.display = 'none';
}

function renderHoldTable(rows) {
  if (!holdTableBody) return;
  holdRowsData = rows || [];

  if (!holdRowsData || holdRowsData.length === 0) {
    holdTableBody.textContent = '';
    if (holdStatusText) holdStatusText.textContent = 'No put-on-hold transactions found for this complaint.';
    return;
  }

  if (holdStatusText) holdStatusText.textContent = '';
  applyHoldFilters();

  // Attach filter button listeners
  if (holdModalOverlay) {
    holdModalOverlay.querySelectorAll('.hold-filter-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        showHoldFilterMenu(btn);
      };
    });
  }

  holdTableBody.querySelectorAll('.hold-account-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const acc = link.dataset.accountNumber;
      expandHoldAccount(acc);
    });
  });
}

function formatHoldValue(row, column) {
  switch (column) {
    case 'account_number':
      return row.account_number || 'N/A';
    case 'bank_name':
      return row.bank_name || 'N/A';
    case 'branch_name':
      return row.branch_name || 'N/A';
    case 'ifsc_code':
      return row.ifsc_code || 'N/A';
    case 'amount':
      return `₹${Number(row.amount ?? 0).toLocaleString('en-IN')}`;
    case 'court_order_date':
      return row.court_order_date || 'N/A';
    case 'refund_status':
      return row.refund_status || 'N/A';
    case 'refund_amount':
      return row.refund_amount ? `₹${Number(row.refund_amount).toLocaleString('en-IN')}` : 'N/A';
    case 'layer':
      return row.layer == null ? 'N/A' : String(row.layer);
    default:
      return '';
  }
}

function normalizeFilterValue(column, rawValue) {
  if (rawValue === undefined || rawValue === null) return 'N/A';
  const value = String(rawValue).trim();

  if (column === 'amount' || column === 'refund_amount') {
    const numeric = Number(value.replace(/[₹,\s]/g, ''));
    return Number.isFinite(numeric) ? numeric : 'N/A';
  }

  if (column === 'layer') {
    const numeric = Number(value.replace(/[^\d.-]/g, ''));
    return Number.isFinite(numeric) ? numeric : 'N/A';
  }

  return value;
}

function getHoldSortValue(row, column) {
  switch (column) {
    case 'amount':
      return Number(row.amount ?? 0);
    case 'layer':
      return Number(row.layer ?? 0);
    case 'refund_amount':
      return Number(row.refund_amount ?? 0);
    case 'account_number':
      return row.account_number || '';
    case 'bank_name':
      return row.bank_name || '';
    case 'branch_name':
      return row.branch_name || '';
    case 'ifsc_code':
      return row.ifsc_code || '';
    case 'court_order_date':
      return row.court_order_date || '';
    case 'refund_status':
      return row.refund_status || '';
    default:
      return '';
  }
}

function sortHoldRows(rows) {
  if (!holdSort.column || !holdSort.direction) return rows;
  const sorted = [...rows];
  sorted.sort((a, b) => {
    const aVal = getHoldSortValue(a, holdSort.column);
    const bVal = getHoldSortValue(b, holdSort.column);
    if (aVal < bVal) return holdSort.direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return holdSort.direction === 'asc' ? 1 : -1;
    return 0;
  });
  return sorted;
}

function applyHoldFilters() {
  if (!holdTableBody) return;
  const filtered = holdRowsData.filter(row => {
    return Object.entries(holdFilters).every(([col, selected]) => {
      if (!selected || selected.size === 0) return true;
      const value = normalizeFilterValue(col, formatHoldValue(row, col));
      return selected.has(value);
    });
  });

  const sortedRows = sortHoldRows(filtered);

  holdTableBody.textContent = '';

  const fragment = document.createDocumentFragment();

  sortedRows.forEach((row, idx) => {
    const tr = document.createElement('tr');

    // Checkbox
    const tdCheck = document.createElement('td');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'hold-row-select';
    checkbox.dataset.accountNumber = row.account_number || '';
    tdCheck.appendChild(checkbox);
    tr.appendChild(tdCheck);

    // Index
    const tdIndex = document.createElement('td');
    tdIndex.textContent = idx + 1;
    tr.appendChild(tdIndex);

    // Account Number Link
    const tdAccount = document.createElement('td');
    const link = document.createElement('a');
    link.href = '#';
    link.className = 'hold-account-link';
    link.dataset.accountNumber = row.account_number || '';
    link.textContent = row.account_number || 'N/A';
    tdAccount.appendChild(link);
    tr.appendChild(tdAccount);

    // Other Columns
    const columns = [
      row.bank_name || 'N/A',
      row.branch_name || 'N/A',
      row.ifsc_code || 'N/A',
      formatHoldValue(row, 'amount'),
      formatHoldValue(row, 'court_order_date'),
      formatHoldValue(row, 'refund_status'),
      formatHoldValue(row, 'refund_amount'),
      row.layer || 'N/A'
    ];

    columns.forEach(text => {
      const td = document.createElement('td');
      td.textContent = text;
      tr.appendChild(td);
    });

    fragment.appendChild(tr);
  });

  holdTableBody.appendChild(fragment);

  holdTableBody.querySelectorAll('.hold-account-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const acc = link.dataset.accountNumber;
      expandHoldAccount(acc);
    });
  });

  // No per-row letter buttons; header edit (pencil) opens the letter popup for selected rows
}

function showHoldFilterMenu(button) {
  if (!holdFilterMenu) return;
  const column = button.dataset.column;
  currentHoldFilterColumn = column;

  const allValues = [...new Set(
    holdRowsData.map(row => normalizeFilterValue(column, formatHoldValue(row, column)))
  )].sort((a, b) => {
    const aNum = typeof a === 'number';
    const bNum = typeof b === 'number';
    if (aNum && bNum) return a - b;
    if (aNum) return -1;
    if (bNum) return 1;
    return String(a).localeCompare(String(b), undefined, { numeric: true });
  });

  const selected = holdFilters[column]
    ? new Set([...holdFilters[column]].map(v => normalizeFilterValue(column, v)))
    : new Set(allValues);

  holdFilterMenu.textContent = '';

  // Header
  const headerDiv = document.createElement('div');
  headerDiv.className = 'menu-header';
  const headerSpan = document.createElement('span');
  headerSpan.textContent = `Filter by ${button.parentElement?.textContent?.trim() || column}`;
  headerDiv.appendChild(headerSpan);
  const closeBtn = document.createElement('button');
  closeBtn.setAttribute('aria-label', 'Close filter');
  closeBtn.style.cssText = 'border:none;background:none;cursor:pointer;font-size:16px;';
  closeBtn.textContent = '×';
  headerDiv.appendChild(closeBtn);
  holdFilterMenu.appendChild(headerDiv);

  // Search
  const searchDiv = document.createElement('div');
  searchDiv.className = 'menu-search';
  searchDiv.style.cssText = 'padding: 8px 12px; border-bottom: 1px solid #e5e7eb;';
  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = 'Search...';
  searchInput.style.cssText = 'width: 100%; padding: 6px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 13px;';
  searchDiv.appendChild(searchInput);
  holdFilterMenu.appendChild(searchDiv);

  // Sort
  const sortDiv = document.createElement('div');
  sortDiv.className = 'menu-sort';
  const ascBtn = document.createElement('button');
  ascBtn.type = 'button';
  ascBtn.dataset.sort = 'asc';
  ascBtn.textContent = 'Ascending ↑';
  sortDiv.appendChild(ascBtn);
  const descBtn = document.createElement('button');
  descBtn.type = 'button';
  descBtn.dataset.sort = 'desc';
  descBtn.textContent = 'Descending ↓';
  sortDiv.appendChild(descBtn);
  holdFilterMenu.appendChild(sortDiv);

  // Actions
  const actionsDiv = document.createElement('div');
  actionsDiv.className = 'menu-actions';
  const selectAllBtn = document.createElement('button');
  selectAllBtn.type = 'button';
  selectAllBtn.dataset.action = 'select-all';
  selectAllBtn.textContent = 'Select All';
  actionsDiv.appendChild(selectAllBtn);
  const clearAllBtn = document.createElement('button');
  clearAllBtn.type = 'button';
  clearAllBtn.dataset.action = 'clear-all';
  clearAllBtn.textContent = 'Clear';
  actionsDiv.appendChild(clearAllBtn);
  holdFilterMenu.appendChild(actionsDiv);

  // Body
  const bodyDiv = document.createElement('div');
  bodyDiv.className = 'menu-body';
  allValues.forEach(val => {
    const label = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = val;
    if (selected.has(val)) cb.checked = true;
    label.appendChild(cb);
    const span = document.createElement('span');
    span.textContent = val;
    label.appendChild(span);
    bodyDiv.appendChild(label);
  });
  holdFilterMenu.appendChild(bodyDiv);

  // Footer
  const footerDiv = document.createElement('div');
  footerDiv.className = 'menu-footer';
  const resetBtn = document.createElement('button');
  resetBtn.className = 'clear-btn';
  resetBtn.type = 'button';
  resetBtn.dataset.action = 'reset';
  resetBtn.textContent = 'Reset';
  footerDiv.appendChild(resetBtn);
  const applyBtn = document.createElement('button');
  applyBtn.className = 'apply-btn';
  applyBtn.type = 'button';
  applyBtn.dataset.action = 'apply';
  applyBtn.textContent = 'Apply';
  footerDiv.appendChild(applyBtn);
  holdFilterMenu.appendChild(footerDiv);

  const rect = button.getBoundingClientRect();
  holdFilterMenu.style.top = `${rect.bottom + globalThis.scrollY + 4}px`;
  holdFilterMenu.style.left = `${rect.left + globalThis.scrollX}px`;
  holdFilterMenu.style.display = 'block';
  holdFilterMenu.setAttribute('aria-hidden', 'false');

  // Search functionality
  // searchInput is already defined above
  searchInput.focus();
  searchInput.onclick = (e) => e.stopPropagation();
  searchInput.oninput = (e) => {
    const term = e.target.value.toLowerCase();
    holdFilterMenu.querySelectorAll('.menu-body label').forEach(label => {
      const text = label.textContent.toLowerCase();
      label.style.display = text.includes(term) ? '' : 'none';
    });
  };

  const closeMenu = () => {
    holdFilterMenu.style.display = 'none';
    holdFilterMenu.setAttribute('aria-hidden', 'true');
    if (holdFilterDocHandler) {
      document.removeEventListener('click', holdFilterDocHandler);
      holdFilterDocHandler = null;
    }
  };

  holdFilterMenu.querySelector('.menu-header button').onclick = (e) => {
    e.stopPropagation();
    closeMenu();
  };

  holdFilterMenu.querySelectorAll('.menu-sort button').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      holdSort = { column, direction: btn.dataset.sort };
      applyHoldFilters();
      closeMenu();
    };
  });

  holdFilterMenu.querySelectorAll('.menu-actions button').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const action = btn.dataset.action;
      holdFilterMenu.querySelectorAll('.menu-body input[type="checkbox"]').forEach(cb => {
        cb.checked = action === 'select-all';
      });
    };
  });

  holdFilterMenu.querySelector('.menu-footer .clear-btn').onclick = (e) => {
    e.stopPropagation();
    holdFilters[column] = new Set();
    applyHoldFilters();
    closeMenu();
  };

  holdFilterMenu.querySelector('.menu-footer .apply-btn').onclick = (e) => {
    e.stopPropagation();
    const selectedValues = new Set();
    holdFilterMenu.querySelectorAll('.menu-body input[type="checkbox"]').forEach(cb => {
      if (cb.checked) selectedValues.add(normalizeFilterValue(column, cb.value));
    });
    holdFilters[column] = selectedValues;
    applyHoldFilters();
    closeMenu();
  };

  holdFilterDocHandler = function onDocClick(evt) {
    if (holdFilterMenu && !holdFilterMenu.contains(evt.target) && evt.target !== button) {
      closeMenu();
    }
  };
  document.addEventListener('click', holdFilterDocHandler);
}

// ── Repeated accounts ──────────────────────────────────────────────────────
// A "repeated account" is the SAME account number that appears as a node in TWO
// OR MORE distinct positions of the fund trail — i.e. a mule / intermediary that
// the money passes through more than once (across branches or layers). A normal
// SPLIT (one account sending onward to several children) leaves that account as a
// SINGLE node, so it is correctly NOT flagged here. Computed once per loaded tree
// (the set never changes when nodes are merely expanded/collapsed).
let repeatedAccounts = new Set();

function computeRepeatedAccounts(root) {
  const counts = new Map();
  // Start below the root so the ACK/root node itself is never counted; every node
  // visited from here is a real account (depth >= 1).
  const stack = [];
  if (root) {
    if (root.children) stack.push(...root.children);
    if (root._children) stack.push(...root._children);
  }
  while (stack.length) {
    const node = stack.pop();
    if (!node) continue;
    const name = node.data?.name ? String(node.data.name).trim() : '';
    if (name && name !== 'N/A' && name.toUpperCase() !== 'NA') {
      counts.set(name, (counts.get(name) || 0) + 1);
    }
    if (node.children) for (const k of node.children) stack.push(k);
    if (node._children) for (const k of node._children) stack.push(k);
  }
  const repeated = new Set();
  counts.forEach((c, name) => { if (c >= 2) repeated.add(name); });
  return repeated;
}

// Per-account detail for the Repeated Accounts list: how many positions an account
// occupies and in which layers / banks. Same traversal/definition as the purple
// marking, so the list and the marking are always consistent.
function computeRepeatedAccountDetails(root) {
  const map = new Map(); // name -> {count, layers:Set, banks:Set}
  const stack = [];
  if (root) {
    if (root.children) stack.push(...root.children);
    if (root._children) stack.push(...root._children);
  }
  while (stack.length) {
    const node = stack.pop();
    if (!node) continue;
    const d = node.data || {};
    const name = d.name ? String(d.name).trim() : '';
    if (name && name !== 'N/A' && name.toUpperCase() !== 'NA') {
      let e = map.get(name);
      if (!e) { e = { count: 0, layers: new Set(), banks: new Set() }; map.set(name, e); }
      e.count += 1;
      if (d.layer != null && d.layer !== '') e.layers.add(d.layer);
      if (d.bank) e.banks.add(d.bank);
    }
    if (node.children) for (const k of node.children) stack.push(k);
    if (node._children) for (const k of node._children) stack.push(k);
  }
  const rows = [];
  map.forEach((e, name) => {
    if (e.count >= 2) {
      rows.push({
        account: name,
        count: e.count,
        layers: [...e.layers].sort((a, b) => Number(a) - Number(b)),
        banks: [...e.banks],
      });
    }
  });
  rows.sort((a, b) => b.count - a.count);
  return rows;
}

// Button handler: open a list modal (like Put-on-Hold) of the repeated accounts.
// It does NOT mass-expand/redraw the tree (which made nodes appear to "vanish");
// the consistent purple marking stays as-is, and each row's Locate button expands
// to that account on demand. Returns the count for the toast.
function findRepeatedAccounts() {
  if (!currentRoot) return 0;
  repeatedAccounts = computeRepeatedAccounts(currentRoot); // keep marking in sync
  const rows = computeRepeatedAccountDetails(currentRoot);

  const tbody = document.getElementById('repeatTableBody');
  const empty = document.getElementById('repeatEmpty');
  const overlay = document.getElementById('repeatModalOverlay');
  if (tbody) {
    tbody.innerHTML = '';
    rows.forEach((r, i) => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        `<td style="padding:6px 10px;">${i + 1}</td>` +
        `<td style="padding:6px 10px;font-family:monospace;">${escapeHtml(r.account)}</td>` +
        `<td style="padding:6px 10px;">${escapeHtml(r.banks.join(', ') || '—')}</td>` +
        `<td style="padding:6px 10px;text-align:center;">${r.count}</td>` +
        `<td style="padding:6px 10px;">${escapeHtml(r.layers.join(', ') || '—')}</td>` +
        `<td style="padding:6px 10px;"></td>`;
      const btn = document.createElement('button');
      btn.textContent = 'Locate';
      btn.style.cssText =
        'background:#7c3aed;color:#fff;border:none;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;';
      btn.onclick = () => locateRepeatedAccount(r.account);
      tr.lastElementChild.appendChild(btn);
      tbody.appendChild(tr);
    });
  }
  if (empty) empty.style.display = rows.length ? 'none' : 'block';
  if (overlay) overlay.style.display = 'flex';
  return rows.length;
}

// From a Repeated Accounts list row: close the modal, expand to that account and
// highlight it (reuses the hold-account expand/highlight machinery).
function locateRepeatedAccount(acc) {
  const overlay = document.getElementById('repeatModalOverlay');
  if (overlay) overlay.style.display = 'none';
  if (typeof expandHoldAccount === 'function') expandHoldAccount(acc);
}

function findPathToAccount(accountNumber) {
  if (!currentRoot || !accountNumber) return null;
  const target = String(accountNumber).trim();
  const stack = [{ node: currentRoot, path: [currentRoot] }];

  while (stack.length > 0) {
    const { node, path } = stack.pop();
    const name = node?.data?.name ? String(node.data.name).trim() : '';
    if (name === target) return path;

    const next = [];
    if (node.children) next.push(...node.children);
    if (node._children) next.push(...node._children);

    next.forEach(child => stack.push({ node: child, path: [...path, child] }));
  }
  return null;
}

function expandNodesInPath(path) {
  if (!path) return;
  path.forEach(n => {
    if (n._children) {
      n.children = n._children;
      n._children = null;
    }
  });
}

function highlightHoldNode(accountNumber) {
  if (!g || !accountNumber) return;
  g.selectAll('.node rect').classed('hold-highlight', false);
  g.selectAll('.node').each(function (d) {
    const name = d?.data?.name ? String(d.data.name).trim() : '';
    if (name === String(accountNumber).trim()) {
      d3.select(this).select('rect').classed('hold-highlight', true);
    }
  });
}

function expandHoldAccount(accountNumber) {
  const path = findPathToAccount(accountNumber);
  if (!path) {
    alert('Account not found in the current graph.');
    return;
  }
  expandNodesInPath(path);
  drawTree(currentRoot);
  highlightHoldNode(accountNumber);
}

// Auto-expand the ancestor path of every Put-On-Hold node so hold accounts are
// visible immediately after load, WITHOUT fully expanding the tree. Reuses the
// existing collapsed-child model (_children) and d3's persistent .parent refs.
// Guarded: any failure degrades to the default collapsed view (graph still loads).
function expandHoldPaths(root) {
  try {
    if (!root) return;
    // Walk the whole hierarchy (including collapsed _children) to find hold nodes.
    const stack = [root];
    const holdNodes = [];
    while (stack.length) {
      const n = stack.pop();
      if (n.data?.hold_info) holdNodes.push(n);
      if (n.children) stack.push(...n.children);
      if (n._children) stack.push(...n._children);
    }
    // For each hold node, expand only its ancestor chain (not its own subtree).
    holdNodes.forEach(h => {
      let n = h.parent;
      while (n) {
        if (n._children) {
          n.children = n._children;
          n._children = null;
        }
        n = n.parent;
      }
    });
  } catch (e) {
    console.error('expandHoldPaths failed; falling back to default expansion', e);
  }
}

function cleanTreeData(root) {
  // Remove children with null or undefined accounts recursively (keep empty strings, "N/A", or "NA" as valid placeholders)
  if (!root?.children) return;
  root.children = root.children.filter(child => {
    if (!child || typeof child !== 'object' || !child.data) return false;
    const name = child.data.name;
    // Exclude only if name is null or undefined
    if (name === null || name === undefined) return false;
    // Recursively clean descendants
    cleanTreeData(child);
    return true;
  });
}

function resizeTree() {
  const headerH = document.querySelector('header')?.clientHeight || 0;
  width = globalThis.innerWidth;
  height = globalThis.innerHeight - headerH;
  svg.attr('width', width).attr('height', height);
}
globalThis.addEventListener('resize', () => {
  resizeTree();
  drawTree(currentRoot);
});
resizeTree();

fetch(`/graph_data/${ackNo}`)
  .then(res => {
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return res.json();
  })
  .then(data => {
    if (!data || data.error) {
      const chartEl = document.getElementById('chart');
      if (chartEl) {
        const message = data.error || 'No graph data found for this Acknowledgement No.';
        chartEl.textContent = '';
        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = 'text-align:center; padding:50px; font-size:18px; color:#666;';
        msgDiv.textContent = message;
        chartEl.appendChild(msgDiv);
      }
      return;
    }
    globalThis.graphData = data; // Set global for statewise summary modal

    // Deep clean the data before creating hierarchy
    function deepCleanData(node) {
      if (!node || typeof node !== 'object') return null;
      if (node.children) {
        node.children = node.children.map(deepCleanData).filter(Boolean);
      }
      return node;
    }

    const cleanedData = deepCleanData(data);
    if (!cleanedData?.children || cleanedData.children.length === 0) {
      console.log('No valid graph data found - cleanedData:', cleanedData);
      const chartEl = document.getElementById('chart');
      if (chartEl) {
        chartEl.textContent = '';
        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = 'text-align:center; padding:50px; font-size:18px; color:#666;';
        msgDiv.textContent = 'No valid graph data found for this Acknowledgement No.';
        chartEl.appendChild(msgDiv);
      }
      return;
    }

    const root = d3.hierarchy(cleanedData);
    if (!root?.children || root.children.length === 0) {
      const chartEl = document.getElementById('chart');
      if (chartEl) {
        chartEl.textContent = '';
        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = 'text-align:center; padding:50px; font-size:18px; color:#666;';
        msgDiv.textContent = 'No valid graph data found for this Acknowledgement No.';
        chartEl.appendChild(msgDiv);
      }
      return;
    }

    // No sanitization needed - let D3 handle the data as is

    if (!root.children || root.children.length === 0) {
      const chartEl = document.getElementById('chart');
      if (chartEl) {
        chartEl.innerHTML = '<div style="text-align:center; padding:50px; font-size:18px; color:#666;">No valid graph data found for this Acknowledgement No.</div>';
      }
      return;
    }

    cleanTreeData(root);
    bfsAssignLayers(root);
    if (!root.children || root.children.length === 0) {
      const chartEl = document.getElementById('chart');
      if (chartEl) {
        chartEl.textContent = '';
        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = 'text-align:center; padding:50px; font-size:18px; color:#666;';
        msgDiv.textContent = 'No valid graph data found for this Acknowledgement No.';
        chartEl.appendChild(msgDiv);
      }
      return;
    }
    root.descendants().forEach(d => {
      if (d.depth > 0) {
        d._children = d.children;
        d.children = null;
      }
    });
    // Smart auto-expansion: reveal every Put-On-Hold account by expanding only the
    // branches that lead to one (the rest stay collapsed). Manual collapse/expand
    // and hold-highlighting behaviour are unaffected.
    expandHoldPaths(root);
    let count = 1;
    root.children?.forEach(child => {
      child.data.victim_label = `Victim ${count++}`;
    });
    currentRoot = root;
    // Flag mule/intermediary accounts that re-appear in the trail (computed once;
    // stable across expand/collapse). The fill logic colours these nodes purple.
    repeatedAccounts = computeRepeatedAccounts(root);
    populateBranchNames(root).then(() => {
      drawTree(root);
      setTimeout(() => drawTree(root), 80);
    });
  })
  .catch(error => {
    console.error('Error fetching graph data:', error);
    const chartEl = document.getElementById('chart');
    if (chartEl) {
      let errorMessage = 'Error loading graph data. Please try again later.';
      if (error.message.includes('500')) {
        errorMessage = 'Server error occurred while processing graph data. Please contact support.';
      } else if (error.message.includes('403')) {
        errorMessage = 'Access Denied: You are not authorized to view this case.';
      } else if (error.message.includes('404')) {
        errorMessage = 'Graph data not found. Please check the Acknowledgement No.';
      } else {
        errorMessage += ' ' + error.message;
      }
      const msgDiv = document.createElement('div');
      msgDiv.style.cssText = 'text-align:center; padding:50px; font-size:18px; color:#666;';
      msgDiv.textContent = errorMessage;
      chartEl.textContent = '';
      chartEl.appendChild(msgDiv);
    }
  });

function bfsAssignLayers(root) {
  if (!root?.data) return;
  const queue = [root];
  root.data.layer = 1;
  while (queue.length > 0) {
    const node = queue.shift();
    if (!node?.data) continue;
    const currentLayer = node.data.layer || 1;
    if (node.children) {
      node.children.forEach(child => {
        if (!child?.data) return;
        child.data.layer = currentLayer + 1;
        queue.push(child);
      });
    }
  }
  // Ensure all descendants have a layer
  if (root.descendants) {
    root.descendants().forEach(d => {
      if (d?.data && !d.data.layer) d.data.layer = 1;
    });
  }
}
// 🧮 Helper: calculate total repeated transaction amount
function getTotalRepeatedAmount(txns) {
  if (!txns || txns.length === 0) return 0;

  const uniqueTxns = Array.from(
    new Map(txns.map(txn => [txn.txn_id, txn])).values()
  );

  return uniqueTxns.reduce((sum, txn) => sum + (Number.parseFloat(txn.amount) || 0), 0);
}

function toggleCollapse(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else if (d._children) {
    d.children = d._children;
    d._children = null;
  }
}

/**
 * Toggle expansion for the whole tree.
 * When expanded, every non-burst node reveals its children.
 * When collapsed, we hide children for all non-root nodes.
 */
// Guards a reveal animation so rapid re-clicks don't start two loops at once.
let expandAllAnimating = false;

function toggleExpandAllNodes() {
  if (!currentRoot) return false;

  expandAllActive = !expandAllActive;

  const btn = document.getElementById('expandAllBtn');
  if (btn) {
    btn.title = expandAllActive ? 'Collapse All Nodes' : 'Expand All Nodes';
    btn.setAttribute('aria-label', btn.title);
  }

  // ── COLLAPSE: cheap (fewer nodes to draw), do it in one pass. Also flips
  //    expandAllActive=false, which signals any in-flight expand animation to stop.
  if (!expandAllActive) {
    const collapse = (node) => {
      if (!node) return;
      const kids = node.children || node._children || [];
      kids.forEach(collapse);
      if (node.children) {
        node._children = node.children;
        node.children = null;
      }
    };
    (currentRoot.children || []).forEach(collapse);
    drawTree(currentRoot);
    return expandAllActive;
  }

  // ── EXPAND: reveal ONE depth-level per animation frame instead of opening the
  //    whole tree synchronously (which froze the browser on large cases). Each pass
  //    opens the shallowest still-collapsed nodes, redraws, then schedules the next
  //    pass — so a big trail unfolds smoothly, layer by layer, and stays responsive.
  if (expandAllAnimating) return expandAllActive;  // a reveal is already running
  expandAllAnimating = true;

  const revealNextLayer = () => {
    if (!expandAllActive) { expandAllAnimating = false; return; }  // user collapsed mid-run

    let openedAny = false;
    const queue = [currentRoot];
    while (queue.length) {
      const node = queue.shift();
      if (!node) continue;
      // Respect the burst (20+ fan-out) rule — never auto-expand those.
      if (node._children && !node.burst) {
        node.children = node._children;
        node._children = null;
        openedAny = true;
        // Its freshly revealed children are handled on the NEXT pass, so the
        // tree grows one level at a time rather than all at once.
        continue;
      }
      const kids = node.children || [];
      for (const k of kids) queue.push(k);
    }

    drawTree(currentRoot);

    if (openedAny) {
      requestAnimationFrame(() => setTimeout(revealNextLayer, 60));
    } else {
      expandAllAnimating = false;  // nothing left to open
    }
  };

  revealNextLayer();
  return expandAllActive;
}

function drawTree(root) {
  if (!root?.children || root.children.length === 0) return;
  g.selectAll('*').remove();
  const layerHeight = 150;
  const maxLayer = d3.max(root.descendants(), d => d?.data?.layer || 1) || 1;
  const requiredHeight = (maxLayer * layerHeight) + 200;
  svg.attr('height', Math.max(height, requiredHeight));
  try {
    root.each(d => {
      if (!d?.data?.layer) return;
      d.y = (d.data.layer - 1) * layerHeight;
    });
    const treeLayout = d3.tree().nodeSize([300, 200]);
    treeLayout(root);
  } catch (error) {
    console.error('Error in drawTree:', error);
    const chartEl = document.getElementById('chart');
    if (chartEl) {
      chartEl.innerHTML = '<div style="text-align:center; padding:50px; font-size:18px; color:#666;">Error rendering graph. Please check the data.</div>';
    }
    return;
  }

  g.selectAll('.link')
    .data(root.links())
    .join('path')
    .attr('class', 'link')
    .attr('d', d3.linkVertical().x(d => d.x).y(d => d.y))
    .attr('stroke', '#888')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none');

  const nodes = g.selectAll('.node')
    .data(root.descendants())
    .join('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${d.x},${d.y})`);

  let victimCounter = 1;
  nodes.each(function (d) {
    const n = d3.select(this);
    if (!d?.data?.layer) return;
    const boxWidth = 250, boxHeight = 140;

    n.append('rect')
      .attr('x', -boxWidth / 2)
      .attr('y', -boxHeight / 2)
      .attr('width', boxWidth)
      .attr('height', boxHeight)
      .attr('rx', 14)
      .attr('fill', d => {
        // Mule/intermediary accounts that recur in the trail are marked purple so
        // the IO can spot reuse at a glance (see computeRepeatedAccounts).
        const acct = d.data?.name ? String(d.data.name).trim() : '';
        if (acct && repeatedAccounts.has(acct)) return '#7c3aed';
        const isLeafNode = !d.children && !d._children;
        if (isLeafNode && !d.burst) return '#15803d';
        return layerColors[d.data.layer] || '#ccc';
      })
      .attr('stroke', d.data.hold_info ? '#dc2626' : '#1e293b')
      .attr('stroke-width', d.data.hold_info ? 3 : 1.5)
      .style('filter', d.data.hold_info
        ? 'drop-shadow(0 0 8px rgba(220, 38, 38, 0.7))'
        : 'drop-shadow(2px 2px 6px rgba(0,0,0,0.15))');

    n.selectAll('text').remove();

    if (d.depth === 0) {
      n.append('text').attr('x', 0).attr('y', -10).attr('text-anchor', 'middle')
        .style('font-size', '13px').style('font-weight', 'bold').style('fill', '#000')
        .text('Acknowledgement No');
      n.append('text').attr('x', 0).attr('y', 10).attr('text-anchor', 'middle')
        .style('font-size', '13px').style('fill', '#000').text(ackNo);
    }

    if (d.depth === 1) {
      const victimNo = victimCounter++;
      n.append('text').attr('x', 0).attr('y', -14).attr('text-anchor', 'middle')
        .style('font-size', '13px').style('font-weight', 'bold').style('fill', '#000')
        .text(`Victim Account No: ${victimNo}`);
      n.append('text').attr('x', 0).attr('y', 6).attr('text-anchor', 'middle')
        .style('font-size', '12px').style('fill', '#000')
        .text(`Acc No: ${d.data.name || 'N/A'}`);
      let bankName = d.data.action || d.data.bank || 'Unknown Bank';

      n.append('text')
        .attr('x', 0).attr('y', 24)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('fill', '#1f2937')
        .text(`Bank: ${bankName}`);

    }
    if (d.data.layer > 2) {

      const isRepeated = d.data.transactions_from_parent &&
        d.data.transactions_from_parent.length > 1;

      // ✅ Remove old amount before adding new
      n.selectAll(".amt-text").remove();

      // Acc No
      n.append("text")
        .attr("x", 0)
        .attr("y", -30)
        .attr("text-anchor", "middle")
        .style("font-size", "13px")
        .style("font-weight", "bold")
        .style("fill", "#000")
        .text(`Acc No: ${d.data.name ?? "Acc ?"}`);

      // Bank Name
      if (d.data.bank) {
        n.append("text")
          .attr("x", 0)
          .attr("y", -10)
          .attr("text-anchor", "middle")
          .style("font-size", "12px")
          .style("fill", "#000")
          .text(`Bank: ${d.data.bank}`);
      }

      n.append('text')
        .attr('x', 0).attr('y', 5)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('fill', '#1f2937')
        .text(`IFSC Code: ${d.data.ifsc}`);

      const branchLabel = d.data.branch || branchCache.get(d.data.ifsc) || 'Unknown';
      const branchText = n.append("text")
        .attr("x", 0)
        .attr("y", 22)
        .attr("text-anchor", "middle")
        .attr("class", "branch-text")
        .style("font-size", "12px")
        .style("fill", "#1f2937")
        .text(`Branch: ${branchLabel}`);

      // If branch is not available yet, fetch it and update the text element
      if (d.data.ifsc && (!d.data.branch || !branchCache.get(d.data.ifsc) || branchCache.get(d.data.ifsc) === 'Unknown')) {
        fetchBranchInfo(d.data.ifsc).then(branchData => {
          const branchName = branchCache.get(d.data.ifsc) || branchData?.BRANCH || 'Unknown';
          d.data.branch = branchName;
          // Update the specific text element
          branchText.text(`Branch: ${branchName}`);
        });
      }

      const amount = Number(d.data.amt || 0).toLocaleString('en-IN');

      if (!isRepeated) {
        n.append("text")
          .attr("class", "amt-text")
          .attr("x", 0)
          .attr("y", 38)
          .attr("text-anchor", "middle")
          .style("font-size", "12px")
          .style("fill", "#000")
          .text(`Amt: ₹${amount}`);
      }

      // For Put-on-Hold accounts, show the refund status as plain text inside the box
      // (single neutral colour — no colour-coding) so the IO sees it without drilling in.
      if (d.data.hold_info) {
        n.append("text")
          .attr("class", "refund-text")
          .attr("x", 0)
          .attr("y", 54)
          .attr("text-anchor", "middle")
          .style("font-size", "11px")
          .style("font-weight", "700")
          .style("fill", "#1f2937")
          .text(`Refund: ${d.data.hold_info.refund_status || 'Not Refunded'}`);
      }

    }

    // Adjust box width and text sizing to prevent overflow
    try {
      const padding = 24;
      let maxTextWidth = 0;
      n.selectAll('text').each(function () {
        const bbox = this.getBBox();
        if (bbox && bbox.width > maxTextWidth) maxTextWidth = bbox.width;
      });
      const currentRect = n.select('rect');
      let adjustedWidth = Math.max(250, Math.min(maxTextWidth + padding, 360));
      currentRect.attr('x', -adjustedWidth / 2).attr('width', adjustedWidth);

      // Reduce font-size for any line still exceeding the box
      n.selectAll('text').each(function () {
        const el = d3.select(this);
        const w = this.getBBox().width;
        const limit = adjustedWidth - padding;
        if (w > limit) {
          const fs = Number.parseFloat(el.style('font-size')) || 12;
          const ratio = Math.max(0.75, Math.min(1, limit / w));
          const newFs = Math.max(10, Math.floor(fs * ratio));
          el.style('font-size', `${newFs}px`);
        }
      });

      // Final fit for branch line if needed
      const branchSel = n.select('.branch-text');
      if (!branchSel.empty()) {
        const w = branchSel.node().getBBox().width;
        const limit = adjustedWidth - padding;
        if (w > limit) {
          branchSel.attr('lengthAdjust', 'spacingAndGlyphs').attr('textLength', limit);
        }
      }
    } catch (e) {
      // silently ignore sizing errors
    }

    const iconData = [];

    if (d.data.atm_info) {
      iconData.push({
        emoji: '💳', onClick: () => {
          leftContent.innerHTML =
            `<strong>ATM Withdrawal</strong><br>` +
            `Account: ${escapeHtml(d.data.name)}<br>` +
            `ATM ID: ${escapeHtml(d.data.atm_info.atm_id)}<br>` +
            (d.data.atm_info.location ? `ATM Location: ${escapeHtml(d.data.atm_info.location)}<br>` : '') +
            `Amount: ₹${escapeHtml(d.data.atm_info.amount)}<br>` +
            `Date: ${escapeHtml(d.data.atm_info.date)}`;
          leftPanel.style.display = 'block';
        }
      });
    }

    // 💥: Burst transaction node (20+ children)
    const totalChildren = (d.children?.length || 0) + (d._children?.length || 0);

    if (d.burst || totalChildren >= 20) {
      if (!d.burst) {
        d.burst = true;
        // Disable expanding this node
        d._children = null;
        d.children = null;
      }
      iconData.push({
        emoji: '💥',
        onClick: () => {
          leftContent.innerHTML = `
           <strong>Burst Transaction Alert</strong><br><br>
           This node has ${escapeHtml(totalChildren)} child transactions.<br>
           To avoid graph clutter, expansion is disabled.
         `;
          leftPanel.style.display = 'block';
        }
      });
    }

    if (d.data.hold_info) {
      iconData.push({
        emoji: '🔒',
        onClick: () => {
          // Get path from root to this hold node
          const path = [];
          let current = d;
          while (current) {
            path.unshift(current);
            current = current.parent;
          }

          // Victim AccNo is the first victim's account (depth 1)
          const victimAccNo = path[1] ? path[1].data.name || 'N/A' : 'N/A';

          const formSectionId = 'holdFormFields';
          const toggleBtnId = 'openHoldFormBtn';

          let html = `<div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">`;
          html += `<strong style="margin:0;">Hold Transaction Details</strong>`;
          // small doc-style icon (from screenshot) to toggle the court/refund form
          html += `<button id="${toggleBtnId}" title="Show/Hide court & refund info" aria-label="Show or hide court and refund info" aria-expanded="false" style="background:#ede9fe; border:1px solid #c4b5fd; border-radius:8px; width:32px; height:32px; display:flex; align-items:center; justify-content:center; cursor:pointer; padding:0; box-shadow: inset 0 0 0 1px #e5e7eb;">`;
          html += `<svg viewBox="0 0 32 40" width="18" height="22" aria-hidden="true" focusable="false">`;
          html += `<rect x="4" y="4" width="24" height="32" rx="2" ry="2" fill="#ede9fe" stroke="#c4b5fd" stroke-width="2"></rect>`;
          html += `<rect x="8" y="10" width="12" height="2" fill="#a78bfa"></rect>`;
          html += `<rect x="8" y="16" width="16" height="2" fill="#a78bfa"></rect>`;
          html += `<rect x="8" y="22" width="14" height="2" fill="#a78bfa"></rect>`;
          html += `<rect x="8" y="28" width="10" height="2" fill="#a78bfa"></rect>`;
          html += `</svg>`;
          html += `</button>`;
          html += `</div>`;
          html += `<strong>Layer:</strong> ${escapeHtml(d.data.layer - 2 || 'N/A')}<br>`;
          html += `<strong>Victim Acc No:</strong> ${escapeHtml(victimAccNo)}<br>`;
          html += `<strong>Put on hold Acc no:</strong> ${escapeHtml(d.data.name || 'N/A')}<br>`;
          html += `<strong>Put on hold by:</strong> ${escapeHtml(d.data.bank || 'N/A')}<br>`;
          html += `<strong>Put on hold Amount:</strong> ₹${escapeHtml(d.data.hold_info.amount)}<br>`;
          html += `<strong>Refund Status:</strong> ${escapeHtml(d.data.hold_info.refund_status || 'Not Refunded')}<br>`;
          if (d.data.hold_info.refund_amount != null && String(d.data.hold_info.refund_amount).trim() !== '') {
            html += `<strong>Refund Amount:</strong> ₹${escapeHtml(d.data.hold_info.refund_amount)}<br>`;
          }
          // Status of MRM (Money Restoration Module): the 7-stage sequential
          // workflow + audit timeline, loaded from the server. Hidden until the
          // doc icon is clicked. Replaces the old single court-date/refund form.
          html += `<div id="${formSectionId}" style="display:none; margin-top:12px; padding:10px 0; border-top:1px solid #e5e7eb;">`;
          html += `<div style="font-weight:700; margin-bottom:8px;">Status of MRM</div>`;
          html += `<div id="mrmContainer" style="font-size:13px;">Loading MRM status…</div>`;
          html += `</div>`;
          // Add PDF button
          html += `<br><button id="downloadHoldGraphPdfBtn" style="background:#10b981; color:white; border:none; padding:8px 16px; border-radius:4px; cursor:pointer;">🖨️ Download Fundtrail</button>`;
          leftContent.innerHTML = html;
          leftPanel.style.display = 'block';

          const formSection = document.getElementById(formSectionId);
          const toggleBtn = document.getElementById(toggleBtnId);
          const mrmContainer = document.getElementById('mrmContainer');
          const holdInfo = d.data.hold_info || {};
          const holdTxnId = holdInfo.txn_id;

          // Doc icon toggles the MRM section; (re)load its state each time it opens.
          if (toggleBtn && formSection) {
            toggleBtn.onclick = () => {
              const isHidden = formSection.style.display === 'none' || formSection.style.display === '';
              formSection.style.display = isHidden ? 'block' : 'none';
              toggleBtn.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
              if (isHidden) loadMrm();
            };
          }

          // ── Status of MRM (Money Restoration Module): 7-stage sequential workflow ──
          function loadMrm() {
            if (!mrmContainer || !holdTxnId) {
              if (mrmContainer) mrmContainer.textContent = 'MRM is unavailable for this transaction.';
              return;
            }
            fetch(`/mrm_timeline/${encodeURIComponent(ackNo)}/${encodeURIComponent(holdTxnId)}`)
              .then(r => (r.ok ? r.json() : Promise.reject(new Error('MRM timeline request failed'))))
              .then(renderMrm)
              .catch(() => { mrmContainer.textContent = 'Failed to load MRM status.'; });
          }

          function renderMrm(mrm) {
            const steps = mrm.steps || [];
            let html = '<ol style="list-style:none; margin:0; padding:0;">';
            steps.forEach(s => {
              const isNext = s.index === mrm.next_step;
              const markInactive = isNext
                ? '<span style="color:#2563eb;">●</span>'
                : '<span style="color:#cbd5e1;">○</span>';
              const mark = s.done
                ? '<span style="color:#10b981; font-weight:700;">✓</span>'
                : markInactive;
              const color = (s.done || isNext) ? '#0f172a' : '#94a3b8';
              const meta = s.done
                ? `<div style="color:#6b7280; font-size:11.5px; margin-left:20px;">Completed: ${escapeHtml(s.date)}</div>`
                : '';
              html += `<li style="padding:5px 0; border-bottom:1px solid #f1f5f9;">
                <div style="display:flex; gap:8px; align-items:center;">${mark}
                  <span style="font-weight:${s.done ? 600 : 500}; color:${color};">${s.index}. ${escapeHtml(s.label)}</span></div>${meta}</li>`;
            });
            html += '</ol>';

            if (mrm.refund_type) {
              const label = mrm.refund_type === 'FULL' ? 'Fully Refunded' : 'Partially Refunded';
              html += `<div style="margin-top:8px; font-size:12.5px;"><b>Refund:</b> ${escapeHtml(label)} — ₹${Number(mrm.refund_amount || 0).toLocaleString('en-IN')}</div>`;
            }

            if (!isViewer && mrm.next_step) {
              const isRefundStage = mrm.next_step === mrm.refund_step;
              html += `<div style="margin-top:10px; padding-top:8px; border-top:1px dashed #e5e7eb;">`;
              html += `<label style="font-weight:600; display:block; margin-bottom:4px;">Next: ${escapeHtml(mrm.next_label)}</label>`;
              html += `<label style="font-size:11.5px; color:#6b7280;">Date of completion</label>`;
              html += `<input id="mrmStageDate" type="date" style="width:100%; padding:6px 8px; border:1px solid #cbd5e1; border-radius:6px; margin-bottom:6px;">`;
              if (isRefundStage) {
                html += `<label style="font-size:11.5px; color:#6b7280;">Refund type</label>`;
                html += `<select id="mrmRefundType" style="width:100%; padding:6px 8px; border:1px solid #cbd5e1; border-radius:6px; margin-bottom:6px;"><option value="FULL">Fully Refunded</option><option value="PARTIAL">Partially Refunded</option></select>`;
                html += `<label style="font-size:11.5px; color:#6b7280;">Amount refunded (₹)</label>`;
                html += `<input id="mrmRefundAmount" type="text" inputmode="decimal" placeholder="₹" style="width:100%; padding:6px 8px; border:1px solid #cbd5e1; border-radius:6px; margin-bottom:6px;">`;
              }
              html += `<button id="mrmSaveBtn" type="button" style="width:100%; background:#2563eb; color:white; border:none; padding:9px 16px; border-radius:8px; cursor:pointer; font-weight:600;">Save Status</button>`;
              html += `</div>`;
            } else if (!mrm.next_step) {
              html += `<div style="margin-top:10px; color:#10b981; font-weight:600;">✓ MRM workflow complete.</div>`;
            }

            if (Array.isArray(mrm.audit) && mrm.audit.length) {
              html += `<div style="margin-top:10px; padding-top:8px; border-top:1px solid #e5e7eb;"><div style="font-weight:600; margin-bottom:4px;">Audit trail</div>`;
              mrm.audit.forEach(a => {
                html += `<div style="font-size:11.5px; color:#475569; margin-bottom:3px;">${a.step}. ${escapeHtml(a.label)} — ${escapeHtml(a.date_completed)} · by ${escapeHtml(a.performed_by || '—')} <span style="color:#94a3b8;">(${escapeHtml(a.recorded_at)})</span></div>`;
              });
              html += `</div>`;
            }

            mrmContainer.innerHTML = html;
            const saveBtn = document.getElementById('mrmSaveBtn');
            if (saveBtn) saveBtn.onclick = () => saveMrm(mrm.next_step, mrm.next_step === mrm.refund_step);
          }

          function saveMrm(step, isRefundStage) {
            const dateEl = document.getElementById('mrmStageDate');
            const dateVal = dateEl ? dateEl.value : '';
            if (!dateVal) { alert('Please enter the date of completion for this stage.'); return; }
            const payload = { ack_no: ackNo, hold_txn_id: holdTxnId, step: step, date: dateVal };
            if (isRefundStage) {
              const typeEl = document.getElementById('mrmRefundType');
              const amtEl = document.getElementById('mrmRefundAmount');
              payload.refund_type = typeEl ? typeEl.value : '';
              const rawAmt = amtEl ? amtEl.value.replace(/[^\d.]/g, '') : '';
              if (!rawAmt) { alert('Please enter the refunded amount.'); return; }
              payload.refund_amount = Number(rawAmt);
            }
            fetch('/save_mrm_status', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
              body: JSON.stringify(payload),
            })
              .then(res => res.json().then(data => ({ ok: res.ok, data })))
              .then(({ ok, data }) => {
                if (!ok || data.status !== 'success') { alert(data.message || 'Failed to save MRM status.'); return; }
                if (isRefundStage) {
                  d.data.hold_info.refund_status = payload.refund_type === 'FULL' ? 'Refunded' : 'Partially Refunded';
                  d.data.hold_info.refund_amount = payload.refund_amount;
                }
                renderMrm(data.mrm);
              })
              .catch(() => alert('Failed to save MRM status.'));
          }

          // Attach click
          document.getElementById('downloadHoldGraphPdfBtn').onclick = () => {
            downloadHoldGraphPdf(path, ackNo);
          };
        }
      });
    }

    if (d.data.cheque_info) {
      iconData.push({
        emoji: '🎫', onClick: () => {
          leftContent.innerHTML =
            `<strong>Cheque Withdrawal</strong><br>` +
            `Account: ${escapeHtml(d.data.name)}<br>` +
            `Cheque No: ${escapeHtml(d.data.cheque_info.cheque_no)}<br>` +
            `Amount: ₹${escapeHtml(d.data.cheque_info.amount)}<br>` +
            `IFSC: ${escapeHtml(d.data.cheque_info.ifsc)}<br>` +
            `Date: ${escapeHtml(d.data.cheque_info.date)}`;
          leftPanel.style.display = 'block';
        }
      });
    }

    if (d.data.incomingFrom && d.data.incomingFrom.length > 1) {
      iconData.push({
        emoji: '📥',
        onClick: () => {
          const incoming = d.data.incomingFrom;
          let html = `<strong>Received from ${escapeHtml(incoming.length)} Accounts</strong><br><br>`;
          html += incoming.map(item =>
            `<div class="detail-row">
              <b>From:</b> ${escapeHtml(item.from || '—')}<br>
              <b>Amt:</b> ₹${escapeHtml(item.amount || '0.0')}<br>
              <b>Date:</b> ${escapeHtml(item.date || '—')}<br>
            </div><hr>`
          ).join('');
          leftContent.innerHTML = html;
          leftPanel.style.display = 'block';
        }
      });
    }

    // 🌀 Handle repeated transactions between parent-child nodes
    // ✅ Only calculate and show total amount if there are multiple transactions
    if (d.data.transactions_from_parent && d.data.transactions_from_parent.length > 1) {
      const txns = d.data.transactions_from_parent;
      const totalAmount = getTotalRepeatedAmount(txns);

      // Remove previous amount display if exists
      n.selectAll(".node-amount").remove();

      // 💰 Show transaction amount (existing line)
      n.append("text")
        .attr("class", "node-amount current")
        .attr("x", 0)
        .attr("y", 42) // Adjust vertical position as needed
        .attr("text-anchor", "middle")
        .style("font-size", "13px")
        .style("fill", "#222")
        .text(`Total amt  ₹${totalAmount.toLocaleString('en-IN')}`);
      // 🔁 Add repeated icon
      iconData.push({
        emoji: "🔁",
        onClick: () => {
          let txnHTML = `
        <strong>${escapeHtml(txns.length)} Transactions between nodes</strong><br>
        <b>Total Amount:</b> ₹${escapeHtml(totalAmount.toLocaleString('en-IN'))}<br><br>
      `;
          txnHTML += txns.map(txn => `
        <div class="detail-row">
          <b>Txn ID:</b> ${escapeHtml(txn.txn_id)}<br>
          <b>Amount:</b> ₹${escapeHtml(txn.amount)}<br>
          <b>Date:</b> ${escapeHtml(txn.date)}<br>
        </div><hr>
      `).join("");
          leftContent.innerHTML = txnHTML;
          leftPanel.style.display = "block";
        }
      });
    }

    // === Icon placement logic ===
    const spacing = 32;
    const startX = -(spacing * (iconData.length - 1)) / 2;
    const iconY = boxHeight / 2 + 10;

    iconData.forEach((icon, i) => {
      const x = startX + i * spacing;
      addIcon(n, x, iconY, icon.emoji, icon.onClick);
    });

    let clickTimer;
    n.on('click', function (event) {
      if (event.target.classList.contains('icon')) return;
      if (d.burst) return;
      clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        toggleCollapse(d);
        drawTree(currentRoot);
      }, 250);
    }).on('dblclick', (event) => {
      event.stopPropagation();
      clearTimeout(clickTimer);
      if (d.data.ifsc) {
        // Use a safe ID (replace non-alphanumeric characters)
        const safeId = `branch-${String(d.data.name || '').replace(/[^a-zA-Z0-9_-]/g, '')}`;

        const isRepeated = Array.isArray(d.data.transactions_from_parent) && d.data.transactions_from_parent.length > 1;
        const branchPhone = d.data.branch_phone || branchPhoneCache.get(d.data.ifsc) || '';
        let baseHtml =
          `<div class="detail-row"><span class="label">Layer:</span> ${escapeHtml(d.data.layer - 2 || '—')}</div>` +
          `<div class="detail-row"><span class="label">Account:</span> ${escapeHtml(d.data.name || '—')}</div>` +
          `<div class="detail-row"><span class="label">IFSC:</span> ${escapeHtml(d.data.ifsc || '—')}</div>` +
          `<div class="detail-row" id="${safeId}"><span class="label">Branch:</span> ${escapeHtml(d.data.branch || branchCache.get(d.data.ifsc) || 'Unknown')}</div>` +
          `<div class="detail-row" id="${safeId}-phone"><span class="label">Branch Phone:</span> ${escapeHtml(branchPhone || '—')}</div>` +
          `<div class="detail-row"><span class="label">Bank/FI:</span> ${escapeHtml(d.data.bank || '—')}</div>`;
        if (!isRepeated) {
          baseHtml +=
            `<div class="detail-row"><span class="label">Date:</span> ${escapeHtml(d.data.date || '—')}</div>` +
            `<div class="detail-row"><span class="label">Txn ID:</span> ${escapeHtml(d.data.txid || '—')}</div>` +
            `<div class="detail-row"><span class="label">Amount:</span> ₹${escapeHtml(d.data.amt || '0.0')}</div>` +
            `<div class="detail-row"><span class="label">Disputed:</span> ₹${escapeHtml(d.data.disputed || '0.0')}</div>`;

          // Only show the letter button where a letter is actually meaningful:
          // a Put-on-Hold account (Layer-1 letters are generated from the toolbar's
          // per-bank button). For ordinary accounts the button is hidden, so there's
          // no empty-ZIP / "Bad Request" path.
          if (d.data.name && d.data.hold_info && typeof globalThis.openLetterModal === 'function' && !isViewer) {
            baseHtml += `
            <div style="text-align:center; margin-top:15px; margin-bottom: 5px;">
              <button class="generate-path-letters-btn" style="background:#10b981; color:white; border:none; padding:8px 12px; border-radius:6px; cursor:pointer; font-size:13px; font-weight:bold; width:100%; box-shadow:0 2px 4px rgba(0,0,0,0.1);" data-account="${escapeHtml(d.data.name)}">
                📜 Generate Letters (Path to Root)
              </button>
            </div>`;
          }
        }
        detailsContent.innerHTML = baseHtml;

        const genPathBtn = detailsContent.querySelector('.generate-path-letters-btn');
        if (genPathBtn) {
          genPathBtn.addEventListener('click', () => {
            const acc = genPathBtn.dataset.account;
            const path = findPathToAccount(acc);
            if (path) {
              const accountsInPath = path
                .filter(n => n.data?.name && n.data.name !== 'Flow' && (n.data.layer === undefined || n.data.layer > 0))
                .map(n => n.data.name);
              const isPoh = Boolean(d.data.hold_info);
              if (typeof globalThis.openLetterModal === 'function') {
                globalThis.openLetterModal(accountsInPath.join(', '), 'suspect', isPoh);
              }
            }
          });
        }

        // If phone or branch missing, fetch and update elements
        if (d.data.ifsc && (!branchPhoneCache.get(d.data.ifsc) || !branchCache.get(d.data.ifsc) || branchCache.get(d.data.ifsc) === 'Unknown')) {
          fetchBranchInfo(d.data.ifsc).then(info => {
            const phone = branchPhoneCache.get(d.data.ifsc) || info?.PHONE || info?.Phone || '';
            const branchName = branchCache.get(d.data.ifsc) || info?.BRANCH || info?.Branch || 'Unknown';
            const phoneEl = document.getElementById(`${safeId}-phone`);
            const branchEl = document.getElementById(`${safeId}`);
            if (phoneEl) phoneEl.innerHTML = `<span class="label">Branch Phone:</span> ${escapeHtml(phone || '—')}`;
            if (branchEl) branchEl.innerHTML = `<span class="label">Branch:</span> ${escapeHtml(branchName || 'Unknown')}`;
          }).catch(() => { });
        }

        // Setup KYC section with current transaction data
        const kycSection = document.getElementById('kycDetailsSection');
        const kycTxnId = document.getElementById('kycTxnId');
        const kycName = document.getElementById('kycName');
        const kycAadhar = document.getElementById('kycAadhar');
        const kycMobile = document.getElementById('kycMobile');
        const kycAddress = document.getElementById('kycAddress');
        const saveKycBtn = document.getElementById('saveKycBtn');
        const editKycBtn = document.getElementById('editKycBtn');
        const kycForm = document.getElementById('kycForm');

        // Hide KYC section by default when new transaction is selected
        if (kycSection) {
          kycSection.style.display = "none";
        }

        // Update form values with current transaction data
        if (kycTxnId) kycTxnId.value = d.data.txid || '';
        if (kycName) kycName.value = d.data.kyc_name || '';
        if (kycAadhar) kycAadhar.value = d.data.kyc_aadhar || '';
        if (kycMobile) kycMobile.value = d.data.kyc_mobile || '';
        if (kycAddress) kycAddress.value = d.data.kyc_address || '';

        // Function to disable KYC inputs
        const disableKycInputs = () => {
          ['kycName', 'kycAadhar', 'kycMobile', 'kycAddress'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = true;
          });
          if (saveKycBtn) saveKycBtn.style.display = "none";
          if (editKycBtn && !isViewer) editKycBtn.style.display = "block";
        };

        // Function to enable KYC inputs
        const enableKycInputs = () => {
          ['kycName', 'kycAadhar', 'kycMobile', 'kycAddress'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = false;
          });
          if (saveKycBtn) saveKycBtn.style.display = "block";
          if (editKycBtn) editKycBtn.style.display = "none";
        };

        // If viewer, disable KYC editing entirely
        if (isViewer) {
          disableKycInputs();
          if (editKycBtn) editKycBtn.style.display = "none";
        } else {
          // Always disable inputs by default (Edit button will enable them)
          disableKycInputs();

          // Add Edit button click handler
          if (editKycBtn) {
            editKycBtn.onclick = null; // Remove old handler
            editKycBtn.onclick = () => {
              enableKycInputs();
            };
          }
        }

        // Remove existing form submit listener if any, then add new one
        if (kycForm) {
          // Create a new form handler function for this transaction
          const formHandler = (e) => {
            if (isViewer) {
              e.preventDefault();
              return;
            }
            e.preventDefault();
            const txnId = document.getElementById('kycTxnId')?.value || '';
            const name = document.getElementById('kycName')?.value || '';
            const aadhar = document.getElementById('kycAadhar')?.value || '';
            const mobile = document.getElementById('kycMobile')?.value || '';
            const address = document.getElementById('kycAddress')?.value || '';

            fetch("/save_kyc", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
              },
              body: JSON.stringify({ txn_id: txnId, name, aadhar, mobile, address }),
            })
              .then((res) => res.json())
              .then((data) => {
                if (data.status === "success") {
                  alert("KYC saved successfully!");
                  d.data.kyc_name = name;
                  d.data.kyc_aadhar = aadhar;
                  d.data.kyc_mobile = mobile;
                  d.data.kyc_address = address;
                  // Disable inputs after saving and show Edit button
                  ['kycName', 'kycAadhar', 'kycMobile', 'kycAddress'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.disabled = true;
                  });
                  const saveBtn = document.getElementById('saveKycBtn');
                  const editBtn = document.getElementById('editKycBtn');
                  if (saveBtn) saveBtn.style.display = "none";
                  if (editBtn && !isViewer) editBtn.style.display = "block";
                } else {
                  alert("Error saving KYC: " + data.message);
                }
              });
          };

          // Remove old listener and add new one
          kycForm.onsubmit = null;
          kycForm.addEventListener("submit", formHandler);
        }
      }

      detailsPanel.style.display = 'block';
      if (d.data.ifsc) {
        const branchEl = document.getElementById(safeId);
        const cached = d.data.branch || branchCache.get(d.data.ifsc);
        if (cached && branchEl) {
          branchEl.innerHTML = `<span class="label">Branch:</span> ${escapeHtml(cached)}`;
        } else {
          fetchBranchInfo(d.data.ifsc).then(branchData => {
            const branchName = branchCache.get(d.data.ifsc) || branchData?.BRANCH || 'Not found';
            d.data.branch = branchName;
            if (branchEl) branchEl.innerHTML = `<span class="label">Branch:</span> ${escapeHtml(branchName)}`;
          });
        }
      }
    });
  });

  // ✅ Center the tree only on the first draw
  if (isFirstDraw) {
    const initialScale = 1;
    const centerX = (width / 2) - root.x;
    const centerY = 80;

    svg.transition().duration(750).call(
      d3.zoom().on('zoom', e => g.attr('transform', e.transform))
        .transform,
      d3.zoomIdentity.translate(centerX, centerY).scale(initialScale)
    );

    isFirstDraw = false;
  }
}
function addIcon(container, x, y, emoji, onClick) {
  container.append('circle')
    .attr('cx', x).attr('cy', y).attr('r', 14)
    .attr('fill', '#ffffffcc').attr('stroke', '#1e293b').attr('stroke-width', 1);
  container.append('text')
    .attr('x', x).attr('y', y + 5).attr('text-anchor', 'middle')
    .attr('class', 'icon')
    .style('font-size', '18px').style('cursor', 'pointer').style('fill', '#000')
    .text(emoji).on('click', onClick);
}

function downloadHoldGraphPdf(path, ackNo) {
  // Exclude the root 'Flow' node from the path
  path = path.slice(1);

  // Prepare data for backend
  const nodes = path.map((node, index) => {
    const d = node.data;
    const isLast = index === path.length - 1;

    // Determine Bank Name logic
    let bankName;
    if (index === 0) {
      bankName = d.action || d.bank || 'Unknown Bank';
    } else {
      bankName = d.bank || "Unknown Bank";
    }

    // Extract Hold Amount for the last node
    let holdAmount = null;
    if (isLast && d.hold_info?.amount) {
      holdAmount = d.hold_info.amount;
    }

    return {
      layer: d.layer || (index + 1).toString(),
      account_number: d.name || "N/A",
      bank: bankName,
      branch: d.branch || branchCache.get(d.ifsc) || "Unknown",
      ifsc: d.ifsc || "N/A",
      txn_id: d.txid || d.txn_id || "N/A",
      amount: d.amt || "0.0",
      disputed_amount: d.disputed || "0.0",
      hold_amount: holdAmount
    };
  });

  const payload = {
    ack_no: ackNo,
    nodes: nodes
  };

  // Send to backend
  // Always send the CSRF token (fall back to the hidden form field if the global is unset).
  const _csrf = (typeof csrfToken !== 'undefined' && csrfToken)
    ? csrfToken
    : (document.querySelector('input[name="csrf_token"]')?.value || '');
  const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': _csrf
  };

  fetch('/download_fundtrail_pdf', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(payload)
  })
    .then(response => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.blob();
    })
    .then(blob => {
      const url = globalThis.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FundTrail_${ackNo}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      globalThis.URL.revokeObjectURL(url);
    })
    .catch(error => {
      console.error('Error generating PDF via backend:', error);
      alert('Failed to generate PDF. Please try again.');
    });
}
