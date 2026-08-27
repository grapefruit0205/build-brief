# Translation Guide

Use this guide to turn product intent into an approval-ready software Design Contract. The vocabulary is open-ended and must emerge from the request, codebase, and operating context. Never treat the examples below as a taxonomy from which one label must be selected.

## Recover the intended reality

Identify the actors, desired outcome, observable behavior, existing constraints, and what the user considers done. Distinguish product facts from implementation guesses.

## Read the actual system

When code exists, trace the relevant behavior and learn the system's language: modules, domain objects, state stores, interfaces, asynchronous paths, deployment boundaries, failure handling, and tests. Reuse established concepts when they still fit.

## Generate only necessary design semantics

Use any software-engineering concept that makes an implicit requirement precise. Depending on the situation, useful language may come from domain modeling, state machines, contracts, transaction boundaries, concurrency control, consistency models, data lifecycle, ports and adapters, queues, scheduling, caching, resilience, security, observability, migrations, testing, or another relevant discipline.

The list is illustrative, not limiting. Start from the situation and derive the language; never start from the list and force the situation into it. Every term must earn its place by changing an invariant, implementation constraint, or proof condition.

Correctness is the hard gate. Minimality ranks only candidates that satisfy it. Reuse the current boundary, runtime, data ownership, dependencies, and operational path unless present evidence shows they cannot preserve a required invariant.

A new deployable unit, store, queue or asynchronous boundary, public contract, framework, abstraction, configuration surface, or operational component must identify the current need, why existing structure is insufficient, the failure prevented, and focused proof. Hypothetical scale or reuse is not evidence.

## Express a contract, not a task plan

State the owning boundary, observable invariants, relevant system semantics, minimum justified design delta, and proof. These are constraints the implementation must satisfy, not directions about which file to edit first or how to divide the work.

Do not emit phases, numbered steps, tasks, a work breakdown, or execution order. Preserve the implementation agent's freedom over low-level sequencing and reversible details that do not affect the approved meaning.

## Mirror the contract in plain language

Create a short explanation from the completed developer contract. Explain the user-visible result, important safeguards, unchanged behavior, and material failure or tradeoff in familiar language. Do not introduce new design decisions or omit material consequences.

Weak translation:

> Use an event-driven, functional, modular architecture.

Strong developer contract:

> At the existing publication boundary, preserve the current write path and notification mechanism. Make delivery idempotent per follower and post where duplicate delivery is a real risk, define how notification failure affects publication, and require proof for that behavior. Add no service or broker unless current reliability requirements and repository evidence show the existing path cannot preserve those invariants.

Faithful plain-language explanation:

> Publishing continues through the current system. A follower should receive each notification once even if the same work is retried, and a notification failure must not silently change whether the post was published. No new service or message broker is added unless the existing notification path is proven unable to provide those safeguards.

## Adapt depth without changing the output kind

A small change may need one sentence per contract concern. Cross-boundary work may need affected contracts, state transitions, failure semantics, rollout constraints, and verification. Legacy work may require compatibility and characterization obligations. A new system should establish only the boundaries and operational qualities required now.

Depth may change; the output remains a Design Contract plus its plain-language explanation, never a task plan.

## Reject unjustified design delta

Reject any material addition that lacks current evidence, exists only for possible future reuse or scale, duplicates an adequate mechanism, or has no concrete failure and proof attached. If two candidates preserve the same invariants, prefer the one adding fewer boundaries, dependencies, stores, contracts, abstractions, and operational responsibilities.

Do not turn this into raw component counting. A necessary transaction boundary, deduplication record, compatibility layer, or failure path remains required when the invariant demands it; omitting it is under-design, not simplicity.

## Completion test

The contract is ready when an implementation agent can preserve every consequential behavior without guessing, while remaining free to choose low-level work sequencing. The plain-language explanation is ready when a non-specialist can understand the same approved meaning without a material omission or contradiction.
