// Pure utility functions for FundTrail graph flow visualization
// Designed to run both in-browser and inside Node.js test suites.

function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return '';
  return String(unsafe)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function deepCleanData(node) {
  if (!node || typeof node !== 'object') return null;
  if (node.children) {
    node.children = node.children.map(deepCleanData).filter(Boolean);
  }
  return node;
}

function cleanTreeData(root) {
  if (!root?.children) return;
  root.children = root.children.filter(child => {
    if (!child || typeof child !== 'object' || !child.data) return false;
    const name = child.data.name;
    if (name === null || name === undefined) return false;
    cleanTreeData(child);
    return true;
  });
}

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
  if (root.descendants) {
    root.descendants().forEach(d => {
      if (d?.data && !d.data.layer) d.data.layer = 1;
    });
  }
}

function getTotalRepeatedAmount(txns) {
  if (!txns || txns.length === 0) return 0;
  const uniqueTxns = Array.from(
    new Map(txns.map(txn => [txn.txn_id, txn])).values()
  );
  return uniqueTxns.reduce((sum, txn) => sum + (Number.parseFloat(txn.amount) || 0), 0);
}

function computeRepeatedAccounts(root) {
  const counts = new Map();
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

function computeRepeatedAccountDetails(root) {
  const map = new Map();
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

function findPathToAccount(root, accountNumber) {
  if (!root || !accountNumber) return null;
  const target = String(accountNumber).trim();
  const stack = [{ node: root, path: [root] }];

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
      return Number((row.mrm ? row.mrm.refund_amount : null) ?? 0);
    case 'account_number':
      return row.account_number || '';
    case 'bank_name':
      return row.bank_name || '';
    case 'branch_name':
      return row.branch_name || '';
    case 'ifsc_code':
      return row.ifsc_code || '';
    case 'mrm_status':
      return row.mrm ? Number(row.mrm.latest_step ?? 0) : 0;
    case 'refund_type':
      return (row.mrm && row.mrm.refund_type) || '';
    default:
      return '';
  }
}

function sortHoldRows(rows, column, direction) {
  if (!column || !direction) return rows;
  const sorted = [...rows];
  sorted.sort((a, b) => {
    const aVal = getHoldSortValue(a, column);
    const bVal = getHoldSortValue(b, column);
    if (aVal < bVal) return direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return direction === 'asc' ? 1 : -1;
    return 0;
  });
  return sorted;
}

const helpers = {
  escapeHtml,
  deepCleanData,
  cleanTreeData,
  bfsAssignLayers,
  getTotalRepeatedAmount,
  computeRepeatedAccounts,
  computeRepeatedAccountDetails,
  findPathToAccount,
  normalizeFilterValue,
  getHoldSortValue,
  sortHoldRows
};

if (typeof window !== 'undefined') {
  Object.assign(window, helpers);
} else if (typeof globalThis !== 'undefined') {
  Object.assign(globalThis, helpers);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = helpers;
}
