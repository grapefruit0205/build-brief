# Build Brief

English | [한국어](README.ko.md)

Build Brief is an explicitly invoked Codex plugin that turns a software request and the relevant repository context into a complete, approval-bound developer execution contract. It creates the developer contract first, translates the same meaning into plain language, asks for approval, and then implements only what was approved.

It is not an architecture-pattern picker. Users do not have to choose “modular monolith,” “microservices,” “event-driven,” “batch,” or “functional.” Build Brief derives whatever software-design language the actual behavior and codebase require, then maps that meaning into executable work.

## Why use it if an LLM can already design software?

Strong coding models already infer design from natural language. Build Brief does not add intelligence to the model. It makes the model's implicit reasoning visible, reviewable, reusable, and approval-bound when requirements, invariants, compatibility, failure behavior, or handoffs matter.

Natural language remains the default. Use Build Brief only when you want to inspect and approve the complete design-and-execution meaning before code changes.

## How it works

```text
natural-language request
  → explicitly select Build Brief or invoke $build-brief
  → arm only this work; unselected work remains fail-open
  → inspect the narrowest relevant repository context
  → create the complete developer execution contract
  → derive a faithful plain-language explanation
  → stage the exact contract digest outside the repository
  → show both views and ask for approval without editing
  → after approval, pass only the identical staged contract
  → implement and verify only the approved contract
  → revise and reapprove before any material scope change
```

Once Build Brief is explicitly selected, wording does not change the workflow. “Design it,” “build it,” “implement it,” “do it,” `설계해줘`, `구현해줘`, and equivalent expressions in other languages all produce the same complete contract. A question about Build Brief is not an invocation, and Build Brief never activates merely because a task is large or architectural.

## One contract, two views

The authoritative developer execution contract contains:

| Field | Purpose |
| --- | --- |
| `boundary` | Existing component, data owner, or external contract that owns the behavior |
| `invariants` | Observable requirements that must remain true |
| `system_semantics` | Material state, ownership, flow, timing, concurrency, consistency, failure, security, compatibility, migration, and operational meaning |
| `plan` | Approved goal, scope, non-goals, and top-down approach |
| `implementation` | Concrete design mapped onto current code and system boundaries |
| `phases` | Proportional implementation checkpoints |
| `steps` | Ordered changes inside the phases |
| `tasks` | Concrete approved code, test, configuration, schema, or documentation units |
| `execution_order` | Dependency and safe-sequencing constraints |
| `minimality` | Existing structure to reuse and evidence for every material addition |
| `proof` | Acceptance criteria and focused verification |

`plain_language` is a faithful easy explanation of that complete contract. It cannot add a decision absent from the developer contract or hide an invariant, compatibility promise, failure behavior, implementation element, task, or execution constraint.

The six execution fields are required but must remain distinct and proportional. A small change may use one concise item per field. Field presence is not permission to inflate a one-file edit into a project.

## Approval is a real boundary

- The original request is not approval of a contract that has not been shown yet.
- Build Brief shows the developer contract first, then its easy translation, and asks whether to approve, revise, simplify, or cancel.
- The Hook records a digest of the staged contract, not its plaintext, outside the target repository.
- After approval, the Hook accepts only the identical staged contract.
- Implementation must stay inside the approved behavior, scope, architecture, dependencies, schemas, public contracts, failure semantics, tasks, and execution constraints.
- A material change requires a revised contract, a regenerated easy explanation, and new approval before more mutation.
- Low-level reversible choices already contained by the approved boundary and tasks do not require another approval.

The Hook enforces structure, ordering, and staged-versus-passed equality. It cannot prove that a design is correct, that a human genuinely approved it, or that every code change semantically matches the contract. The Skill, repository evidence, focused verification, semantic grader, and user review cover those boundaries.

## Minimum-sufficient design

Required behavior and invariants are the correctness gate. Among candidates that satisfy them, Build Brief chooses the smallest justified design delta and maximizes reuse of the current system.

A new deployable unit, store, queue or asynchronous boundary, public contract, framework or dependency, abstraction layer, configuration surface, or operational component needs all four:

1. a current requirement or repository fact;
2. evidence that the existing structure is insufficient;
3. the concrete failure the addition prevents;
4. focused proof.

Hypothetical scale, future reuse, imagined teams, and fashionable vocabulary are not evidence. Necessary concurrency, safety, compatibility, and failure handling are not overdesign merely because they add code.

## Example

Input:

```text
$build-brief Design and implement order cancellation. Prevent duplicate refunds and preserve the existing API.
```

Build Brief first traces the existing cancellation, refund persistence, payment adapter, and API contract. It then produces a top-down contract whose invariants preserve API behavior and prevent a second refund under retries or concurrent cancellation; whose implementation, phases, steps, tasks, plan, and execution order map that meaning onto the current system; and whose proof covers compatibility, retries, concurrency, and failure behavior.

It then explains the same result plainly, for example: “Cancellation will continue through the current API. Retrying or sending the same cancellation at the same time must not refund twice. We will reuse the existing order and payment paths, change only the approved cancellation and verification units, and test compatibility and duplicate-refund cases.”

It asks:

> Do you approve this execution contract? If approved, I will implement only this contract.

No project file changes before that approval.

## Installation from GitHub

You need a Codex version with plugin marketplaces and Python 3.10 or newer, available as `python3` or `py -3` on Windows.

```bash
codex plugin marketplace add grapefruit0205/build-brief
codex plugin add build-brief@build-brief
```

Restart the ChatGPT desktop app after installation. Review and trust the included Build Brief Hook when prompted; in Codex CLI, inspect it with `/hooks`. Start a new task after installation or Hook changes so Codex loads the current release.

## Usage

For ordinary work, keep using natural language without Build Brief. To use the approval workflow, select the plugin or invoke the Skill explicitly:

```text
$build-brief Add partial refunds to this legacy checkout without changing existing full refunds.
```

Build Brief inspects the relevant code, stages and shows the complete contract and easy explanation, then stops. Continue only after reviewing it:

```text
I approve this execution contract. Implement exactly what was approved.
```

If you want a contract for handoff but no coding, say so explicitly. Build Brief still creates all fields but does not mutate the project:

```text
$build-brief Create the complete execution contract and easy explanation for another developer. Do not implement it.
```

To opt out after invocation:

```text
Continue this work without Build Brief.
```

Optional strict mode applies the Gate session-wide only when the user explicitly requests it. Build Brief never enables strict mode on its own.

## Repository structure

```text
.codex-plugin/plugin.json             Plugin manifest
.agents/plugins/marketplace.json      GitHub marketplace entry
LICENSE                               MIT License
skills/build-brief/SKILL.md           Skill entry point
skills/build-brief/references/        Contract and translation guidance
hooks/hooks.json                      Codex lifecycle Hook configuration
hooks/build_brief_gate.py             Local mutation and contract-equality guard
evals/golden-prompts.yaml             Activation and semantic cases
evals/semantic_grader.py              Deterministic scorer after semantic judgment
evals/semantic-judgment.schema.json   Structured model/human judgment contract
evals/SEMANTIC_GRADER.md              Evidence-based judge guidance
tests/                                Deterministic Hook, grader, and policy tests
```

This release contains no MCP server, app connection, external API call, credential requirement, or third-party runtime dependency. Hook state lives under Codex-provided `PLUGIN_DATA`; no contract plaintext or runtime state is written into the target repository.

## Validation and evaluation

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py skills/build-brief
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
python3 -m unittest discover -s tests -v
```

`evals/golden-prompts.yaml` defines expected behavior; it is not a benchmark result. The bounded A/B runner compares no-plugin, explicitly invoked Skill-only, and explicitly invoked Skill-plus-Hook conditions on pinned disposable repositories. The semantic grader hard-fails missing behavior, unwanted blocking, premature implementation, explanation mismatch, missing execution fields, and changes outside the approved contract, then penalizes unjustified design delta.

The recorded v0.5.0 opt-out pilot remains historical evidence for the unwanted-blocking defect fixed in later releases. It contains one run per condition and is not a general performance claim.

## Current limits

Explicit selection costs more time and tokens than ordinary natural-language coding because the complete contract and explanation are displayed before implementation. Build Brief therefore stays opt-in and fail-open when unused. The Hook starts a small standard-library Python process for covered local tool calls, which adds modest per-tool latency.

The Hook covers supported lifecycle mutation paths; it is an ordering guardrail, not a security sandbox. Real legal policy, production traffic, organizational practice, and other facts absent from the repository still require user input. Behavioral A/B evaluation and semantic grading improve confidence but cannot prove that an architecture is absolutely correct.

## License

Build Brief is released under the [MIT License](LICENSE).
