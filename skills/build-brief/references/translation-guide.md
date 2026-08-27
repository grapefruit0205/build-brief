# Translation Guide

Use this guide to turn product intent into an approval-ready developer execution contract. The vocabulary must emerge from the request, codebase, and operating context. Never treat architecture terms as a fixed taxonomy from which one label must be selected.

## Recover the intended reality

Identify the actors, desired outcome, observable behavior, existing constraints, and what the user considers done. Distinguish product facts from implementation guesses. Treat any explicit no-code, handoff, compatibility, data-safety, or scope restriction as binding.

## Read the actual system

Trace the named behavior from its narrowest entry point. Learn the system's modules, domain objects, state stores, interfaces, asynchronous paths, deployment boundaries, failure handling, and focused tests. Reuse established concepts when they still fit.

Widen inspection only when an unresolved decision would change observable behavior, data safety, a public contract, an expensive-to-reverse boundary, or the executable work the user will approve.

## Generate necessary design semantics

Use any software-engineering concept that makes an implicit requirement precise. Depending on the situation, relevant language may come from domain modeling, state machines, contracts, transaction boundaries, concurrency control, consistency models, data lifecycle, ports and adapters, queues, scheduling, caching, resilience, security, observability, migrations, testing, or another discipline.

The list is illustrative, not limiting. Start from the situation and derive the language; never start from the list and force the situation into it. Every term must earn its place by changing an invariant, implementation constraint, approved task, execution dependency, or proof condition.

Correctness is the hard gate. Minimality ranks only candidates that satisfy it. Reuse the current boundary, runtime, data ownership, dependencies, and operational path unless present evidence shows they cannot preserve a required invariant.

## Translate design into executable work

Build the contract top-down instead of starting with a generic checklist:

1. Fix the goal, scope, non-goals, owner, invariants, and material system semantics.
2. Map those obligations onto the smallest concrete implementation that fits the existing system.
3. Derive proportional phases and steps from real dependencies.
4. Name only the concrete tasks covered by the approved scope.
5. Record execution ordering only where sequence affects safety, compatibility, or successful delivery.
6. Attach focused proof to the invariants and tasks.

All six execution fields are required, but they must not become six copies of the same plan. A one-file change may need one compact item in each field. Cross-boundary work may need more detail. Field presence does not justify extra architecture, speculative preparation, or unrelated cleanup.

## Mirror the complete contract in plain language

Create the easy explanation only after the developer contract is complete. Explain the user-visible result, important safeguards, unchanged behavior, how the approved work proceeds, and material failure or tradeoff in familiar language. Do not introduce new design decisions or omit material consequences.

Weak translation:

> Use an event-driven, functional, modular architecture, then implement it in phases.

Strong developer meaning:

> At the existing publication boundary, preserve the current write path and notification mechanism. Make delivery idempotent per follower and post where retry can duplicate work, define how notification failure affects publication, update only the owning publication and notification units, and verify retry and failure behavior before completion. Add no service or broker unless repository evidence proves the existing path cannot preserve those invariants.

Faithful plain explanation:

> Publishing continues through the current system. Retrying the same work must not send a follower the same notification twice, and a notification failure must not silently change whether the post was published. We will change only the existing publishing and notification paths and test retries and failures; no new service or message broker will be added without evidence that the current path cannot provide those safeguards.

## Reject unjustified design delta

A new deployable unit, store, queue or asynchronous boundary, public contract, framework, abstraction, configuration surface, or operational component must identify the current need, why existing structure is insufficient, the failure prevented, and focused proof. Hypothetical scale, possible reuse, imagined teams, and fashionable vocabulary are not evidence.

Do not turn minimum-sufficient design into raw component counting. A necessary transaction boundary, deduplication record, compatibility layer, migration, or failure path remains required when an invariant demands it; omitting it is under-design, not simplicity.

## Guard approval fidelity

The staged contract is the implementation boundary. During execution, compare every material discovery and proposed change against it. If behavior, scope, architecture, dependency, schema, public contract, failure semantics, task coverage, or execution constraints would change, stop and request approval of a revised staged contract. Do not hide scope growth inside “implementation details.”

## Completion test

The contract is ready when an implementation agent can preserve every consequential behavior and execute the named work without a material guess. The plain-language explanation is ready when a non-specialist can understand that same approved meaning without an omission or contradiction. Implementation is complete only when the approved proof passes or any failure is reported without silently widening the contract.
