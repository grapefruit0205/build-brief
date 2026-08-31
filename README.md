# Click — Hook-enforced workflow for Codex coding agents

English | [한국어](README.ko.md) | [简体中文](README.zh-CN.md)

Community: [LINUX DO](https://linux.do/)

[![CI](https://github.com/grapefruit0205/click/actions/workflows/ci.yml/badge.svg)](https://github.com/grapefruit0205/click/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

### Prompt-only coding workflows are over.

> **Prompts can suggest behavior. Hooks can enforce the workflow.**

**Click is a Codex plugin that turns a software-change request into one compact contract, then uses a persistent Hook state machine to keep the observable execution path inside the boundary you approved.**

Most coding-agent workflows still rely on the model remembering instructions such as:

```text
Plan once.
Stay in scope.
Do not rescan the repository.
Do not keep rewriting the plan.
Run only the checks that are actually needed.
```

That works until context grows, the task branches, or the agent decides to plan and prove the same thing again.

Click moves those rules out of prompt-only convention and into the supported tool boundary.

```text
request
   ↓
compact contract
   ↓
Later user turn approval
   ↓
implementation
   ↓
current-revision evidence
   ↓
done
```

> **The model decides how to implement the change. The Hook decides whether the workflow is allowed to move forward.**

**One contract. One approval. One implementation boundary. One evidence set.**

## Core purpose

> **Click binds AI execution to approved intent and returns verifiable evidence.**

Click's stable product boundary is an authorization-and-evidence runtime, not a
model workflow optimizer. The canonical admission test and policy layers are in
the [Click Product Constitution](PRODUCT_CONSTITUTION.md); the current no-behavior-change
inventory is in [Click Guard Classification](GUARD_CLASSIFICATION.md).

v0.24.6 still contains the legacy anti-loop hard gates documented below. Those
guards remain accurately documented until separate changes move strategic rules
to explicit user policy or non-blocking advisory behavior.

## Why Click?

A prompt can tell an agent what it *should* do. Click adds persistent state around what the agent is *allowed* to do on the observable tool path.

| Prompt-only workflow | Click |
| --- | --- |
| Hope the model remembers the plan | Persist the approved workflow state |
| Hope approval happens at the right time | Stage a digest-bound `contract_id` and require a later user turn |
| Ask the agent not to rescan | Allow one useful root inventory, then require narrower inspection |
| Ask the agent not to replan | Reject matched `update_plan` churn while the workflow is active |
| Ask the agent not to rerun proof | Reuse current structured evidence and receipts |
| Let verification expand with the task | Bind completion evidence to an approved verification budget |
| Stop when the agent says it is done | Require declared evidence to be current for the latest mutation revision |

The core idea is simple:

> **Do not keep asking the coding agent to remember the process. Put the process in the execution boundary.**

## What the Hook actually enforces

During staging, implementation, review, and verification, Click can enforce these **observable workflow rules**:

- **Proposal and approval are separate.** Staging emits an opaque `contract_id`; the same user turn cannot both stage and pass it.
- **Mutation waits for approval.** An active contract remains locked until the exact staged ID is approved and passed.
- **Replanning is bounded.** Matched `update_plan` calls are rejected while the Click workflow is active, except for an explicitly authorized one-turn bypass.
- **Repository exploration narrows.** One useful root inventory may run for the current revision; later broad inventories are rejected in favor of path-scoped inspection.
- **Successful observations are reused.** The same successful structured read is not repeated until an in-scope mutation makes it stale.
- **Verification is evidence-bound.** Local checks name the approved `evidence_id` they prove, and cumulative verification stays within the approved scale.
- **Completion follows the code.** A mutation advances the revision and makes older completion evidence stale rather than silently reusing it.
- **Local server lifecycle is owned.** Recognized development servers use Click's managed service path so the exact isolated child can be cleaned up.

The Hook controls the **observable tool path**. It does not inspect hidden reasoning, prove semantic correctness by itself, or act as an operating-system sandbox.

## The compact contract

Click turns the request and relevant repository context into one small execution contract:

| Field | What it fixes |
| --- | --- |
| `outcome` | The concrete result and user-visible behavior |
| `boundary` | What may change and what stays outside the work |
| `must_hold` | Observable safety, compatibility, and correctness promises |
| `build` | The smallest repository-aware implementation route |
| `verification` | One risk-based scale and the evidence that means done |
| `plain_language` | The same contract explained for a non-specialist |

The contract locks the **meaning, boundary, and completion commitment**. It does not freeze every file, dependency, library, or low-level implementation choice.

If the agent discovers that an in-scope file, tool, or dependency is necessary, it can still use it. Reapproval is needed only when the approved outcome, boundary, must-hold behavior, or verification commitment materially changes.

## How it works

```mermaid
flowchart TB
    A["Software change request"] --> B["Compact contract<br/>+ plain explanation"]
    B --> C["Stage once<br/>issue contract_id"]
    C --> D{"Later user turn:<br/>approve?"}
    D -->|Revise| B
    D -->|Cancel| X["Stop"]
    D -->|Approve exact id| E["Implement inside boundary"]
    E --> F["Current-revision evidence"]
    F --> G["Done"]
```

The initial request is **not** approval of an unseen design. Click stages the canonical contract once, receives an opaque `contract_id`, shows the contract, and stops. The next approval passes only that ID, not the JSON again.

When every declared evidence source is current for the latest mutation revision and no managed service remains active, the contract is complete and the next change can start from clean workflow state.

## Quick start

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

Restart the ChatGPT desktop app, inspect and trust the included Click Hook, then start a new task.

On first use, choose **Always ON** to apply Click to software changes by default, or **Manual** to activate it only when you mention `@Click`.

```text
@Click Add order cancellation.
Prevent duplicate refunds and preserve the existing API.
```

You can later say “Set Click to Always ON” or “Set Click to Manual.” A one-turn `@Click bypass` and `@Click cancel` are also available for explicit control.

## Example contract

For the cancellation request above, repository evidence might produce a contract like this:

```json
{
  "outcome": "An eligible order can be cancelled through the existing API and receives at most one refund.",
  "boundary": {
    "in_scope": ["the current cancellation and refund path"],
    "out_of_scope": ["new payment providers", "unrelated order-state cleanup"]
  },
  "must_hold": [
    "Concurrent or repeated requests cannot create a second refund.",
    "Existing request fields, response fields, and status meanings remain compatible."
  ],
  "build": {
    "approach": ["Reuse the current cancellation path and make the refund transition idempotent and atomic."]
  },
  "verification": {
    "scale": "full",
    "evidence": [
      {"id": "E1", "kind": "argv", "description": "cancellation and duplicate-refund tests"},
      {"id": "E2", "kind": "argv", "description": "existing API regression tests"}
    ],
    "done_when": [
      {"condition": "Refund behavior is correct.", "primary_evidence": "E1"},
      {"condition": "The public API remains compatible.", "primary_evidence": "E2"}
    ]
  },
  "plain_language": "Customers can cancel an eligible order, but retries or simultaneous requests cannot refund it twice. Existing API compatibility is preserved."
}
```

The exact design is repository-dependent. The example shows the contract shape, not a universal refund architecture.

## Evidence-driven anti-loop behavior

| Guard | Behavior |
| --- | --- |
| Reuse evidence | A successful identical structured read/search is not repeated until an in-scope mutation makes it stale |
| Block plan churn | Matched `update_plan` calls are rejected while the workflow is armed, staged, approved-but-incomplete, or in review |
| Inventory once, then narrow | The first useful root inventory may run for the current revision; later broad inventories are rejected |
| Make command intent explicit | Ambiguous active shell work is replaced by structured `inspect`, `mutate`, `service`, or `verify` paths |
| Keep verification in one budget | Each local check names its registered `argv` source and cumulative reservations must fit the approved scale |
| Track completion by source | All declared sources must be current; no placeholder local check is invented when no `argv` source exists |
| Deduplicate Browser evidence | Successful normalized Browser input is not repeated; one unchanged retry is allowed after failure |

## Automatic verification budget

Click chooses the smallest sufficient verification scale from the current risk and repository evidence. The user approves that scale as part of the contract.

| Scale | Typical use | Automatic ceiling |
| --- | --- | ---: |
| `quick` | Small, local, reversible change | 1 unit |
| `focused` | Ordinary bounded feature or repair | 4 units |
| `full` | Payments, auth, deletion, migrations, public contracts, or cross-boundary concurrency | 10 units |

A `targeted` check costs 1 unit, `broad` costs 3, and `deep` costs 5. These are ceilings, not targets.

Evidence may come from local `argv` checks or explicitly declared Browser, hosted, manual, or existing sources. An `argv` source completes only through the real success of its linked local runner. Non-argv completion is an explicit attestation; the Hook records the approved source identity and current revision but does not independently prove unmatched external or manual work.

## Structured capabilities

Click separates executables from arguments and uses structured capability paths:

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'
click-gate service '{"version":1,"action":"start","argv":["python3","-m","http.server","4173","--bind","127.0.0.1"]}'
click-gate service '{"version":1,"action":"stop"}'
click-gate evidence '{"version":1,"evidence_id":"E-browser"}'
click-gate verify '{"version":2,"checks":[{"evidence_id":"E1","argv":["python3","-m","pytest","tests/test_cancellation.py"],"class":"targeted"}]}'
```

Recognized reads are constrained by the Hook's read-only capability policy. Exact schemas, trusted executable rules, shell-free execution details, snapshots, claims, and process boundaries live in the [capability protocol](skills/click/references/capability-protocol.md).

Click is a **workflow guardrail**, not an OS security sandbox.

## Google Antigravity adapter — experimental

The repository also builds a self-contained Google Antigravity plugin that shares Click's contract state machine, evidence ledger, verification budget, and shell-free runners.

```bash
python3 scripts/build_antigravity_distribution.py
agy plugin install ./dist/antigravity
```

Antigravity IDE users may also copy `dist/antigravity` into `.agents/plugins/click` for one workspace or `~/.gemini/config/plugins/click` globally.

Antigravity's Hook contract differs from Codex. Native file/search and unrelated MCP or Skill tools remain available, but cross-tool deduplication and Browser evidence are not currently supported. See [`platforms/antigravity/README.md`](platforms/antigravity/README.md) for the exact limits.

## Update an existing installation — v0.24.6

The current release is **v0.24.6**.

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

Restart the ChatGPT desktop app and review/trust the updated Hook. On Windows, v0.24.6 adds Python-launcher fallback and routes Desktop `exec_command` aliases through Click when the host dispatches the matching Hook event. Do not reuse a pending runner command created by an older installation; let the updated Hook issue a fresh one.

Detailed release history is in [RELEASE_NOTES.md](RELEASE_NOTES.md).

## Honest limits

Click makes strong claims only where the Hook can observe and enforce behavior.

It does **not** claim that the Hook can:

- inspect hidden reasoning or a plan written only in prose;
- observe every unmatched connector or hosted tool;
- enforce a host execution path when the Codex client does not dispatch the matching Hook event;
- independently prove semantic boundary compliance or architectural correctness;
- prove that an unmatched manual or external attestation truly occurred;
- stop allowed custom code from hiding multiple operations;
- replace expert review, authorization, deployment controls, or an OS sandbox.

The repository's deterministic suite tests the observable Hook and contract behavior across Linux, macOS, and Windows. Click does not claim project-wide improvements in success rate, accuracy, time, token use, or overdesign without independent measurements on unrelated real repositories.

## Related approaches

Click overlaps with spec-driven, autonomous-loop, and approval-gated tools, but deliberately stays narrow: **one compact contract, one approval, one implementation boundary, observable anti-loop guards, and one bounded evidence commitment.**

See [COMMUNITY_POSTS.md](COMMUNITY_POSTS.md) for ready-to-edit launch copy.

## License

Click is released under the [MIT License](LICENSE).
