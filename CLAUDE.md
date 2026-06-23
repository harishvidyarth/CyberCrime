# CLAUDE.md

## Output policy (permanent, applies to every session)
- No conversational text: no "Let me...", "Now I'll...", "Great, that's done", restating the request, or narrating intent before acting.
- No prose explanations of what a fix does — state it as a fact in a table row, not a paragraph.
- Verification is mandatory, but reported as data, not narration:
  - Before an edit to graph.js/graph_tree1.html: assertion check pass/fail only (e.g. "anchor check: PASS").
  - After every commit: `node --check <file>` result as one line: PASS/FAIL.
  - Final report: one table — commit hash | rule | change | risk note. No surrounding text.
- If an edit's pre-check assertion fails: state the failure line and the corrected anchor, nothing else. Do not explain why it failed.
- If something is genuinely ambiguous and needs a human decision: state it as "DECISION NEEDED: <one line>" — not a paragraph of reasoning.
- This applies permanently to all future sessions in this repo. Do not re-explain this policy to the user; just follow it.
