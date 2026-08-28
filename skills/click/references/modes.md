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

Apply the compact contract to software creation, modification, deletion, refactoring, and repair. Questions, explanations, and simple read-only inspection do not need a contract. The Hook blocks matched mutations until the exact staged contract has been approved and passed.

For a read-only code review:

1. Run `click-gate review`.
2. Do not stage a build contract or ask for contract approval.
3. Allow one useful repository-wide inventory when needed, then narrow later reads and searches.
4. Reuse successful evidence. The Hook blocks an identical successful matched shell read or search, and blocks a second successful repository-wide inventory attempt in the same review turn.
5. Report findings without modifying the project. A later request to fix findings starts the normal compact-contract workflow.

The review guard is intentionally narrower than the build gate. It observes recognized Bash or PowerShell reads and searches routed through the bundled Hook. It cannot deduplicate hidden reasoning, hosted search, unmatched connectors, or custom wrappers.

## Manual

Ordinary work remains fail-open. Apply Click only when the user selects `@Click` or invokes `$click`; then run `click-gate arm` and use the normal compact-contract workflow.

## Per-turn bypass

When the user explicitly asks not to use Click for the current turn, run:

```text
click-gate bypass
```

This clears the current Click contract/review state and allows that turn to proceed normally. It does not change the persistent Always ON or Manual preference.

The legacy `click-gate mode strict|adaptive` command remains available as a session-only compatibility control. Prefer the persistent default modes for normal use.
