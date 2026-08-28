# Operating Modes

Click stores one user-level default outside the target repository. The setting persists across sessions; a per-turn bypass does not change it.

## First use

When the default is unset, questions, explanations, code review, and simple read-only inspection proceed normally. Before the first supported software mutation, ask one short question:

> Use Click in Always ON mode for future software changes (recommended), or Manual mode only when you mention `@Click`?

After the user answers, run exactly one of:

```text
click-gate default on
click-gate default manual
```

Do not choose on the user's behalf. `click-gate default status` reports the stored value.

## Always ON

Apply the compact contract to software creation, modification, deletion, refactoring, and repair. Questions, explanations, and simple read-only inspection do not need a contract. The Hook blocks matched mutations until the exact staged contract has been approved and passed from a later `UserPromptSubmit` turn. It also blocks matched plan tools while the staged or incomplete approved session contract remains active.

After final verification passes for the current mutation revision, a later software-change request may stage a fresh contract without `bypass`. An approved contract that is unverified, running, failed, or stale still blocks replacement. Staging the next contract resets its observation, mutation, and verification state and requires a new user approval.

For a read-only code review:

1. Run `click-gate review`.
2. Do not stage a build contract or ask for contract approval.
3. Use `click-gate inspect` with argv arrays for explicit review evidence. Compatible simple direct reads are converted to the same internal structure.
4. Allow one useful repository-wide inventory when needed, then narrow later reads and searches.
5. Reuse successful evidence. The Hook blocks an identical successful structured read or search, and blocks a second successful repository-wide inventory attempt in the same review turn.
6. Report findings without modifying the project. A later request to fix findings starts the normal compact-contract workflow.

The review guard is intentionally narrower than the build gate. It observes structured inspection and compatible simple reads routed through the bundled local Hook. It cannot deduplicate hidden reasoning, hosted search, unmatched connectors, or custom wrappers.

## Manual

Ordinary work remains fail-open only while no Click contract is active. Apply Click when the user selects `@Click` or invokes `$click`; then run `click-gate arm` and use the normal compact-contract workflow. Once a proposal is staged, or approved but incomplete, that session contract blocks ordinary mutations and plan tools across later turns. On the approval or resume turn, arm and pass the exact same contract before editing. Ephemeral turn, review, prompt, and temporary session state may age out after seven days, but staged and approved-incomplete contracts are never removed by that cleanup. A per-turn bypass suspends enforcement only for its authorized turn; it does not release or erase an active contract.

## User-authorized bypass and cancel

A bypass is authorized only when the first line of the current user prompt is either the plain directive:

```text
@Click bypass
```

or the trusted Click autocomplete form:

```text
[@Click](plugin://click@click) bypass
```

The `@Click` label and `bypass` action are case-insensitive, but the plugin URI must be exactly `plugin://click@click`. The directive line must contain no other text; the task can continue on later lines. Then run `click-gate bypass` once in that same turn. The authorization marker is one-use and cannot carry into another turn. Bypass leaves any staged or approved-incomplete contract intact; it only suspends Click enforcement for the authorized turn. The persistent Always ON or Manual preference is unchanged.

To discard an active contract, use the corresponding plain or trusted autocomplete `cancel` form:

```text
@Click cancel
[@Click](plugin://click@click) cancel
```

Then run `click-gate cancel` once in that turn. Cancel clears the active contract and review state but does not change the persistent mode. A bare `click-gate bypass` or `click-gate cancel` without its matching user directive is denied.

The legacy `click-gate mode strict|adaptive` command remains available as a session-only compatibility control. Prefer the persistent default modes for normal use.
