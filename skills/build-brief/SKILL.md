---
name: build-brief
description: When explicitly invoked for software work, compile repository-aware intent into a complete developer execution contract, explain the same contract plainly, wait for approval, then implement only the approved contract. Never invoke implicitly.
---

# Build Brief

Translate the user's natural-language intent and actual repository context into the software-design and execution language this situation needs. Build Brief is a semantic compiler and approval boundary, not a chooser over fixed architecture labels.

## Activate only when explicitly selected

- Activate when the user selects Build Brief or explicitly invokes `$build-brief` for the current software work.
- Once selected, treat requests such as “설계해줘”, “구현해줘”, “해줘”, “design it”, “build it”, and equivalent wording in any language as the same full-contract workflow. Classify intent, not literal verbs.
- A question about Build Brief is not an invocation to apply it.
- Do not infer activation because a request is large, architectural, vague, risky, or consequential.
- Do not activate when the user asks to proceed without Build Brief. If the current turn was armed, run `build-brief-gate bypass` and immediately return to the ordinary workflow.

Users do not need to choose architecture vocabulary. Infer the relevant design language from the requirement and repository. Enable session-wide strict mode only when the user explicitly asks, with `build-brief-gate mode strict`; leave it with `build-brief-gate mode adaptive`.

## Preserve meaning and authorization

- Treat the requested outcome, scope, product decisions, and authorization as authoritative.
- Use the codebase's boundaries, domain language, runtime, data model, dependencies, failure handling, and tests.
- Do not treat an existing project as a blank system or translate a request into permission for a rewrite, migration, new service, or wider product.
- Do not invent scale, latency, organization, deployment, compliance, compatibility, or future-reuse requirements.
- If the user explicitly requests a contract or handoff without coding, produce the same complete execution contract but do not implement it.

## Inspect from the narrowest evidence frontier

Run `build-brief-gate arm` as soon as explicit invocation starts, before any mutation. Read-only inspection remains available.

Start at the behavior named by the request. Locate its owning entry point, state or data owner, external contracts, and focused tests. Widen inspection only while a consequential behavior remains unresolved. Stop when the owning boundary, observable behavior, material system semantics, smallest justified design delta, executable work, and completion evidence are known without a consequential guess.

For broad or cross-boundary work with non-obvious state, failure, compatibility, or handoff semantics, read [references/translation-guide.md](references/translation-guide.md).

## Compile one authoritative execution contract

Read [references/directive-format.md](references/directive-format.md) whenever a contract will be shown or staged.

Generate one compact developer-facing contract. It must contain all of these non-empty fields:

- `boundary`: the current component, data owner, or external contract that owns the behavior;
- `invariants`: observable requirements and facts that must remain true;
- `system_semantics`: only the state, ownership, flow, timing, ordering, concurrency, consistency, failure, security, compatibility, migration, and operational meaning needed to preserve the invariants;
- `plan`: the approved goal, scope, non-goals, and top-down approach;
- `implementation`: the concrete design mapped onto existing code and system boundaries;
- `phases`: proportional implementation checkpoints;
- `steps`: ordered changes within those checkpoints;
- `tasks`: concrete code, test, configuration, schema, or documentation units covered by approval;
- `execution_order`: dependencies and sequencing that constrain safe execution;
- `minimality`: existing structure to reuse and present evidence for every material addition;
- `proof`: acceptance criteria and focused verification.

Also include `plain_language`, a faithful non-empty explanation of the complete developer contract. Keep the six execution fields distinct instead of repeating the same list under different names. A small change can use one concise item per field; required fields are not permission to inflate the work.

The contract is ready only when consequential behavior no longer depends on an unstated guess, each design term changes an invariant or execution constraint, every task remains inside the requested scope, and no larger design is chosen when a smaller one preserves the same invariants.

## Present, translate, and request approval

Create the developer contract first. Then derive its easy explanation from that completed contract.

1. Stage the exact JSON that will be shown with `build-brief-gate stage '<Execution Contract JSON>'`.
2. Show the authoritative developer execution contract.
3. Show the faithful plain-language translation in the user's language.
4. Ask whether the user approves, wants a revision, wants a simpler explanation, or wants to cancel.
5. Stop without passing the gate or modifying code, tests, configuration, schemas, or other project files.

The original request—even “설계해줘”, “구현해줘”, “해줘”, “build it”, or “do it”—is not approval of a contract that had not yet been shown. The easy explanation may simplify terminology but must neither add a decision absent from the developer contract nor hide a material invariant, compatibility promise, failure behavior, implementation element, task, or execution constraint. Regenerate it whenever the contract changes.

## Execute only the approved contract

After the user explicitly approves the displayed contract:

1. Run `build-brief-gate arm` in the approval turn.
2. Run `build-brief-gate pass '<Execution Contract JSON>'` with the exact staged JSON.
3. Implement the approved `implementation`, `phases`, `steps`, `tasks`, `plan`, and `execution_order` while preserving every invariant and system semantic.
4. Run the approved proof and report the result.

Do not silently add behavior, scope, architecture, dependencies, schemas, public contracts, failure semantics, tasks, or execution changes absent from the approved contract. If repository discovery or implementation makes a material change necessary, stop mutation, revise the developer contract, regenerate the easy explanation, stage the revised JSON, show both views, and obtain approval again. Low-level reversible choices already contained by the approved boundary and tasks do not require a new contract.

If the user asks only for a simpler explanation, keep the developer contract unchanged, rewrite only `plain_language` faithfully, stage the updated paired artifact, and ask again. If the user cancels or opts out, do not implement.

The Hook stores only contract digests outside the repository. It validates shape, mutation ordering, and equality between the staged and passed contract; it cannot prove design truth, semantic implementation fidelity, or authentic human approval. The Skill must preserve those boundaries. If the Hook is disabled or untrusted, follow the same ordering at instruction level and disclose that runtime enforcement was inactive.

## Enforce minimum-sufficient design

Required behavior and invariants are the correctness gate. Among candidates that satisfy them, choose the smallest justified design delta and maximize reuse of the current system.

A new deployable unit, store, queue or asynchronous boundary, public contract, framework or dependency, abstraction layer, configuration surface, or operational component belongs only when a current requirement or repository fact requires it, the existing structure cannot preserve an invariant with a smaller change, the prevented failure is concrete, and focused proof is available.

Hypothetical scale, future reuse, imagined teams, and fashionable vocabulary are not evidence. Do not remove necessary concurrency, safety, compatibility, or failure behavior merely to make the design look smaller.

## Resolve ambiguity proportionally

Ask the smallest question only when the answer changes public behavior, cost, data safety, security, or a difficult-to-reverse decision. Otherwise use a conservative, reversible assumption and expose it when consequential. Never ask the user to choose technical vocabulary that repository evidence can resolve.

## Communicate plainly

- Use the user's language and level of technical detail.
- Show the authoritative developer contract before its easy translation, then ask one compact approval question.
- Prefer concrete invariants and consequences over architecture slogans.
- Keep the contract proportional so Build Brief adds clarity without turning a small change into a large project.
