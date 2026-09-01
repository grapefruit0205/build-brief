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

The adapter shares Click's Evidence/Guarded/Off lifecycle, contract validation,
evidence ledger, verification classifier, and shell-free runners with the Codex
plugin. It maps Antigravity lifecycle and mutation tools onto that common runtime.

## Modes

- **Evidence** is the default: Antigravity retains host authority while Click records prompt lineage, mutation revisions, exact checks, cache lineage, and an approval-free receipt.
- **Guarded** adds one human-readable approval contract for higher-risk work.
- **Off** leaves ordinary work unmanaged; explicit `@Click` may still start Guarded.

Existing pre-v2 `on` and `manual` preferences migrate once to Evidence. An active Guarded contract remains locked until completion or explicit cancellation.

## Enforce the boundary, not the reasoning

> **Click constrains what observable execution may do—not how the model must
> think.**

Antigravity still decides which files to inspect, how to reason about the task,
which implementation to choose, and which concrete checks to run inside the
current intent or approved contract. Click hard-enforces receipt integrity and,
in Guarded mode, approval and mutation authority, plus replay and tampering
protection.

## Reuse proof when its inputs have not changed

A new revision does not automatically make every passing check useless. Click's
**dependency-aware revision cache** can carry an exact success forward only
while the resolved dependency files and content, exact check, environment,
executable, Antigravity host-coverage digest, and approved mutation snapshot
still match.

```text
revision 12  auth code changed  → run auth tests → pass
revision 13  README only changed → proof inputs unchanged → reuse the pass
revision 14  auth code changed  → proof inputs changed → rerun the tests
```

Antigravity's matching mutation events close this proof boundary. If a required
dependency or post-mutation observation is missing, ambiguous, or different,
Click fails closed and runs the check again. That can avoid rerunning a large
test suite after an unrelated documentation edit without merely trusting the
model's claim that the earlier result is still valid.

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
  commands therefore run through the exact absolute `antigravity_gate.py
  control` launcher injected at each `PreInvocation`. Bare, relative, or
  lookalike Python launchers are rejected. The accepted launcher is one
  expansion-free Bash command; shell chaining, redirects, substitutions, globs,
  and multiline suffixes fail closed.
- Direct read-only `run_command` calls are denied because the Hook cannot replace
  their argv with Click's trusted executable. Use `control inspect` instead.
  Native file/search tools and unrelated MCP, Skill, and Plugin tools remain
  available.
- Structured broad requests sent through the exact `control inspect` launcher
  forward Click's non-blocking narrowing advisory while continuing execution.
  A prior cross-digest broad request that is running or successful does not
  block them. A completed exact-digest request may run again under a fresh
  one-use authorization with advisory context; an active same-digest
  reservation and all runner safety checks remain hard.
- Native Antigravity file/search tools are not routed through Click's local
  observation runner, so cross-tool repeat guidance is not claimed.
- Matching mutation `PreToolUse` and `PostToolUse` events close the Git snapshot
  boundary for optional dependency-aware argv receipt reuse. Missing or
  mismatched post state falls back to executing verification.
- Successful argv receipts bind the registered Antigravity tool surface with a
  `known-surfaces-only` digest. This prevents cross-host or registry-drift reuse
  but cannot observe a capability for which Antigravity emits no Hook event.
- `receipt export` and `receipt verify <path>` run through the same exact
  launcher and retain the explicit `unsigned-integrity-only` assurance.
- `update_plan` and `create_plan` remain available. While a Click lifecycle is
  active, the adapter returns advisory context explaining that plan output
  cannot grant mutation authority or replace, widen, or complete the contract.
- No Antigravity Browser tool is currently bound to Click's Browser evidence
  meter. Do not declare `kind: browser` in an Antigravity contract.

These limits keep unsupported host behavior explicit instead of weakening the
shared Codex runtime or claiming feature parity that the available Hook fields
cannot prove.
