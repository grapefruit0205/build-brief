# Anti-loop Policy

Apply the build guards after the exact staged Click contract has been approved and passed. In Always ON code-review mode, apply only the read-only observation guards without requiring a build contract. Manual work where Click was not explicitly invoked remains fail-open.

## Hard observable guards

1. **Reuse successful evidence.** Approved read-only argv requests are executed with `shell=False` by the local observation runner. Compatible simple Bash reads are converted to the same request. The runner stores a normalized request digest, mutation revision, exit code, output size, and status—not argv or output. An identical successful read or search is blocked until an in-scope mutation clears the evidence ledger.
2. **Retry bounded failures, not loops.** A failed command or output larger than 48,000 bytes may be retried unchanged once. If it still fails or remains incomplete, narrow or change the command. Do not repeat it again.
3. **Do not create a parallel plan.** Matched `update_plan` tool calls are blocked in armed, staged, approved/passed, and review turns, and in later turns while the session contract remains staged or approved but incomplete. A completed current-revision contract or explicit bypass releases ordinary later planning. Same-turn second staging, same-turn pass, and mid-run replacement are also blocked. Implement directly from the compact contract. If the approved outcome or boundary must change, stop and ask the user.
4. **Do not reopen repository inventory.** After approval, repository-wide inventory argv such as root-level `rg --files`, `find .`, recursive root `ls`/`Get-ChildItem`, `tree`, `git ls-files`, or an unscoped recursive `git ls-tree` are blocked. Path-scoped inventory and concrete content searches remain available.
5. **Make write intent explicit.** An ambiguous implementation command must use `click-gate mutate`; ordinary edit tools remain deterministic mutations. Direct active Bash is not guessed writable.
6. **Keep broad verification in the budget.** Final checks use argv-based `click-gate verify` entries with submitted `targeted`, `broad`, or `deep` classes. The Hook infers and applies each recognized command's minimum class before checking the approved scale.
7. **Do not mutate through verification.** Python `-c` and direct Python scripts are rejected as checks. In Git worktrees, a final batch that changes tracked or pre-existing untracked content fails stale instead of becoming completion evidence.

## Read-only code review

When Always ON is active and the user requests code review without changes, run `click-gate review`. Do not create or approve a build contract. Use structured inspection or compatible simple direct reads. One repository-wide inventory may establish context; after success, narrow later reads and searches. Identical successful observations are blocked for the review turn. Mutations and plan-tool churn are rejected while review mode is active.

Questions, explanations, and simple read-only lookups do not enter review mode and are not recorded in the observation ledger.

A source mutation clears the successful observation ledger because earlier file evidence may be stale. A read/search or final verification already running blocks a concurrent mutation so the recorded result cannot silently describe different code.

## What the Hook cannot observe

The Hook cannot inspect hidden reasoning, detect a plan written only in prose, cover reads performed through an unmatched connector or hosted tool, prove that a natural-language boundary was obeyed semantically, or stop a custom wrapper from concealing work. These guards reduce visible tool loops; they are not a reasoning-token cap, semantic proof, or security/resource sandbox.

When a guard blocks an action, use existing evidence, narrow the command, make the necessary in-scope correction, or report a real boundary blocker. Do not rename or wrap the same work merely to bypass the guard.
