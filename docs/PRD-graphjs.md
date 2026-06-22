# PRD — `main/static/graph.js` (FundTrail fund-flow graph)

**File:** `main/static/graph.js` · **Consumer:** `main/templates/graph_tree1.html` (D3 v7)
**First commit:** `856c936` (2026-06-01, initial import) · **Latest commit:** `8554681` (2026-06-18, MRM)
**Lifetime delta:** 1,759 → 1,944 lines · `+318 / -133` across 5 commits.

## 1. Purpose
Render an interactive directed fund-flow tree for a cybercrime case (ACK no): victim → layered
beneficiary accounts → ATM/cheque cash-outs, with per-node investigative detail, put-on-hold /
refund tracking, repeated-account detection, letter generation, and a government-style PDF export.
It is the investigator's primary visual tool; all data is rendered client-side from `/graph_data`,
`/put_on_hold_transactions`, `/mrm_timeline`, and branch lookups.

## 2. Current functionality (as of `8554681`)
- **Tree rendering (`drawTree`, `resizeTree`, `bfsAssignLayers`, `cleanTreeData`)** — D3 hierarchy with
  per-layer assignment, collapse/expand (`toggleCollapse`, `toggleExpandAllNodes`), zoom/fit controls.
- **Branch enrichment (`fetchBranchInfo`, `populateBranchNames`)** — resolves IFSC → branch/phone,
  cached, rendered into node detail panels.
- **Node detail panels** — account/IFSC/branch/bank/amount/date/txn-id; special icons:
  ATM withdrawal, cheque, burst (>=20 children, expansion disabled), repeated transactions between two
  nodes, multiple incoming sources, put-on-hold.
- **Put-on-hold modal (`openHoldPopup`, `renderHoldTable`, filters/sort: `applyHoldFilters`,
  `showHoldFilterMenu`, `sortHoldRows`, `formatHoldValue`)** — tabular hold view with per-column
  filtering and sorting.
- **MRM (Money Restoration Module) 7-stage workflow** — in the hold node's left panel: a vertical
  status timeline (green check + completion dates), a "next stage" form (date; refund type FULL/PARTIAL +
  amount on stage 6), and an audit trail (who/what/when), wired to `/save_mrm_status` and
  `/mrm_timeline`. Replaced the original single court-date/refund-status form.
- **Repeated-account detection (`computeRepeatedAccounts`, `computeRepeatedAccountDetails`,
  `findRepeatedAccounts`, `locateRepeatedAccount`)** — flags accounts recurring across the trail and
  jumps to them (`findPathToAccount`, `expandNodesInPath`, `highlightHoldNode`, `expandHoldAccount`).
- **Letter generation** — "Generate Letters (Path to Root)" on hold accounts.
- **PDF export (`downloadHoldGraphPdf`)** — government-style fund-trail PDF for a hold path.
- **Security** — `escapeHtml()` applied to all uploaded-data interpolations; CSRF token always sent;
  no inline `on*` handlers (CSP-nonce safe; uses `addEventListener`).

## 3. Original functionality (as of `856c936`)
Core D3 tree, branch-name population, hold modal with filter/sort, ATM/cheque/burst/repeated/incoming
node icons, path-find/highlight helpers, a **single court-order-date + refund-status + refund-amount
form** (`attachAmountFormatter`) in the hold panel posting to `/save_hold_refund`, and a PDF download.
No zoom/fit controls, no dedicated repeated-account analysis module, no MRM workflow, weaker output
escaping, and some inline handlers.

## 4. Delta (first -> latest)
**Added**
- Repeated-account analysis module (`computeRepeatedAccounts`, `computeRepeatedAccountDetails`,
  `findRepeatedAccounts`, `locateRepeatedAccount`).
- MRM 7-stage timeline + audit UI (nested `loadMrm`/`renderMrm`/`saveMrm` in `drawTree`).
- Zoom / fit-to-screen controls (commit `80207ce`); government-style PDF (`80207ce`).
- Systematic `escapeHtml()` on user data; always-on CSRF; refund-visibility improvements (`2a68267`).

**Removed / replaced**
- Court-date/refund-status/amount form and its `attachAmountFormatter` helper -> superseded by MRM.
- Inline `on*` handlers -> `addEventListener` (CSP compliance).

**Refactored**
- `drawTree` grew substantially (hold panel rewritten around MRM).
- Detail-panel string building hardened with escaping throughout.

**Commit timeline**
| Commit | Date | Theme |
|--------|------|-------|
| `856c936` | 2026-06-01 | Initial import |
| `80207ce` | 2026-06-10 | PDF reports; zoom/fit controls |
| `2a68267` | 2026-06-16 | Graph UX, refund visibility, letters, audit |
| `6c6a899` | 2026-06-17 | Standalone-window UX, always-CSRF |
| `8554681` | 2026-06-18 | MRM 7-stage workflow UI + audit trail |

## 5. Known gaps / not production-ready
1. **No automated tests for graph.js** — all logic is verified only via `node --check` + manual use.
   No DOM/unit tests for `renderMrm`, filters, repeated-account math, or path-finding.
2. **Duplicate `getTotalRepeatedAmount`** defined twice (lines ~857 and ~1698) — dead/confusing.
3. **Legacy styling** — relies on `style.css` + inline styles rather than the design-system tokens;
   does not honor dark mode like the rest of the app.
4. **Monolith** — 1,944 lines in one global file; `drawTree` is very large with nested MRM/closure
   logic; hard to test or reason about.
5. **`alert()`-based UX** for save/validation errors (MRM + hold) — not consistent with the app's
   toast/modal system.
6. **No loading/empty/error states** beyond inline text for some async fetches; partial failures of
   `/mrm_timeline` or branch lookups degrade quietly.
7. **Accessibility** — SVG graph + custom panels lack ARIA/keyboard navigation.
8. **Performance** — large trees re-render fully; no virtualization; repeated-account computation
   runs O(n) per open.

## 6. Recommended next steps
1. Extract pure logic (filters, sort, repeated-account math, MRM state->view) into testable modules and
   add a small jsdom/Vitest suite; keep D3 rendering thin.
2. Remove the duplicate `getTotalRepeatedAmount`.
3. Migrate inline styles to design-system tokens so the graph respects dark mode.
4. Replace `alert()` with the app's toast/modal components.
5. Add consistent loading/empty/error states for all fetches.
6. Add ARIA roles + keyboard focus order for panels and node selection.
7. Consider splitting `drawTree` (rendering) from the MRM/hold-panel controller.
