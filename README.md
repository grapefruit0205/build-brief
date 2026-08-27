# Build Brief

English | [한국어](README.ko.md)

Build Brief is a small, skills-only Codex plugin that compiles ordinary software requests into context-aware engineering directives and then carries them out.

It is **not** an architecture-pattern picker. It does not ask users to choose between a modular monolith, microservices, event-driven design, batch processing, functional programming, or other labels. It reads the request and the actual codebase, generates only the design semantics that matter in that situation, and translates each one into a concrete implementation or verification consequence.

## Why use it if an LLM can already design software?

A capable coding model can already infer architecture from natural language. Build Brief does not add new intelligence. It makes that inference more repeatable, explicit, and suitable for handoff—especially when requirements are vague, several agents or developers are involved, or important invariants are easy to miss.

Use ordinary natural language as the default. Use Build Brief when you want a visible engineering directive, more consistent treatment of implicit constraints, or a reusable implementation handoff.

## What it does

```text
plain-language intent
  → automatically activate only for non-trivial work
  → inspect the real repository and operating context
  → complete an implementation-ready Design Contract
  → pass the design gate
  → implement, review, compare, or hand off as requested
```

Examples of semantics it may derive include state transitions, domain invariants, contracts, concurrency, consistency, failure behavior, data lifecycle, compatibility, security, observability, rollout, and proof of completion. This is an open vocabulary, not a checklist.

## Hybrid invocation, architecture-first execution

Build Brief uses a hybrid invocation model:

- **Automatic discovery:** Non-trivial requests with implicit engineering consequences can activate the skill without requiring the user to know its name.
- **Explicit invocation:** `$build-brief` guarantees activation when the user wants a design review or reusable directive.
- **Negative routing:** Terminology questions and trivial, fully specified edits stay on the direct path.

Once activated for implementation, Build Brief must complete an implementation-ready Design Contract before modifying code, tests, configuration, or schemas. The contract proceeds top-down from the current system boundary and observable behavior to invariants, ownership, state, contracts, execution flow, material failure semantics, implementation slices, and proof.

This gate is proportional. It fixes the consequential design for the requested change; it does not attempt to freeze the architecture of the whole system.

## Example

Input:

> When inventory drops below five, notify the buyer once. Several inventory updates may arrive close together.

The plugin should translate this into consequences such as detecting a threshold crossing instead of every low-stock write, making duplicate suppression safe under concurrent updates, defining notification failure behavior, and testing the boundary and race cases. It should not merely answer “use event-driven architecture and idempotency.”

## Install from GitHub

Requires a Codex version with plugin marketplace support.

```bash
codex plugin marketplace add grapefruit0205/build-brief
codex plugin add build-brief@build-brief
```

Restart the ChatGPT desktop app after installing, then begin a new conversation.

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
- Do not modify implementation files until the proportional Design Contract passes its gate.
- Execute the directive when implementation was requested; do not stop at a design document.
- Keep small changes small and avoid vocabulary theater.

## Repository layout

```text
.codex-plugin/plugin.json             Plugin manifest
.agents/plugins/marketplace.json      GitHub marketplace entry
skills/build-brief/SKILL.md           Skill entry point
skills/build-brief/references/        Conditional translation guidance
evals/golden-prompts.yaml             Activation and semantic test cases
```

This release contains no hook, MCP server, app connection, or credential requirement.

## Validation

The repository includes positive, negative, boundary, and Korean-language cases in `evals/golden-prompts.yaml`. These cases describe expected activation and semantic invariants; they are not presented as benchmark results.

Structural validation:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py skills/build-brief
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
```

For behavioral evaluation, run the same representative prompts with and without the plugin and compare task correctness, missed invariants, unnecessary architecture, clarification turns, and proof of completion.

## Current scope

Build Brief is intentionally a lean skills-only release. The design gate is instruction-enforced and should be measured on real workflows. Add a hard write-blocking hook only if repeated evaluations show that the Skill-level gate is insufficient.
