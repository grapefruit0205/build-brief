# Translation Guide

Use this guide to convert product intent into a handoff-quality software-design directive. The vocabulary is open-ended and must emerge from the request, codebase, and operating context. Never treat the examples below as a taxonomy from which one label must be selected.

## Translate in four passes

### 1. Recover the intended reality

Identify the actors, desired outcome, observable behavior, existing constraints, and what the user considers done. Distinguish product facts from implementation guesses.

### 2. Read the actual system

When code exists, trace the relevant behavior and learn the system's own language: modules, domain objects, state stores, interfaces, asynchronous paths, deployment boundaries, failure handling, and tests. Reuse established concepts when they still fit.

### 3. Generate the necessary design semantics

Mobilize any software-engineering concept that makes an implicit requirement precise. Depending on the situation, useful language may come from domain modeling, state machines, contracts, transaction boundaries, concurrency control, consistency models, data lifecycle, ports and adapters, queues, scheduling, caching, resilience, security, observability, migrations, testing, or another relevant discipline.

This list is illustrative, not limiting. Start from the situation and derive the language; never start from the list and force the situation into it.

Every term must earn its place by implying at least one concrete action or invariant. If removing a term would not change the implementation or its verification, omit it.

Correctness is the hard gate; minimality ranks only candidates that satisfy it. Reuse the current boundary, runtime, data ownership, dependencies, and operational path unless present evidence shows that doing so cannot preserve a required invariant. A new deployable unit, store, queue or asynchronous boundary, public contract, framework, abstraction, configuration surface, or operational component must identify the current need, why existing structure is insufficient, the failure prevented, and the proof. Hypothetical scale or reuse is not evidence.

### 4. Emit an imperative directive

Turn the semantics into commands an implementation agent can follow:

- locate the behavior in the correct boundary;
- model the relevant state and invariants;
- define inputs, outputs, and compatibility contracts;
- specify ordering, concurrency, consistency, and failure semantics where material;
- constrain data, security, performance, or operations where material;
- require observable proof of the user-visible outcome.

The directive may be used internally for immediate execution or surfaced for a human or another agent.

Before implementation writes begin, make sure these passes form an implementation-ready Design Contract: the owning boundary is known, observable behavior and invariants are explicit, consequential system semantics are resolved, the smallest justified design delta is selected, and completion evidence is defined. This is the design gate. Keep it proportional to the change rather than attempting to finish the architecture of the entire system.

## Translate consequences, not labels

Weak translation:

> Use an event-driven, functional, modular architecture.

Strong translation:

> At the existing publication boundary, preserve the current write path and use the repository's notification mechanism. Make delivery idempotent per follower and post where duplicate delivery is a real risk, define how notification failure affects publication, and test that behavior. Add no new service or broker unless current reliability requirements and repository evidence show the existing path cannot preserve those invariants.

The strong form may use established design terms when they compress meaning, but it also states what those terms require in this system.

## Adapt depth to the task

- For a small change, the compiled directive may be one sentence naming the boundary, invariant, and check.
- For a cross-cutting feature, include the affected contracts, state transitions, failure semantics, rollout, and verification.
- For legacy code, express safe-change commands such as tracing callers, characterizing current behavior, creating a seam, preserving compatibility, and changing incrementally.
- For a new system, establish only the boundaries and operational qualities required now. Do not fabricate future scale or team structure.

## Reject unjustified design delta

For every candidate, account for material additions. Reject it when any addition lacks current evidence, exists only for possible future reuse or scale, duplicates an adequate existing mechanism, or has no concrete failure and proof attached. If two candidates satisfy the same invariants, prefer the one that adds fewer boundaries, dependencies, stores, contracts, abstractions, and operational responsibilities.

Do not turn this into a raw component-count contest. A necessary transaction boundary, deduplication record, compatibility layer, or failure path remains required when the invariant demands it; omitting it is under-design, not simplicity.

## Avoid vocabulary theater

- Do not expose a glossary unless the user asks for teaching.
- Do not ask the user to pick among design labels the translator can resolve.
- Do not decorate an ordinary function or edit with architecture language.
- Do not equate a named pattern with a finished command.
- Do not silently replace the user's product intent with a technically interesting adjacent problem.

## Completion test

The design gate is ready when an implementation agent can act without guessing about consequential behavior, while retaining freedom over low-level details that do not affect the user's outcome. Implementation must not begin before this condition is met.
