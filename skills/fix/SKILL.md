---
name: fix
description: When explicitly invoked with a software defect or unwanted behavior, translate the natural-language report and repository evidence into one compact repair contract, explain it plainly, then fix it in one approved shot. Never invoke implicitly.
---

# Fix

Turn a natural-language bug report into a repository-aware developer repair directive. `$fix` is the narrow repair entry point bundled with Click; it uses the same contract lock, implementation freedom, and final verification profiles.

## Explicit invocation only

Activate only when the user selects Fix or invokes `$fix`. Do not infer activation from words such as “bug,” “broken,” or “fix.” Codex Skills use `$fix`; do not promise a native `/fix` command.

Run `click-gate arm` before any mutation. If the user opts out, run `click-gate bypass`.

## Translate the defect without serial questions

Start from the reported symptom and trace the narrowest owning behavior, relevant state, public contract, and focused tests. Separate confirmed repository evidence from a hypothesis. Resolve technical choices yourself and expose any consequential assumption in the contract instead of asking a sequence of implementation questions.

Before staging, read [Click's contract format](../click/references/directive-format.md), [verification profiles](../click/references/verification-profiles.md), [anti-loop policy](../click/references/anti-loop-policy.md), and [structured capability protocol](../click/references/capability-protocol.md). Produce the same six-area contract: `outcome`, scoped `boundary`, `must_hold`, compact `build`, `verification`, and `plain_language`. Omit optional build semantics, order, and an intermediate gate unless the defect genuinely requires them.

Choose `quick`, `focused`, or `full`; approval of the repair contract approves that scale and its automatically enforced unit ceiling. Prefer one final completion batch. Add an intermediate gate only for an irreversible or externally consequential boundary.

## Approve once, repair once

Stage the exact contract with `click-gate stage`, show the developer repair directive and its faithful easy explanation, and ask once for approval. Stop without editing. The Hook requires a later `UserPromptSubmit` turn before the exact staged contract can pass; it rejects same-turn pass or replacement staging.

After approval, pass the exact contract with `click-gate pass`, repair the defect continuously without creating a new plan or reopening repository-wide inventory exploration, use `click-gate mutate` for write-capable implementation commands, and submit the smallest sufficient argv completion batch once with `click-gate verify '{"version":1,"checks":[{"argv":[...],"class":"targeted"}]}'`. Reuse successful structured read/search evidence; narrow or materially change the query when more evidence is needed. The Hook blocks observable repetition, blocks plan tools throughout the active workflow, infers each recognized check's minimum cost class, and meters the completion batch. Verification rejects Python `-c` and direct Python scripts; in a Git worktree, changing tracked or already-present untracked content makes the batch fail stale. A failed batch may be retried after the in-scope fix; one unchanged transient retry is allowed. A successful batch is not repeated unless a later mutation makes it stale. Within the approved outcome, boundary, must-hold conditions, and verification commitment, freely choose necessary dependencies, MCP tools, external services, graders, files, and low-level tactics without a replacement contract or reapproval.

Stop only for missing authority, an uncovered irreversible or paid external action, or a required change to the approved outcome or semantic boundary. Otherwise finish the repair in one shot and report what changed and whether the completion checks passed.
