# Translation Guide

Turn product intent into one approval-ready developer execution contract. Design vocabulary must emerge from the request, repository, and operating context; never select from a fixed architecture taxonomy.

## Recover the intended reality

Identify actors, desired outcome, observable behavior, explicit constraints, and the user's definition of done. Treat compatibility, data safety, no-code, handoff, and scope restrictions as binding.

When details are missing, avoid a serial questionnaire. Infer reversible technical choices from repository evidence. Put consequential assumptions or proposed product choices into the contract so the user reviews them together. Ask early only when no safe proposal can be made without authority the user has not granted.

## Read the actual system

Trace the named behavior from its narrowest entry point. Learn the owning modules, domain state, interfaces, asynchronous paths, deployment boundaries, failure handling, and focused tests. Widen inspection only while an unresolved fact would change the user-visible outcome, semantic boundary, data safety, public contract, or required authority.

## Generate necessary design semantics

Use any engineering concept that makes the requirement precise: domain models, state machines, contracts, transactions, concurrency, consistency, queues, scheduling, caching, resilience, security, observability, migrations, testing, or another discipline. This list is illustrative, not limiting.

Every term must change an invariant, material implementation constraint, execution dependency, or proof condition. Choose the smallest design that satisfies the invariants, but do not ban a component by category. A service, dependency, MCP, grader, queue, or store is valid when it is a proportionate in-scope means of delivering the approved result.

## Translate design into executable work

Build top-down:

1. Fix the outcome, semantic boundary, non-goals, owner, invariants, and material system meaning.
2. Map those obligations onto a concrete design that fits the current system.
3. Derive proportional phases and steps from real dependencies.
4. Name concrete deliverables without turning them into separate approval gates.
5. Record ordering only where sequence affects safe completion.
6. Define observable proof, recommend a verification scale, and group checks into one final batch.

An implementation agent may change low-level tactics, dependencies, tools, files, or internal sequencing without reapproval when the result remains inside the contract's outcome, boundary, invariants, material semantics, constraints, and verification commitment.

## Mirror the complete contract plainly

Create the easy explanation after the developer contract. Explain what the user gets, what remains unchanged, the important safeguards, the broad route, and the selected verification cost. It is a faithful projection, not a second design.

## Execute one shot

After approval, keep the staged contract unchanged and finish within its semantic envelope. Do not create a replacement contract for an in-scope implementation discovery. Report material technical choices in the final result.

Stop only for new authority, an uncovered irreversible or paid external action, or a necessary change to the approved outcome, user-visible behavior, boundary, invariant, or verification commitment. A blocker is not permission to widen the contract silently.

Implementation is complete when the selected final verification batch passes, or failures are reported without claiming success.
