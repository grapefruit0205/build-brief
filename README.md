# Click

[![HOL Guard](https://img.shields.io/endpoint?url=https%3A%2F%2Fhol.org%2Fapi%2Fregistry%2Fbadges%2Fplugin%3Fslug%3Djunseok-pak%252Fclick%26metric%3Dtrust)](https://hol.org/go/guard/pjseok1219?dest=%2Fguard%2Fbilling%3Fpromo%3DGUARD20-PJSEOK1219%23upgrade&link_id=351107f3-00d1-4b0f-8aac-1bb449193d84&utm_source=insights_share&utm_medium=affiliate_cta&utm_campaign=share20)
[![CI](https://github.com/grapefruit0205/click/actions/workflows/ci.yml/badge.svg)](https://github.com/grapefruit0205/click/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English | [한국어](README.ko.md) | [简体中文](README.zh-CN.md)

> ## Make coding agents prove what they changed.
>
> **Evidence by default. Approval-bound execution when the risk calls for it.**

Click is a Codex plugin that moves **execution authority and verification evidence out of the model's memory and into persistent Hooks**.

For normal work, Codex keeps working normally while Click records **prompt lineage, mutation revisions, and reusable verification evidence** that still matches the current code.

For higher-risk work, Click can require one human-readable contract to be approved **before observable mutations are allowed**.

```text
Evidence (default)
request → implementation → current-revision evidence → honest receipt

Guarded
request → Goal / Changes / Unchanged / Completion checks
        → Later user turn approval
        → bounded execution
        → current-revision evidence
        → receipt
```

**The model still decides how to solve the problem. Click keeps track of what was authorized and whether the proof still matches the code.**

**One default with no Click approval friction. One opt-in guard for work that needs it.**

---

## Why Click?

Coding agents are good at solving local problems. Long-running sessions have a different problem: **state drifts**.

A test can pass, the code can change afterward, and the agent can still remember the old result as if it were current. A task can start with a narrow request and gradually widen. The same repository scan or verification can be repeated because the model no longer has a reliable record of what is still valid.

Prompts can say:

```text
Stay in scope.
Do not modify files before approval.
Do not rerun checks that are already valid.
Do not claim completion from stale test results.
```

But prompts are instructions the model must remember.

**Click puts the important parts on the execution path instead.**

| Problem | Without Click | With Click |
| --- | --- | --- |
| A test passed before the latest edit | The model may remember the old result | Evidence is bound to a mutation revision and becomes stale when required |
| A risky change needs approval | Approval is mostly conversational | Guarded binds a later user approval to an exact `contract_id` and digest |
| An unrelated edit happens after a test | The suite may be rerun unnecessarily | Dependency-safe evidence can be reused when all proof inputs still match |
| The agent repeats repository exploration | Context is rediscovered | Repeated/broad exploration stays allowed, with non-blocking reuse and narrowing guidance |
| The agent says “done” | Completion depends on the agent's summary | Click can export a receipt from current observable evidence |

### The 30-second mental model

```text
Prompt / AGENTS.md
    tells the model what it should do

Click
    stores what observable execution is allowed to do
    and which evidence is still valid
```

Click does **not** make the model smarter. It makes authority and evidence harder to accidentally forget.

---

## Three modes

| Mode | What it feels like | Execution authority |
| --- | --- | --- |
| **Evidence** — default | Work normally. No Click approval prompt. Get revision-aware evidence and a receipt. | Host |
| **Guarded** | Approve one four-section contract, then let the agent work inside it. | Approved Click contract |
| **Off** | Click does not govern ordinary work. Explicit `@Click` can still start Guarded. | Host |

### Evidence — use this most of the time

Evidence mode is intentionally low-friction.

Codex uses its normal host permissions. Click records intent lineage, observed mutations, verification receipts, cache lineage, and completion evidence without pretending that Click approved the work.

Evidence receipts explicitly report:

```text
approval_bound: false
execution_authority: host
```

### Guarded — use it when the boundary matters

Guarded is useful for changes such as:

- authentication and authorization
- payments and refunds
- deletion or destructive operations
- database migrations
- public API or compatibility changes
- security-sensitive configuration
- changes where “do not touch X” really matters

The user sees four sections:

```text
Goal
What result should exist?

Changes
What is allowed to change?

Unchanged
What must stay untouched or compatible?

Completion checks
What evidence means the work is actually done?
```

Click stages that contract once, emits an opaque `contract_id`, and requires approval from a **Later user turn**. The same turn cannot both stage and approve it.

---

## Quick start

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

Restart the host so the Click Hooks are loaded, review/trust the included Hook, and start a new task.

Evidence is the default for new and unset installations.

```text
click-gate default evidence
click-gate default guarded
click-gate default off
```

Then work normally:

```text
Refactor the authentication parser and keep the public behavior unchanged.
```

Or explicitly start a Guarded task:

```text
@Click Add order cancellation.
Prevent duplicate refunds and preserve the existing API.
```

Explicit controls remain available:

```text
@Click bypass
@Click cancel
```

Neither silently unlocks an active incomplete Guarded contract.

### Upgrade an existing installation — v0.36.1

The current release is **v0.36.1**.

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

Start a fresh task after upgrading so the current Hook code and mode behavior are loaded.

v0.36.1 also handles hosts that omit a nested execution workdir during receipt
export. Click recovers it only when every current argv evidence source binds the
same canonical Git root; stale, malformed, missing, or conflicting roots remain
fail-closed.

---

## What revision-aware evidence means

Click does not treat “a test passed sometime earlier” as permanent truth.

```text
revision 12  auth code changed   → run auth tests → pass
revision 13  README only changed → proof inputs unchanged → reuse pass
revision 14  auth code changed   → proof inputs changed → rerun tests
```

A successful check can be reused only when the bindings required for that evidence still match, including the relevant combination of:

- exact check request
- protected workspace state
- mutation revision
- execution environment
- executable identity
- known host Hook coverage
- dependency mapping and resolved dependency content

If a required binding is missing, ambiguous, changed, or unsafe, Click falls back to real verification instead of trusting the model's explanation.

### Cross-revision reuse is deliberately conservative

In **Guarded**, an argv evidence source may use dependencies declared before approval or a committed repository mapping.

In **Evidence**, runtime guesses do not create reuse authority. Cross-revision reuse requires a committed:

```text
.click/evidence-dependencies.json
```

If the dependency mapping, resolved files, environment, executable, host coverage, mutation receipts, or workspace state no longer match, the check runs again.

---

## What Click actually enforces

Click is a **workflow guardrail** that separates **hard runtime guarantees** from **workflow advice**.

Hard enforcement applies only on the **observable tool path**. The model's planning and search strategy remain non-authoritative.

### Hard runtime boundaries

Click can enforce observable invariants such as:

- selected authority mode is reported honestly
- Guarded approval is bound to the exact staged contract and a later user turn
- supported Guarded mutations wait for approval
- one-use runner claims cannot be replayed or substituted
- cancellation, state binding, and runner tokens are checked against persistent state
- mutation advances the revision and invalidates stale evidence
- argv verification is bound to the exact request and observed result
- environment, executable, workspace, and known host coverage can participate in evidence identity
- managed service execution tracks and cleans up the owned child process
- completion receipts cannot invent a successful result that the Hook did not observe

### Advisory, not authority

Click intentionally does **not** hard-code model workflow strategy.

These remain non-blocking guidance:

- whether the model should replan
- how many times it should inspect the repository
- whether another broad search is useful
- which implementation strategy is best
- whether the model's chosen verification scope is semantically sufficient

`update_plan` may still be used. A **distinct-digest broad inventory remains available** with narrowing guidance, and a **fresh identical structured read/search** may run through a new one-use authorization rather than being confused with replay of an old runner.

They cannot approve, replace, or widen a Guarded contract.

> **Click constrains observable execution, not hidden reasoning.**

### Advisory verification profiles

Guarded can recommend a qualitative verification profile before approval. Evidence mode does not use these profiles as execution authority.

| Profile | Typical use |
| --- | --- |
| `quick` | Small, local, reversible change |
| `focused` | Ordinary bounded feature or repair |
| `full` | Payments, auth, deletion, migrations, public contracts, or cross-boundary concurrency |

The model still chooses concrete checks. Click binds the exact `evidence_id`, check request, revision, environment, executable, known host coverage, and observed result rather than turning a profile label into proof.

---

## Guarded example

A high-risk request might produce a human view like this:

```text
Goal
Eligible orders can be cancelled through the existing API and receive at most one refund.

Changes
- Current cancellation and refund path
- Idempotent / atomic refund transition

Unchanged
- Existing request and response fields
- Existing status meanings
- No new payment provider

Completion checks
- Cancellation and duplicate-refund tests pass
- Existing API regression tests pass
```

Internally, Click keeps a canonical structured contract for schema validation and digest binding. The human view is the approval surface; raw JSON is technical detail.

The contract fixes **meaning, boundary, invariants, and completion commitment**. It does not freeze every implementation detail or file choice.

A digest-bound follow-up can be recorded and an incomplete approved contract can resume with the same ID. Material changes to the approved outcome, boundary, invariants, authority, or verification commitment require a new contract. Click records the follow-up digest; it does not claim to semantically prove that natural-language follow-up was in scope.

<details>
<summary><strong>Example canonical Guarded contract</strong></summary>

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
    "approach": [
      "Reuse the current cancellation path and make the refund transition idempotent and atomic."
    ]
  },
  "verification": {
    "scale": "full",
    "evidence": [
      {
        "id": "E1",
        "kind": "argv",
        "description": "cancellation and duplicate-refund tests",
        "dependencies": ["src/orders/", "tests/test_cancellation.py"]
      },
      {
        "id": "E2",
        "kind": "argv",
        "description": "existing API regression tests"
      }
    ],
    "done_when": [
      {"condition": "Refund behavior is correct.", "primary_evidence": "E1"},
      {"condition": "The public API remains compatible.", "primary_evidence": "E2"}
    ]
  },
  "plain_language": "Customers can cancel an eligible order, but retries or simultaneous requests cannot refund it twice. Existing API compatibility is preserved."
}
```

</details>

---

## Completion receipts

When every required source is current and no managed service remains active, Click can export a canonical completion receipt:

```text
click-gate receipt export
```

A receipt binds the observable execution lineage relevant to the selected mode.

**Evidence** records host authority, intent/follow-up lineage, mutation revision, evidence results, environment/executable bindings, host coverage, and dependency/cache lineage.

**Guarded** additionally binds the contract ID and digest plus staging and approval turns.

Receipts intentionally exclude raw runner tokens, raw contract prose, prompts, and workspace paths.

You can verify an exported receipt offline:

```text
click-gate receipt verify ./completion-receipt.json
```

Current receipts are labelled:

```text
unsigned-integrity-only
```

That means canonical-body/digest mismatch can be detected, but publisher identity and non-repudiation are **not** yet provided. An attacker able to rewrite both the body and digest is outside the current receipt guarantee.

---

## Why not just use a system prompt or `AGENTS.md`?

Use them. Click solves a different problem.

| Prompt / `AGENTS.md` | Click |
| --- | --- |
| Describes desired behavior | Maintains persistent observable runtime state |
| The model must remember it | State survives context drift |
| Can ask for approval | Guarded binds approval to an exact contract ID/digest |
| Can say “rerun only when needed” | Evidence can track whether previous proof still matches its inputs |
| Can ask the model not to overclaim | Receipt semantics distinguish host authority from Click approval |

A good prompt helps the model reason well.

Click is for the things you do not want to depend on reasoning memory alone.

---

## Structured capabilities

Click uses structured capability paths and direct argv execution for supported runners instead of treating an arbitrary shell string as authority.

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"]]}'

click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'

click-gate service '{"version":1,"action":"start","argv":["python3","-m","http.server","4173","--bind","127.0.0.1"]}'

click-gate evidence '{"version":1,"evidence_id":"E-browser"}'

click-gate verify '{"version":2,"checks":[{"evidence_id":"E1","argv":["python3","-m","pytest","tests/test_cancellation.py"],"class":"targeted"}]}'
```

Supported structured argv requests reject shell interpreters and process-control executables on the direct capability path. Exact schemas, executable policy, environment handling, process boundaries, and runner transport are documented in the [capability protocol](skills/click/references/capability-protocol.md).

Click is a **workflow guardrail**, not an operating-system sandbox.

---

## Google Antigravity adapter — experimental

The repository can also build a self-contained Google Antigravity plugin using the same core contract state, evidence ledger, verification receipts, and shell-free runner concepts.

```bash
python3 scripts/build_antigravity_distribution.py
agy plugin install ./dist/antigravity
```

You may also copy `dist/antigravity` into:

```text
.agents/plugins/click
```

for one workspace, or:

```text
~/.gemini/config/plugins/click
```

for a global installation.

Antigravity's Hook surface is not identical to Codex. Native file/search and unrelated MCP or Skill tools remain available, and some cross-tool deduplication / Browser evidence behavior is not currently supported. See [`platforms/antigravity/README.md`](platforms/antigravity/README.md) for the exact adapter limits.

---

## Honest limits

Click is a **workflow guardrail**, not an OS sandbox and not a semantic correctness oracle.

It does **not** claim to:

- inspect hidden chain-of-thought or private model reasoning
- observe tool paths for which the host emits no matching Hook event
- observe every unmatched connector, MCP tool, or hosted action
- independently prove that a natural-language follow-up is semantically inside an earlier scope
- prove architecture quality or business correctness by itself
- prove that unmatched manual/external attestations really happened
- stop an allowed custom program from hiding multiple internal side effects
- replace expert review, deployment controls, authorization systems, CI provenance, or an operating-system sandbox

Host coverage is explicitly **`known-surfaces-only`**.

The deterministic suite tests observable Hook/runtime behavior across Linux, macOS, and Windows. Click does not claim universal improvements in success rate, accuracy, tool calls, token usage, or completion time without independent measurements on unrelated real repositories.

That limitation is intentional: **Click should make only the claims its runtime can actually observe and enforce.**

---

## Design boundary

Click's stable product boundary is defined in the [Product Constitution](PRODUCT_CONSTITUTION.md):

> A hard Core feature belongs only when an external guarantee is still useful even with a perfect model, the runtime can observe the relevant action/result, and failure threatens authority, side-effect control, or evidence integrity.

This keeps model-specific workflow preferences out of runtime authority.

Useful technical references:

- [Product Constitution](PRODUCT_CONSTITUTION.md) — what belongs in Click Core
- [Guard Classification](GUARD_CLASSIFICATION.md) — hard guarantees vs user policy vs heuristics
- [Capability Protocol](skills/click/references/capability-protocol.md) — structured execution rules
- [Verification Profiles](skills/click/references/verification-profiles.md) — advisory verification guidance
- [Anti-loop Policy](skills/click/references/anti-loop-policy.md) — repeat/replan guidance and boundaries
- [Release Notes](RELEASE_NOTES.md) — version history
- [Antigravity Adapter](platforms/antigravity/README.md) — experimental host differences

---

## The idea in one sentence

> **Do not ask the coding agent to remember which authority and evidence are still valid. Put that state on the execution boundary.**

Community: [LINUX DO](https://linux.do/)

## License

Click is released under the [MIT License](LICENSE).
