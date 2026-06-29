const test = require('node:test');
const assert = require('node:assert');
const helpers = require('../static/js/graph-helpers.js');

test('escapeHtml sanitizes HTML string inputs', () => {
  assert.strictEqual(helpers.escapeHtml('<script>alert("XSS")</script>'), '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;');
  assert.strictEqual(helpers.escapeHtml('hello & world'), 'hello &amp; world');
  assert.strictEqual(helpers.escapeHtml(null), '');
  assert.strictEqual(helpers.escapeHtml(undefined), '');
});

test('deepCleanData cleans tree structure', () => {
  const data = {
    name: 'Root',
    children: [
      { name: 'Child 1' },
      null,
      { name: 'Child 2', children: [null, { name: 'Grandchild' }] }
    ]
  };
  const cleaned = helpers.deepCleanData(data);
  assert.strictEqual(cleaned.children.length, 2);
  assert.strictEqual(cleaned.children[1].children.length, 1);
  assert.strictEqual(cleaned.children[1].children[0].name, 'Grandchild');
});

test('bfsAssignLayers assigns correct layers to nodes', () => {
  const root = {
    data: { name: 'Root' },
    children: [
      {
        data: { name: 'Child 1' },
        children: [
          { data: { name: 'Grandchild 1' } }
        ]
      },
      { data: { name: 'Child 2' } }
    ]
  };
  // Mock descendants
  root.descendants = () => {
    const list = [root, root.children[0], root.children[0].children[0], root.children[1]];
    return list;
  };
  helpers.bfsAssignLayers(root);
  assert.strictEqual(root.data.layer, 1);
  assert.strictEqual(root.children[0].data.layer, 2);
  assert.strictEqual(root.children[1].data.layer, 2);
  assert.strictEqual(root.children[0].children[0].data.layer, 3);
});

test('getTotalRepeatedAmount calculates sum of unique txn amounts', () => {
  const txns = [
    { txn_id: 't1', amount: '1000' },
    { txn_id: 't1', amount: '1000' }, // duplicate txn_id
    { txn_id: 't2', amount: '500' }
  ];
  assert.strictEqual(helpers.getTotalRepeatedAmount(txns), 1500);
  assert.strictEqual(helpers.getTotalRepeatedAmount([]), 0);
  assert.strictEqual(helpers.getTotalRepeatedAmount(null), 0);
});

test('computeRepeatedAccounts detects multiple occurrences of accounts', () => {
  // Mock hierarchy
  const root = {
    children: [
      { data: { name: 'Acc1' } },
      { data: { name: 'Acc2' } },
      { data: { name: 'Acc1' } } // repeat
    ]
  };
  const repeated = helpers.computeRepeatedAccounts(root);
  assert.ok(repeated.has('Acc1'));
  assert.ok(!repeated.has('Acc2'));
});

test('computeRepeatedAccountDetails returns sorted summary of duplicate accounts', () => {
  const root = {
    children: [
      { data: { name: 'Acc1', layer: 2, bank: 'SBI' } },
      { data: { name: 'Acc2', layer: 2, bank: 'HDFC' } },
      { data: { name: 'Acc1', layer: 3, bank: 'SBI' } },
      { data: { name: 'Acc1', layer: 4, bank: 'ICICI' } }
    ]
  };
  const details = helpers.computeRepeatedAccountDetails(root);
  assert.strictEqual(details.length, 1);
  assert.strictEqual(details[0].account, 'Acc1');
  assert.strictEqual(details[0].count, 3);
  assert.deepStrictEqual(details[0].layers, [2, 3, 4]);
  assert.deepStrictEqual(details[0].banks.sort(), ['ICICI', 'SBI'].sort());
});

test('findPathToAccount searches tree and traces path', () => {
  const root = {
    data: { name: 'Root' },
    children: [
      {
        data: { name: 'Acc1' },
        children: [
          { data: { name: 'Acc3' } }
        ]
      },
      { data: { name: 'Acc2' } }
    ]
  };
  const path = helpers.findPathToAccount(root, 'Acc3');
  assert.strictEqual(path.length, 3);
  assert.strictEqual(path[0].data.name, 'Root');
  assert.strictEqual(path[1].data.name, 'Acc1');
  assert.strictEqual(path[2].data.name, 'Acc3');
});

test('normalizeFilterValue normalizes value types', () => {
  assert.strictEqual(helpers.normalizeFilterValue('amount', '₹1,500.50'), 1500.5);
  assert.strictEqual(helpers.normalizeFilterValue('layer', 'Layer 3'), 3);
  assert.strictEqual(helpers.normalizeFilterValue('bank_name', ' SBI '), 'SBI');
  assert.strictEqual(helpers.normalizeFilterValue('bank_name', null), 'N/A');
});

test('sortHoldRows sorts rows properly', () => {
  const rows = [
    { account_number: 'a1', amount: 500, layer: 3 },
    { account_number: 'a2', amount: 1500, layer: 2 },
    { account_number: 'a3', amount: 200, layer: 4 }
  ];
  const sortedByAmtAsc = helpers.sortHoldRows(rows, 'amount', 'asc');
  assert.strictEqual(sortedByAmtAsc[0].account_number, 'a3');
  assert.strictEqual(sortedByAmtAsc[2].account_number, 'a2');

  const sortedByLayerDesc = helpers.sortHoldRows(rows, 'layer', 'desc');
  assert.strictEqual(sortedByLayerDesc[0].account_number, 'a3');
  assert.strictEqual(sortedByLayerDesc[2].account_number, 'a2');
});
