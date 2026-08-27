---
name: build-brief
description: Compile non-trivial software build or change requests with consequential behavior left implicit into a proportional Design Contract before edits, then execute or hand off. Skip explanations and trivial fully specified edits.
---

# Build Brief

Compile the user's natural-language intent and actual repository context into the software-design language this situation needs, then issue it as an actionable implementation command. This is a semantic translation layer, not a chooser over a fixed catalog of architectures or programming styles.

## Route depth before spending context

Keep automatic discovery cheap and correct:

- For an explanation or other request with no implementation, answer directly without manufacturing a directive.
- For a trivial, fully specified edit, return control to the ordinary workflow. If Build Brief was explicitly invoked or the mutation hook requests a contract, use a compact contract with one concise item per field.
- For consequential work, form a full but proportional contract. Read [references/translation-guide.md](references/translation-guide.md) only when the change is broad, crosses boundaries, or has non-obvious state, failure, compatibility, or handoff semantics.

These are context-depth choices, not architecture categories. Do not ask the user to select design vocabulary the request and repository can resolve.

## Preserve meaning and authorization

- Treat the requested outcome, scope, product choices, and authorization as authoritative.
- Incorporate the codebase's existing boundaries, domain language, runtime, data model, dependencies, failure handling, and tests.
- Do not translate an existing project as though it were a blank system.
- Do not turn translation into permission for a rewrite, migration, new service, or wider product.
- Do not invent scale, latency, organization, deployment, compliance, or compatibility constraints.

## Inspect from a narrow evidence frontier

Before designing an implementation, start at the behavior named by the request: find its owning entry point, immediate state owner, relevant contracts, and focused tests. Widen the search only while a consequential behavior remains unresolved. Do not scan the whole repository, create a complete architecture map, or load supporting references merely because the task is large.

Stop inspecting when the owning boundary, observable behavior, material system semantics, implementation slices, and completion evidence are known well enough to act without a consequential guess.

## Compile a proportional Design Contract

Make implicit engineering consequences explicit only when they change code, configuration, data, operations, or verification. Useful language may come from domain modeling, state transitions, contracts, concurrency, consistency, failure handling, data lifecycle, security, performance, observability, migration, or another relevant discipline; this vocabulary is open-ended.

Complete the Design Contract top-down:

1. **Boundary:** locate the current component, data owner, or external contract that owns the behavior.
2. **Invariants:** define the requested observable behavior and what must remain true.
3. **System semantics:** resolve only the responsibilities, state, flow, timing, ordering, concurrency, consistency, failure, security, compatibility, migration, and operations that materially affect those invariants.
4. **Implementation:** derive the smallest coherent implementation slices.
5. **Proof:** define focused tests, checks, or operational evidence that prove the behavior.

The gate passes only when consequential behavior no longer depends on an unstated guess and every design term changes an implementation action, invariant, or verification step. A local edit may need one sentence; a cross-boundary feature may need a fuller contract. Keep the contract internal unless the user requests review or a reusable directive.

## Pass the mutation gate

Do not modify code, tests, configuration, schemas, or other local files before the Design Contract passes.

When the installed plugin hook supplies a `build-brief-gate pass` command, run that exact virtual command after completing the contract and before the first mutation. Supply a compact JSON object with:

- `boundary`: a non-empty string;
- `invariants`: a non-empty list of observable requirements;
- `implementation`: a non-empty list of coherent implementation slices;
- `proof`: a non-empty list of completion evidence.

Keep the payload proportional and do not use the command as a substitute for design. The hook records only a digest in plugin data outside the repository. If the hook command is unavailable, follow the same instruction-level gate without inventing a command or repository marker.

Read-only repository inspection may happen before the gate. A review-only, plan-only, or directive-only request makes no mutation and therefore does not need to pass the runtime mutation gate.

## Route the compiled command

Match the user's requested outcome:

- **Build or change:** pass the Design Contract and mutation gates, implement, verify the invariants, and report the outcome. Do not stop after translation or require approval for reversible details resolved by repository evidence.
- **Review first:** read [references/directive-format.md](references/directive-format.md), expose the contract in top-down order, and wait for approval before implementation.
- **Plan, handoff, or directive only:** read [references/directive-format.md](references/directive-format.md), expose a concise reusable directive, and do not implement it.
- **Compare implementations:** compile serious alternatives into concrete consequences and compare those consequences rather than their labels.

Explicit `$build-brief` invocation always activates the skill and follows the requested mode. Without explicit invocation, allow discovery only for non-trivial software work whose consequential engineering behavior remains implicit.

## Resolve ambiguity proportionally

- Ask the smallest question only when its answer materially changes public behavior, cost, data safety, security, or a difficult-to-reverse decision.
- If such a decision remains unresolved, do not pass the gate or begin implementation.
- Otherwise use a conservative, reversible assumption and disclose it only when consequential.
- Do not present a vocabulary menu when a coherent directive can be inferred.

## Communicate plainly

- Use the user's language and level of technical detail.
- Lead with the outcome and expose design terminology only when requested or materially clarifying.
- Prefer executable verbs and concrete invariants over architecture slogans.
- Define completion through observable behavior and evidence, not sophisticated vocabulary.
