# Click for Google Antigravity

This directory is the source manifest for Click's experimental Google
Antigravity adapter. Build the self-contained package from the repository root:

```bash
python3 scripts/build_antigravity_distribution.py
agy plugin install ./dist/antigravity
```

For Antigravity IDE, the generated `dist/antigravity` directory can instead be
copied to either `.agents/plugins/click` in one workspace or
`~/.gemini/config/plugins/click` globally.

The adapter shares Click's contract validation, state machine, evidence ledger,
verification classifier, and shell-free runners with the Codex plugin. It maps
Antigravity lifecycle and mutation tools onto that common runtime.

## Current platform limits

- Proposal and approval separation requires a fully idle `model_stop`, a new
  readable user transcript entry, and the following `PreInvocation`. The Skill
  still interprets whether the user's words actually approve the proposal. If
  the transcript cannot be read, approval advancement fails closed.
- Antigravity does not expose a `UserPromptSubmit` equivalent. Plain
  `@Click bypass` and `@Click cancel` authorization is recovered from the latest
  readable user entry in `transcript.jsonl`; if it cannot be recovered, those
  actions fail closed.
- Antigravity `PreToolUse` cannot rewrite tool arguments. Structured Click
  commands therefore run through the bundled `antigravity_gate.py control`
  launcher.
- Native Antigravity file/search tools are not routed through Click's local
  observation runner, so cross-tool duplicate-read blocking is not claimed.
- No Antigravity Browser tool is currently bound to Click's Browser evidence
  meter. Do not declare `kind: browser` in an Antigravity contract.

These limits keep unsupported host behavior explicit instead of weakening the
shared Codex runtime or claiming feature parity that the available Hook fields
cannot prove.
