# Verification Profiles

Choose one scale and place it in the contract. Approval of the contract approves that scale and the Hook applies its executable ceiling automatically; never ask the user to configure a separate budget.

| Scale | Use when | Automatic ceiling | Typical argv evidence, when declared |
| --- | --- | ---: | --- |
| `quick` | The change is small, local, reversible, and has a narrow failure surface | 1 unit | The nearest meaningful local check |
| `focused` | An ordinary feature or repair affects behavior but has a bounded owner | 4 units | Direct behavior tests and the closest relevant regression checks |
| `full` | The work changes payments, authentication, authorization, deletion, migration, public contracts, concurrency across boundaries, or another high-impact surface | 10 units | Available full suite plus relevant integration, migration, security, or end-to-end checks |

One `targeted` argv check costs 1 unit, `broad` costs 3, and `deep` security, audit, coverage, integration, load, end-to-end, or benchmark work costs 5. Submit the class honestly. The Hook recognizes runner kind and actual scope separately: one exact file or node may be targeted; filters, multiple targets, directories, and suites are at least broad; one exact integration or security node is broad; and a broad integration or security suite is deep. It raises a lower submission before calculating the batch cost. Each check is an argv array executed with `shell=False`; shell interpreters, chaining, pipes, redirection, background execution, and command substitution are not part of the protocol.

Use present evidence, not task size alone. `focused` is the normal recommendation. Do not inflate `quick` work into broad testing, and do not reduce high-impact work to `quick` merely to save time.

## One cheapest sufficient primary evidence source per condition

Before staging the contract, declare every source once in `verification.evidence` with a unique id, typed `kind`, and short description. Each `verification.done_when` object references exactly one source id through `primary_evidence`. The source must be the cheapest available evidence that is still strong enough to prove that condition on the final relevant revision. One id may cover several conditions; do not split it merely to create one command per sentence.

Use this order as a cost heuristic, not as a substitute for sufficiency:

1. current successful evidence that the relevant mutation did not invalidate;
2. a narrow static, unit, or existing regression check;
3. a focused integration or build check;
4. one representative browser, manual, hosted, or external-system scenario;
5. a broad suite or timed end-to-end flow only when the condition itself concerns that complete flow.

Do not prove one condition twice by default. In particular, do not pair an automated rule test with a browser replay of the same rule, exhaustively exercise equivalent UI permutations, or play through long timed progression when a deterministic state transition can prove the outcome. Use interactive evidence for integration, input, accessibility, or visual behavior that cheaper checks cannot establish. If a primary source fails, becomes stale after a relevant mutation, or is genuinely insufficient, fix or replace that source; do not retain it and add a second proof path.

Sources with `kind: "argv"` run together in the one final `click-gate verify` batch. Every check names its source through `evidence_id`; the batch covers every unresolved argv source, and all checks assigned to one id must pass before that source completes. If the contract declares no argv source, do not invent a local verification batch. When Browser is assigned, declare one source with `kind: "browser"`, reference its id from every covered condition, and collect one serial representative session after the last relevant mutation. The Hook allows at most three calls and 90 measured seconds, limits a tool call timeout to 30 seconds, and rejects obvious waits over five seconds; use deterministic state instead of natural timed progression. A successful Browser call records an observation, then `click-gate evidence` explicitly finalizes that source. Use the same completion command once for collected hosted, manual, or existing evidence. Those three kinds are explicit attestations because the Hook does not independently observe arbitrary external systems. Once every declared source is current for the final mutation revision, stop verifying.

Run the argv-based primary sources together after implementation with `click-gate verify '{"version":2,"checks":[{"evidence_id":"E1","argv":[...],"class":"targeted"}]}'`. Keep checks for the same evidence id adjacent. If an earlier source passes before a later check fails, the Hook retains the successful source and retries only the unresolved ids without allowing the total initial budget to be split. Python verification accepts explicit pytest, unittest, or coverage module runners, including `py -3 -m ...`; it rejects Python `-c` and direct Python scripts. Common recognized forms include exact-file `node --check` and `node --test`, `uv run pytest`, package-manager lint/build scripts, `ruff check`, `mypy`, `tsc --noEmit`, `cargo check`, `cargo clippy`, and `go vet`. Project-wide `node --test` is broad and Node eval/print is not verification. Routine bounded implementation builds use `click-gate mutate` when they may write. A recognizable long-running development server uses `click-gate service` start/stop so its exact isolated child is supervised rather than holding a foreground mutation open. The Hook blocks a needless repeat after success. A failed source gets one unchanged transient retry; further retries require an in-scope mutation. A later mutation makes every completed source stale and permits collection again.

Finalize non-argv evidence with `click-gate evidence '{"version":1,"evidence_id":"E2"}'`. For Browser this succeeds only after a successful current-revision call in the metered session. For `hosted`, `manual`, and `existing`, the command records an explicit completion attestation; do not claim that the Hook proved an unmatched external action. It rejects `argv` ids, which can complete only through their bound runner checks.

In a Git worktree, the runner snapshots tracked content and pre-existing non-ignored untracked content. If protected content changes, verification fails stale and advances the mutation revision instead of recording success. Every newly created non-ignored untracked path is reported and also fails stale; source, application, library, configuration, or migration classification only makes the warning clearer. Git-ignored paths are outside the snapshot. Outside Git, this content-change check is unavailable; command allowlisting, shell-free execution, and revision state still apply.

Accepted capability execution is deterministic for the supplied argv and inferred minimum class, but a custom program can conceal expensive work. Unknown verification-like wrapper names are charged conservatively as `deep`; unrecognized commands are rejected. This guard is not a resource sandbox and does not prove semantic test sufficiency.

Omit `intermediate_gate` normally. Name it only when continuing past a point would make recovery materially harder—for example applying an irreversible migration, deleting data, deploying, or spending money through an external API. A gate is a safety boundary, not a routine checkpoint.
