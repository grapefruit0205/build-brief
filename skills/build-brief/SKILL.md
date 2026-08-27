---
name: build-brief
description: Translate non-trivial product- or everyday-language requests to build, change, modernize, automate, or integrate software into context-aware design contracts and engineering directives, then plan or carry out the work. Use when desired behavior leaves consequential boundaries, state, contracts, timing, failure, compatibility, or verification implicit. Do not use automatically for terminology explanations or trivial, fully specified edits.
---

# Build Brief

Compile the user's natural-language intent into the software-design language this situation actually needs, then issue that translation as an actionable command to the execution phase. This is a semantic translation layer, not a chooser over a fixed catalog of architectures or programming styles.

## Preserve meaning and context

- Treat the requested outcome, scope, product choices, and authorization as authoritative.
- When a repository is available, inspect its instructions, code paths, boundaries, dependencies, runtime, data model, and tests before translating the request.
- Incorporate the codebase's existing design language and operational reality. Do not translate an existing project as though it were a blank system.
- Preserve product meaning while making implicit engineering consequences explicit.
- Do not turn translation into permission for a rewrite, migration, new service, or wider product.

If the request is only an explanation or a trivial explicit edit, handle it directly without manufacturing a design directive.

## Compile the design directive

Infer the semantics that matter to the requested behavior. These may include domain concepts, invariants, state transitions, boundaries, contracts, control flow, concurrency, consistency, failure behavior, data lifecycle, security, performance, observability, deployment, migration, and verification—but this is not a closed vocabulary or a checklist to fill.

For each inferred design term, translate it into an implementation consequence. A term belongs only if it changes code, configuration, data, operations, or verification. Do not produce labels such as “event-driven” or “functional” without the concrete command they imply here.

Read [references/translation-guide.md](references/translation-guide.md) when the request is broad, crosses system boundaries, has non-obvious failure or state semantics, or needs a handoff-quality directive. For straightforward work, translate directly from the repository and request without loading the guide.

Write the internal directive as imperatives addressed to the implementation agent. It should identify where the behavior belongs, what contracts and invariants must hold, how important failures are handled, and what evidence proves completion. Do not ask the user to supply technical vocabulary the skill can infer from context.

## Pass the design gate before implementation

For a build or change request, work top-down and complete an implementation-ready **Design Contract** before modifying code, tests, configuration, or schemas. Read-only repository inspection is part of forming the contract and may happen before the gate. Keep the contract internal unless the user requests review or a reusable directive.

The Design Contract is proportional readiness, not an attempt to freeze the complete system architecture. Establish only what this change needs:

1. Locate the current system boundary and behavior that own the change.
2. Define the desired observable behavior and invariants.
3. Resolve responsibilities, state ownership and transitions, contracts, and execution flow.
4. Resolve material timing, ordering, concurrency, consistency, failure, security, compatibility, migration, and operational semantics.
5. Derive implementation slices and the evidence that will prove the contract.

The gate passes only when consequential behavior no longer depends on an unstated guess and every design term changes an implementation action, invariant, or verification step. Omit categories that do not affect the request. A small explicitly invoked task may need only a one-sentence contract.

## Route the compiled command

Match the user's requested outcome:

- **Automatic build or change:** Pass the design gate internally, implement the contract, verify its invariants, and report the outcome. Do not stop after translation or require approval for reversible details the repository resolves.
- **Review first:** When the user asks to see or approve the design before coding, read [references/directive-format.md](references/directive-format.md), expose the Design Contract, and wait for approval before implementation.
- **Plan, hand off, or directive only:** Read [references/directive-format.md](references/directive-format.md) and expose a concise, reusable directive without implementing it.
- **Compare implementations:** Compile each serious alternative into its concrete consequences and compare those consequences, not just their names.

Explicit `$build-brief` invocation always activates the skill and follows the requested mode. Without explicit invocation, allow automatic discovery only for non-trivial work with implicit engineering consequences.

## Resolve ambiguity proportionally

- Ask the smallest set of questions only when an answer would materially change cost, public behavior, data safety, security, or a difficult-to-reverse decision.
- If such a decision remains unresolved, do not pass the design gate or begin implementation until the user decides it.
- Otherwise encode a conservative, reversible assumption into the directive and disclose it only when consequential.
- Do not invent scale, latency, organization, deployment, compliance, or compatibility constraints.
- Do not present a vocabulary menu when a coherent directive can be inferred.

## Communicate plainly

- Use the user's language and level of technical detail.
- Keep the user's prompt natural; technical fluency is the translator's responsibility.
- Lead with the outcome. Expose design terminology only when the user asks for the translation or when a term materially clarifies the result.
- Prefer executable verbs and concrete invariants over architecture slogans.
- Define completion through observable behavior and verification, not through the presence of sophisticated vocabulary.
