# Build Brief

English | [한국어](README.ko.md)

Build Brief is a small Codex plugin that compiles ordinary software requests into the smallest sufficient context-aware engineering directive, then gates supported local edits until its Design Contract is recorded.

It is **not** an architecture-pattern picker. It does not ask users to choose between a modular monolith, microservices, event-driven design, batch processing, functional programming, or other labels. It reads the request and the actual codebase, generates only the design semantics that matter in that situation, and translates each one into a concrete implementation or verification consequence.

## Why use it if an LLM can already design software?

A capable coding model can already infer architecture from natural language. Build Brief does not add new intelligence. It makes that inference more repeatable, explicit, and suitable for handoff—especially when requirements are vague, several agents or developers are involved, or important invariants are easy to miss.

Use ordinary natural language as the default. Use Build Brief when you want a visible engineering directive, more consistent treatment of implicit constraints, or a reusable implementation handoff.

## What it does

```text
plain-language intent
  → automatically activate only for non-trivial work
  → inspect the narrowest relevant repository context
  → complete the smallest sufficient Design Contract
  → record the mutation gate outside the repository
  → implement, review, compare, or hand off as requested
```

Examples of semantics it may derive include state transitions, domain invariants, contracts, concurrency, consistency, failure behavior, data lifecycle, compatibility, security, observability, rollout, and proof of completion. This is an open vocabulary, not a checklist.

## Hybrid invocation, architecture-first execution

Build Brief uses a hybrid invocation model:

- **Automatic discovery:** Non-trivial requests with implicit engineering consequences can activate the skill without requiring the user to know its name.
- **Explicit invocation:** `$build-brief` guarantees activation when the user wants a design review or reusable directive.
- **Negative routing:** Terminology questions do not activate it. Trivial, fully specified edits skip the full design path but still use a one-item compact contract before mutation.
- **Mutation guard:** Before supported local write tools run, the plugin requires at least a compact contract containing the owning boundary, invariants, implementation slice, minimality justification, and proof.

For consequential work, Build Brief completes an implementation-ready Design Contract before modifying code, tests, configuration, or schemas. The contract proceeds top-down from the current system boundary and observable behavior to invariants, ownership, state, contracts, execution flow, material failure semantics, implementation slices, minimality accounting, and proof. A lightweight lifecycle hook applies the same ordering to supported local mutation tools even when automatic Skill discovery misses; trivial edits pass with a one-item compact contract.

This gate is proportional. It fixes the consequential design for the requested change; it does not attempt to freeze the architecture of the whole system. Read-only inspection stays available before the gate, and the Skill starts from the behavior's entry point instead of scanning the whole repository.

## Minimum-sufficient design

Required behavior and material invariants are a hard correctness gate. Among candidates that pass it, Build Brief selects the smallest justified design delta and maximizes reuse of the current system.

A new service, store, queue or asynchronous boundary, public contract, framework or dependency, abstraction, configuration surface, or operational component must identify a current need, why the existing structure is insufficient, the failure it prevents, and focused proof. Hypothetical scale, future reuse, imagined teams, and architecture vocabulary are not evidence. Necessary concurrency, safety, compatibility, and failure handling cannot be removed merely to make the design look smaller.

This behavior is built into Build Brief's Skill and Hook contract. Recipients do not need a separate policy or memory plugin.

To bound repeated context cost, the Hook injects one short policy at session start instead of analyzing or rewriting every prompt. Its local runtime performs no architecture analysis and makes no network call; it only distinguishes covered read-only calls, gate commands, and mutations. If automatic Skill discovery misses, the first covered mutation is denied with a recovery instruction, after which the agent can pass the contract and retry. Supporting reference files are loaded only when a broad or non-obvious change needs them.

## Example

Input:

> When inventory drops below five, notify the buyer once. Several inventory updates may arrive close together.

The plugin should translate this into consequences such as detecting a threshold crossing instead of every low-stock write, making duplicate suppression safe under concurrent updates, defining notification failure behavior, and testing the boundary and race cases. It should reuse the existing inventory and notification paths, adding no broker or service unless current evidence shows those paths cannot preserve the invariants. It should not merely answer “use event-driven architecture and idempotency.”

## Install from GitHub

Requires a Codex version with plugin marketplace support and Python 3.10 or newer available as `python3` (`py -3` on Windows).

```bash
codex plugin marketplace add grapefruit0205/build-brief
codex plugin add build-brief@build-brief
```

Restart the ChatGPT desktop app after installing, review and trust the bundled Build Brief hook when prompted (or with `/hooks` in Codex CLI), then begin a new conversation. Changed hook definitions require a new trust review.

## Use

Use natural language for normal work, or invoke it explicitly to guarantee a mode.

Automatic build after the internal design gate:

```text
$build-brief Add partial refunds to this legacy checkout flow without changing existing full refunds.
```

Review before coding:

```text
$build-brief Show me the design contract first and wait for approval before coding.
```

Directive only:

```text
$build-brief Create a handoff-ready engineering directive. Do not implement it.
```

## Design principles

- Preserve the user's product meaning, scope, and authorization.
- Inspect an existing repository before translating it.
- Generate design language from the situation instead of selecting from a fixed catalog.
- Attach every design term to a concrete implementation or verification consequence.
- Treat correctness as a hard gate, then choose the smallest justified design delta among passing candidates.
- Reuse existing structure and require present evidence for every material new design element.
- Do not modify implementation files until the proportional Design Contract passes its gate.
- Start from the narrowest relevant evidence and widen only for unresolved consequential behavior.
- Execute the directive when implementation was requested; do not stop at a design document.
- Keep small changes small and avoid vocabulary theater.

## Repository layout

```text
.codex-plugin/plugin.json             Plugin manifest
.agents/plugins/marketplace.json      GitHub marketplace entry
LICENSE                               MIT license
skills/build-brief/SKILL.md           Skill entry point
skills/build-brief/references/        Conditional translation guidance
hooks/hooks.json                      Codex lifecycle hook configuration
hooks/build_brief_gate.py             Local per-turn mutation guard
evals/golden-prompts.yaml             Activation and semantic test cases
tests/test_build_brief_gate.py        Deterministic hook behavior tests
```

This release contains no MCP server, app connection, external API call, or credential requirement. Hook state is stored under Codex-provided `PLUGIN_DATA`, not in the working repository. The gate stores a digest rather than the Design Contract text and prunes stale state.

## Validation

The repository includes positive, negative, boundary, and Korean-language cases in `evals/golden-prompts.yaml`. Each case also names structure to reuse and material additions to reject without evidence. These cases describe expected activation and semantic invariants; they are not presented as benchmark results.

Structural validation:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py skills/build-brief
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
python3 -m unittest discover -s tests -v
```

For behavioral evaluation, compare the same representative prompts with no plugin, with the Skill only, and with Skill plus Hook. Treat task correctness as a hard gate, then measure unjustified design elements and total design delta before activation, mutation ordering, clarification turns, time, tokens, Hook costs, and proof of completion.

## Current scope

Automatic Skill discovery remains model-mediated, so it can still over-activate or fail to activate. The deterministic Mutation Gate catches a missed activation at the first covered write attempt, but it does not make Skill selection deterministic.

The Gate blocks supported local tool paths such as `apply_patch` and guarded Bash commands until a structurally valid contract is recorded. It is an ordering guardrail, not a complete security boundary: users must trust and enable the Hook, and specialized tool paths may not pass through Codex lifecycle hooks. The Hook requires a `minimality` field but validates only its shape; whether the proposed design is truly minimum-sufficient still belongs to the Skill, repository evidence, and behavioral evaluation. It also launches a small standard-library Python process for each covered local tool call, so command-heavy work retains a modest per-tool latency cost even though repeated prompt context is avoided.

## License

Build Brief is released under the [MIT License](LICENSE).
