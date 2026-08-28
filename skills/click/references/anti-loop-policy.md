# Anti-loop Policy

Apply the build guards after the exact staged Click contract has been approved and passed. In Always ON code-review mode, apply only the read-only observation guards without requiring a build contract. Manual work where Click was not explicitly invoked remains fail-open.

## Hard observable guards

1. **Reuse successful evidence.** Approved read-only Bash commands are executed by the local observation runner. It stores a normalized command digest, mutation revision, exit code, output size, and status—not the command or output. An identical successful read or search is blocked until an in-scope mutation clears the evidence ledger.
2. **Retry bounded failures, not loops.** A failed command or output larger than 48,000 bytes may be retried unchanged once. If it still fails or remains incomplete, narrow or change the command. Do not repeat it again.
3. **Do not replan after approval.** Matched `update_plan` tool calls and every attempt to restage or replace the approved contract are blocked. Implement directly from the compact contract. If the approved outcome or boundary must change, stop and ask the user.
4. **Do not reopen repository inventory.** After approval, repository-wide inventory commands such as root-level `rg --files`, `find .`, recursive root `ls`/`Get-ChildItem`, `tree`, `git ls-files`, or an unscoped recursive `git ls-tree` are blocked. Path-scoped inventory and concrete content searches remain available.
5. **Keep broad verification in the budget.** Recognized full-suite, security, coverage, audit, end-to-end, and benchmark checks must run through `click-gate verify` and fit the approved scale.

## Read-only code review

When Always ON is active and the user requests code review without changes, run `click-gate review`. Do not create or approve a build contract. One repository-wide inventory may be used to establish review context; after a successful inventory, narrow later reads and searches. Identical successful matched shell observations are blocked for the review turn. Mutations and plan-tool churn are rejected while review mode is active.

Questions, explanations, and simple read-only lookups do not enter review mode and are not recorded in the observation ledger.

A source mutation clears the successful observation ledger because earlier file evidence may be stale. A read/search or final verification already running blocks a concurrent mutation so the recorded result cannot silently describe different code.

## What the Hook cannot observe

The Hook cannot inspect hidden reasoning, detect a plan written only in prose, cover reads performed through an unmatched connector or hosted tool, prove that a natural-language boundary was obeyed semantically, or stop a custom wrapper from concealing work. These guards reduce visible tool loops; they are not a reasoning-token cap, semantic proof, or security/resource sandbox.

When a guard blocks an action, use existing evidence, narrow the command, make the necessary in-scope correction, or report a real boundary blocker. Do not rename or wrap the same work merely to bypass the guard.
