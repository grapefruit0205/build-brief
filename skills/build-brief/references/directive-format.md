# Software Design Directive Format

Use this format only when the user asks to see, reuse, review, or hand off the translated command. Keep it proportional to the work.

## Intent

Restate the desired software behavior in one or two sentences without replacing the user's product meaning.

## System boundary

Identify the existing component, domain boundary, data owner, or external contract that owns the change. For a new system, define only the boundary needed for the requested outcome.

## Design contract

State the observable behavior and invariants first, then the responsibilities, state and data ownership, contracts, and execution flow that preserve them. Include timing, concurrency, consistency, failure, security, compatibility, migration, and operations only where they materially affect the request.

## Minimum sufficient design

Treat the required behavior as a hard gate, then minimize the design delta. Name the existing boundaries and mechanisms that will be reused. For each material new service, store, asynchronous boundary, public contract, dependency, abstraction, configuration surface, or operational component, state the current evidence that requires it, why a smaller change is insufficient, the failure it prevents, and how that claim will be tested. Omit speculative future-proofing and reject a larger candidate when a smaller one preserves the same invariants.

## Engineering directive

Derive imperative implementation steps from the Design Contract. Name the relevant code or system boundaries, domain and state semantics, contracts, failure behavior, operational constraints, and rollout concerns only where they affect this request.

Each design term must be attached to a concrete action or invariant. Do not output a bag of labels.

## Proof of completion

Specify observable user behavior and the focused tests, checks, or operational evidence that demonstrate completion.

## Assumptions requiring visibility

Include only consequential inferred assumptions. If a missing decision truly blocks safe work, state the question instead of inventing an answer.

Collapse sections when the task is small, but preserve the top-down order from boundary and behavior through minimality to implementation and proof.
