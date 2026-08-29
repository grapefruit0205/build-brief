# Click

English | [한국어](README.ko.md) | [简体中文](README.zh-CN.md)

Community link: [LINUX DO](https://linux.do/)

[![CI](https://github.com/grapefruit0205/click/actions/workflows/ci.yml/badge.svg)](https://github.com/grapefruit0205/click/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Agree once on what changes and what must hold. Then finish implementation and the necessary checks inside that boundary.

Click is a Codex plugin for people who want coding agents to agree on a software change once and then finish it without repeatedly rewriting the plan, rescanning the repository, or proving the same result twice. It turns your request and the relevant repository context into a short contract—what will change, what must stay true, and what evidence will count—explains it plainly, waits for approval, then keeps implementation and verification inside that boundary.

Choose **Always ON (recommended)** for software changes by default or **Manual** for tasks where you mention `@Click`. Questions, explanations, simple lookup, and read-only review remain lightweight.

## Core purpose

Click's core purpose is to preserve one user-approved boundary from proposal through implementation and necessary verification. It is not a larger specification system or an architecture-pattern picker. Click makes three things explicit—what changes, what must stay true, and what evidence is enough—then blocks observable replanning, repeated repository-wide exploration, and duplicate verification while leaving necessary in-scope implementation choices open.

## Quick start

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

Restart the ChatGPT desktop app, inspect and trust the included Click Hook, then start a new task. Before the first code-changing request, Click asks once:

```text
Use Always ON for future software changes (recommended), or Manual only when I mention @Click?
```

Choose Always ON for the default experience. Choose Manual if you prefer explicit invocation:

```text
@Click Add order cancellation. Prevent duplicate refunds and preserve the existing API.
```

## Update to v0.20.0

If Click is already installed, explicitly refresh its Git marketplace snapshot and reinstall the plugin to load this release:

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

Restart the ChatGPT desktop app, review and trust the updated Click Hook, and start a new task. Existing mode preferences remain outside the target repository. If you call `click-gate` directly, update `pass` to use the emitted `contract_id` instead of contract JSON and migrate inline `done_when` strings to structured evidence references.

You can later say “Set Click to Always ON” or “Set Click to Manual.” Those preferences persist outside the target repository. To bypass Click for exactly one turn, make the first line of that user prompt either `@Click bypass` or the autocomplete form `[@Click](plugin://click@click) bypass`; the Hook authorizes one same-turn `click-gate bypass` and keeps any active contract intact. Use the corresponding `cancel` form to authorize one same-turn `click-gate cancel` and discard the active contract. The `@Click` label and action are case-insensitive, but the plugin URI must match exactly and the directive line cannot contain extra text. The task may continue on later lines. Neither authorization is reusable or carries across turns. Click does not place preference or contract files in your project.

<details>
<summary>Upgrading from Build Brief or an older Click installation</summary>

For `click@build-brief` 0.9.0:

```bash
codex plugin remove click@build-brief
codex plugin marketplace remove build-brief
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

For Build Brief 0.8, replace the first command with `codex plugin remove build-brief@build-brief`.

</details>

## How it works

```mermaid
flowchart TB
    A["First use"] --> B{"Choose once"}
    B -->|Always ON| C["Software changes<br/>use Click automatically"]
    B -->|Manual| D["Use @Click<br/>when wanted"]
    C --> E["Compact contract<br/>+ plain explanation"]
    D --> E
    E --> F["Stage JSON once<br/>receive contract_id"]
    F --> I{"Later user turn:<br/>approve once?"}
    I -->|Revise or cancel| E
    I -->|Approve| G["One-shot implementation"]
    G --> H["One budgeted<br/>final verification"]
```

The initial request is not approval of an unseen design. Click stages the contract JSON once, receives an opaque `contract_id`, shows that id with both contract views, then stops. The Hook records `staged_turn_id` and rejects pass or replacement staging in the same `UserPromptSubmit` turn. A later explicit approval passes only the emitted id—never the JSON again—and the Hook matches it to the staged digest before recording `approved_turn_id`. Revising the proposal issues a new id and invalidates the old handle. This proves that another user response occurred; the Skill still interprets whether that response actually means approval because the Hook does not classify natural-language consent.

Only a real change to the approved result, boundary, must-hold behavior, or verification commitment requires stopping. Necessary files, libraries, tools, services, and implementation tactics inside the approved boundary do not require a replacement contract.

In Manual mode, fail-open behavior applies only when no Click contract is active. Once a contract is staged, or approved but not yet verified for its current revision, that session state keeps ordinary mutations blocked across later turns. This prevents an approval turn from editing before the bound `contract_id` is passed. If an approved implementation is interrupted and resumed in another turn, Click arms and passes the same id before continuing; it does not resend the JSON or invent a replacement contract.

When final verification passes for the current code revision, the next change request can stage a fresh contract normally. Verification that has not run, is running, failed, or became stale after another mutation does not unlock replacement. The new contract starts with clean inspection, mutation, and verification state and needs its own approval; no `bypass` or manual state deletion is required.

## Example: from request to approval

Given this request:

```text
@Click Add order cancellation. Prevent duplicate refunds and preserve the existing API.
```

Click may present a compact contract like this before touching code:

```json
{
  "outcome": "An eligible order can be cancelled through the existing API and receives at most one refund.",
  "boundary": {
    "in_scope": ["the current cancellation and refund path"],
    "out_of_scope": ["new payment providers", "unrelated order-state cleanup"]
  },
  "must_hold": [
    "Concurrent or repeated requests cannot create a second refund.",
    "Existing request fields, response fields, and status meanings remain compatible.",
    "A payment-provider failure must not leave the order marked as refunded."
  ],
  "build": {
    "approach": [
      "Reuse the current cancellation path, add an idempotent refund record, and make the refund state transition atomic."
    ],
    "semantics": [
      "The refund result is recorded once and repeated requests return the recorded result."
    ]
  },
  "verification": {
    "scale": "full",
    "evidence": [
      {
        "id": "E1",
        "kind": "argv",
        "description": "cancellation tests for success, duplicate, concurrent, and provider-failure cases"
      },
      {
        "id": "E2",
        "kind": "argv",
        "description": "the existing API regression suite"
      }
    ],
    "done_when": [
      {
        "condition": "Refund behavior is correct.",
        "primary_evidence": "E1"
      },
      {
        "condition": "The public API remains compatible.",
        "primary_evidence": "E2"
      }
    ]
  },
  "plain_language": "Customers can cancel an eligible order, but retries or simultaneous requests cannot refund it twice. The public API stays the same, and a failed payment call cannot falsely complete the refund. Because this touches payments and concurrency, Click recommends full verification."
}
```

Staging returns `CLICK_CONTRACT_ID=ctr_0123456789abcdef0123456789abcdef`. Click shows that id and asks one question: approve this contract and its verification scale, revise it, or cancel? Approval authorizes the developer meaning in the contract—not merely the easy summary—and the later turn passes only this id to start implementation.

The exact design is repository-dependent. The example shows the contract shape, not a universal refund architecture.

## The compact contract

| Field | What it fixes |
| --- | --- |
| `outcome` | The concrete result and user-visible behavior |
| `boundary` | What may change and what stays outside the work |
| `must_hold` | Observable safety, compatibility, and correctness promises |
| `build` | The smallest repository-aware implementation route |
| `verification` | One risk-based scale and the evidence that means done |
| `plain_language` | The same contract explained for a non-specialist |

`build.semantics`, `build.order`, and `verification.intermediate_gate` appear only when state meaning, safe ordering, or an irreversible boundary makes them necessary. Click does not mirror the same work into separate phases, steps, tasks, and plans.

The contract locks the result and its boundaries. It does not lock every low-level implementation choice. This is how Click stays small without forcing reapproval whenever the implementation needs an in-scope dependency, file, or tool.

## Always ON without getting in the way

| Request | Always ON behavior |
| --- | --- |
| Create, change, delete, refactor, or repair software | Show one compact contract and plain explanation, then wait for one approval |
| Code review without fixes | No build contract or approval; use the read-only anti-loop guard |
| Question or explanation | Answer normally |
| Simple read-only lookup | Inspect normally without creating an observation ledger |
| First line is plain or autocomplete `@Click bypass` | Authorize one bypass for that turn; keep any active contract |
| First line is plain or autocomplete `@Click cancel` | Authorize one cancel that clears the active contract |

During code review, Click permits one useful repository-wide inventory when needed. After a successful inventory it requires narrower inspection, blocks an identical successful read or search, rejects plan-tool churn, and prevents project mutation while the review guard is active. A later request to fix findings starts a separate compact build contract.

Simple recognized direct reads remain convenient. For ambiguous or tracked work, Click uses `click-gate inspect` with a program-and-arguments array instead of guessing from a shell string. The review guard covers supported local Hook paths; it does not deduplicate hidden reasoning, hosted search, unmatched connectors, or custom wrappers.

## Implementation without loops

Across staging, review, implementation, and verification, the Hook enforces these observable rules:

| Guard | What happens |
| --- | --- |
| Reuse evidence | An identical structured read or search that already succeeded is blocked until an in-scope mutation makes the evidence stale. |
| No parallel planning | Matched `update_plan` calls are rejected while the workflow is armed, staged, approved but incomplete, or in review—even from a later turn. A user-authorized bypass releases planning only for that turn; current-revision completion releases ordinary later planning. |
| No full inventory reset | Root-level inventory such as `rg --files`, `find .`, recursive root listings, and equivalent Git inventory scans are rejected; path-scoped inspection remains available. |
| Make command intent explicit | Ambiguous active Bash is rejected with guidance to use structured `inspect` for reading, `mutate` for implementation, or `verify` for final checks. |
| Keep checks in budget | Final checks must run through the structured `click-gate verify` batch and fit the approved scale. |
| Bound Browser evidence | Browser MCP calls require an explicitly assigned Browser primary source, then receive one three-call, 90-second representative-session budget; long timed progression and post-completion replay are rejected. |
| Own local servers | Recognized development servers use `click-gate service`; Click supervises and stops the exact isolated child instead of leaving a foreground mutation open. |
| Separate proposal from approval | Stage emits an opaque id bound to the digest. Same-turn pass and replacement staging are rejected; a later approval passes only that exact id. |

A failed observation or one whose output exceeds 48,000 bytes gets one unchanged retry. A source mutation resets successful observation evidence because the code may have changed. Hook state changes use a cross-platform lock so parallel result recording does not strand a false “running” observation. The Hook stores request digests and non-content metadata, not command bodies or output.

These are tool-level guardrails, not a reasoning-token cap or operating-system sandbox. The Hook cannot inspect hidden reasoning, detect a plan written only in prose, observe unmatched connectors or hosted tools, prove semantic boundary compliance, or stop allowed custom code from hiding several operations.

### Structured capabilities

Each capability uses protocol version `1` and separates the executable from every argument. Accepted argv arrays run with `shell=False` in a new POSIX session or Windows process group, so pipelines, redirections, command substitutions, and shell wrappers cannot be hidden in the request, and group-directed child signals cannot reach the Codex parent group.

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'
click-gate service '{"version":1,"action":"start","argv":["python3","-m","http.server","4173","--bind","127.0.0.1"]}'
click-gate service '{"version":1,"action":"stop"}'
```

`inspect` accepts only the Hook's bounded read-only operations. Git reads use subcommand-specific positive option policies; `git grep`, `git cat-file`, arbitrary `--format`/`--pretty` output, signature-rendering options, and `git status -v/-vv` are excluded. Accepted Git inspection strips inherited `GIT_*` variables, ignores system/global Git config, forces safe log and diff settings, disables paging and optional locks, and adds `--no-ext-diff` plus `--no-textconv` to supported diff-rendering commands. `mutate` requires the current turn to have passed the emitted id for the approved digest-bound contract and marks prior evidence stale. Recognized long-running server forms are rejected there and instead use `service`, whose supervisor owns the exact child, isolates its process group, stops it explicitly or on `SessionEnd`, and applies a two-hour lifetime ceiling. Ordinary canonical edit tools such as `apply_patch`, `Edit`, and `Write` remain supported mutations without a shell envelope. Malformed requests, shell interpreters, and direct process-control executables such as `kill`, `pkill`, `killall`, `taskkill`, and `Stop-Process` fail closed. An allowed custom program can still conceal explicit process operations, so Click remains a workflow guardrail rather than an operating-system sandbox. See [the capability protocol](skills/click/references/capability-protocol.md) for the exact schemas and enforcement boundary.

SSH Git inspection is **Experimental and POSIX-remote-shell only**. It supports only bounded `git status`, `git rev-parse HEAD`, `git merge-base`, and `git remote get-url` reads, accepts no caller-provided SSH options, requires an already-known host key, disables interactive password flows, host-key updates, forwarding, local commands, and TTY allocation, and fails quickly with connection and keepalive limits. Unknown hosts, non-POSIX remote shells, and unreachable servers fail closed. This is a convenience guardrail, not a general remote executor or security sandbox.

## Automatic verification budget

Click chooses the smallest sufficient scale from the current risk and repository evidence. The user approves it as part of the contract; there is no second budget prompt.

Each source is declared once in `verification.evidence` with an id, a typed `kind`, and a description. Every `done_when` condition references exactly one cheapest sufficient source id through `primary_evidence`; one id may cover several conditions. Click prefers current valid evidence and narrow automated checks, using browser, manual, hosted, broad-suite, or timed end-to-end evidence only when cheaper sources cannot prove the condition. It does not duplicate an automated result through another surface, and it stops when every condition has current evidence. Semantic sufficiency still belongs to the Skill and grader, but the Hook observes the canonical Browser MCP path structurally: Browser calls are denied unless one referenced evidence source has `kind: "browser"`, then capped at three serial calls and 90 measured seconds. A single tool timeout may not exceed 30 seconds, obvious waits above five seconds are rejected, a later mutation resets that evidence, and completion prevents replay. Other unmatched connectors remain outside this meter.

| Scale | Typical use | Automatic ceiling |
| --- | --- | ---: |
| `quick` | Small, local, reversible change | 1 unit |
| `focused` | Ordinary bounded feature or repair | 4 units |
| `full` | Payments, auth, deletion, migrations, public contracts, or cross-boundary concurrency | 10 units |

A `targeted` check costs 1 unit, a `broad` check costs 3, and a `deep` check costs 5. The submitted value is not trusted as the cost: the Hook first recognizes the runner, then estimates its actual scope. One exact file or test node may be targeted; filters such as `-k` or regex selection, multiple files or packages, directories, and whole suites are at least broad. An exact integration or security node is broad, while a whole integration or security suite is deep. The Hook automatically raises an underdeclared check before calculating the total. These values are ceilings, not targets.

Click submits one explicit argv check per entry to:

```text
click-gate verify '{"version":1,"checks":[{"argv":["python3","-m","unittest","discover","-s","tests","-q"],"class":"broad"},{"argv":["git","diff","--check"],"class":"targeted"}]}'
```

The Hook validates and normalizes the submitted classes, executes the accepted final batch without a shell, and records the real exit codes. For Python, explicit pytest, unittest, and coverage module runners qualify, including Windows `py -3 -m ...`; Python `-c` and direct Python scripts are rejected. Common bounded forms such as exact-file `node --check` and `node --test`, `uv run pytest`, `npm run lint`, `npm run build`, `ruff check`, `mypy`, `tsc --noEmit`, `cargo check`, `cargo clippy`, and `go vet` are recognized and charged by their inferred scope. Project-wide `node --test` is broad, and Node eval/print forms are rejected as verification. Legacy shell-string `commands` batches are rejected with migration guidance. A failed batch may be retried once unchanged for a transient failure; after that, an in-scope mutation is required. A later mutation makes an earlier success stale and permits the same batch again.

In a Git worktree, the runner snapshots tracked content and pre-existing **non-ignored** untracked content before the batch. If protected content changes, the batch fails stale and advances the mutation revision instead of recording false success. It also reports every new non-ignored untracked path. Any such path created during final verification is treated as a workspace change, fails stale, and advances the mutation revision. Source or configuration classification is retained only to make the warning clearer. Expected generated artifacts should be Git-ignored or produced during the approved mutation phase. Git-ignored paths are not visible to this snapshot. Outside Git this content-diff guard is unavailable; argv validation, shell-free execution, and revision state still apply.

Minimum class inference closes simple underdeclaration. An unknown verification-like wrapper name is charged conservatively as `deep`, and an unrecognized command is rejected, but an allowed program can still conceal expensive work internally. This is not a security or resource sandbox and does not prove that the chosen tests are semantically sufficient.

## Minimum design still protects the important parts

Minimum design removes ceremony, not necessary safeguards.

| Concern | What the contract preserves when relevant |
| --- | --- |
| Concurrency | Race behavior, duplicate execution, idempotency |
| State | Valid transitions, persistence points, ownership |
| Failure | Partial failure, retry, recovery, external errors |
| Security | Authentication, authorization, secrets, privacy boundaries |
| Compatibility | Existing API, data, statuses, and user-visible behavior |

Material conditions belong in `must_hold`; concrete state or failure meaning belongs in optional `build.semantics`; evidence sources belong in `verification.evidence`, and observable conditions reference them from `verification.done_when`. The Hook protects contract shape, approval order, digest equality, visible loops, and visible verification breadth. It does not prove that the implementation is architecturally correct or semantically faithful by itself.

More precisely, Click does not semantically decide whether a new microservice, queue, or abstraction is overdesign. The Skill and semantic grader prefer the smallest evidence-backed design; the Hook blocks the repeated planning, whole-repository rediscovery, and repeated-verification loops that often produce design expansion. Product claims are limited to that observable enforcement boundary.

## Who Click is for

Click targets two groups:

- users of high-capability models who are tired of repeated planning, repository exploration, and excessive verification;
- people building MVPs, internal tools, automations, and clearly bounded features who want minimum design followed by continuous implementation.

It is especially useful for:

- a brownfield feature that must preserve an existing API;
- idempotency, concurrency, state transitions, or failure recovery;
- a migration or other high-impact change with a clear safe boundary;
- a handoff where another person or agent must implement the same meaning;
- an MVP, internal tool, or automation where you want minimum planning followed by continuous implementation.

Manual mode or a per-turn bypass is usually better for tiny, obvious, reversible, or exploratory changes where no durable approval boundary is useful. For legal, regulated, security-critical, or operationally irreversible work, Click does not replace expert review, authorization, or deployment controls.

## Evidence and honest limits

The v0.20.0 source is release-gated by the deterministic suite. It covers persistent modes, distinct-turn approval, active-contract locking, read and plan anti-loops, scope-aware local verification, structured evidence references, Browser primary-source assignment and budgets, managed server start/stop cleanup, Node file checks, hardened Git inspection, process isolation, verification-time workspace mutation detection, distribution consistency, and repository policy. Required CI runs the suite on Linux, macOS, and Windows; Ubuntu also validates the plugin, marketplace, Click/Fix skills, Python compilation, and whitespace errors.

The repository also includes version-17 golden cases and a semantic grader for deterministic fixture-based policy review. These artifacts check contract shape and expected behavior; they are not runtime productivity measurements.

These gates prove observable Hook and contract behavior only. Click does not claim that it improves success rate, accuracy, time, token use, or overdesign across projects without independent measurements on unrelated real repositories.

Click is not claimed to be the first or only workflow in this area. It overlaps with spec-driven, autonomous-loop, and approval-gated tools; its deliberately narrow emphasis is one persistent choice, one compact contract, one approval, one-shot implementation, observable anti-loop guards, and one final verification budget.

A ready-to-edit launch post for developer communities is available in [COMMUNITY_POSTS.md](COMMUNITY_POSTS.md).

<details>
<summary>Repository structure and local validation</summary>

```text
.codex-plugin/plugin.json             Plugin manifest
.agents/plugins/marketplace.json      GitHub marketplace entry
skills/click/                         One-shot design-and-build Skill
skills/click/references/modes.md      Persistent mode and code-review behavior
skills/click/references/capability-protocol.md  Structured runner schemas
skills/fix/                           Compact repair Skill
hooks/click_gate.py                   Contract, capability, anti-loop, and budget guard
hooks/hooks.json                      Lifecycle Hook configuration
evals/                                Golden cases and semantic grader
tests/                                Deterministic Hook, grader, and policy tests
scripts/validate_distribution.py     Repository-owned release validator
COMMUNITY_POSTS.md                    Ready-to-edit English and Korean launch posts
LICENSE                               MIT License
```

```bash
python3 scripts/validate_distribution.py
python3 -m compileall -q hooks evals scripts tests
python3 -m unittest discover -s tests -v
git diff --check
```

</details>

<details>
<summary>Related approaches</summary>

| Project | Overlap | Click's narrower emphasis |
| --- | --- | --- |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | Specification, planning, tasks, implementation | One compact contract and one approval instead of a persistent multi-command specification process |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | Agreement before AI-assisted coding | No project-local specification store; the Hook keeps only content-free lifecycle metadata and a digest outside the target repository |
| [Kiro Specs](https://kiro.dev/docs/cli/v3/specs/) | Requirements, design, tasks, verified execution | One complete contract review followed by one-shot implementation |
| [Agentic SDLC Codex Plugin](https://github.com/aantenore/agentic-sdlc-codex-plugin) | Hash-bound proposals and approval | A smaller pre-code boundary rather than broader SDLC governance |

This is a bounded comparison, not an exhaustive novelty search.

</details>

## License

Click is released under the [MIT License](LICENSE).
