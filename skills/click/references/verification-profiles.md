# Verification Profiles

Choose one scale and place it in the contract. Approval of the contract approves that scale and the Hook applies its executable ceiling automatically; never ask the user to configure a separate budget.

| Scale | Use when | Automatic ceiling | Final batch |
| --- | --- | ---: | --- |
| `quick` | The change is small, local, reversible, and has a narrow failure surface | 1 unit | The nearest meaningful check plus final diff/status inspection |
| `focused` | An ordinary feature or repair affects behavior but has a bounded owner | 4 units | Direct behavior tests, the closest relevant regression checks, and final diff/status inspection |
| `full` | The work changes payments, authentication, authorization, deletion, migration, public contracts, concurrency across boundaries, or another high-impact surface | 10 units | Available full suite plus relevant integration, migration, security, or end-to-end checks |

One `targeted` argv check costs 1 unit, `broad` costs 3, and `deep` security, audit, coverage, integration, load, end-to-end, or benchmark work costs 5. Submit the class honestly. The Hook recognizes runner kind and actual scope separately: one exact file or node may be targeted; filters, multiple targets, directories, and suites are at least broad; one exact integration or security node is broad; and a broad integration or security suite is deep. It raises a lower submission before calculating the batch cost. Each check is an argv array executed with `shell=False`; shell interpreters, chaining, pipes, redirection, background execution, and command substitution are not part of the protocol.

Use present evidence, not task size alone. `focused` is the normal recommendation. Do not inflate `quick` work into broad testing, and do not reduce high-impact work to `quick` merely to save time.

Run `done_when` checks together after implementation with `click-gate verify '{"version":1,"checks":[{"argv":[...],"class":"targeted"}]}'`. Python verification accepts explicit pytest, unittest, or coverage module runners, including `py -3 -m ...`; it rejects Python `-c` and direct Python scripts. Common recognized forms include `uv run pytest`, package-manager lint/build scripts, `ruff check`, `mypy`, `tsc --noEmit`, `cargo check`, `cargo clippy`, and `go vet`. Routine implementation builds, app runs, and narrow feedback use `click-gate mutate` when they may write. The Hook blocks a needless repeat after success. A failed batch gets one unchanged transient retry; further retries require an in-scope mutation. A later mutation makes a successful result stale and permits the same batch again.

In a Git worktree, the runner snapshots tracked content and pre-existing non-ignored untracked content. If protected content changes, verification fails stale and advances the mutation revision instead of recording success. Every newly created non-ignored untracked path is reported; a new path under a source, application, library, configuration, or migration directory also fails stale, while a generic generated report only warns. Git-ignored paths are outside the snapshot. Outside Git, this content-change check is unavailable; command allowlisting, shell-free execution, and revision state still apply.

Accepted capability execution is deterministic for the supplied argv and inferred minimum class, but a custom program can conceal expensive work. Unknown verification-like wrapper names are charged conservatively as `deep`; unrecognized commands are rejected. This guard is not a resource sandbox and does not prove semantic test sufficiency.

Omit `intermediate_gate` normally. Name it only when continuing past a point would make recovery materially harder—for example applying an irreversible migration, deleting data, deploying, or spending money through an external API. A gate is a safety boundary, not a routine checkpoint.
