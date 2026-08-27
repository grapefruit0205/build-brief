---
name: click
description: When explicitly invoked for software work, compile repository-aware intent into one approval-bound execution contract, explain it plainly, then implement it in one shot with a user-approved verification scale. Never invoke implicitly.
---

# Click

Translate the user's natural-language intent and actual repository context into the software-design and execution language the situation needs. Click is a semantic compiler and one-shot approval boundary, not a chooser over fixed architecture labels.

## Activate only when explicitly selected

- Activate when the user selects Click or invokes `$click` for the current software work.
- Treat “설계해줘”, “구현해줘”, “해줘”, “design it”, “build it”, and equivalent wording in any language as the same complete-contract workflow after explicit selection.
- A question about Click is not an invocation. Never activate merely because work is large, architectural, vague, or risky.
- If the user opts out after activation, run `click-gate bypass` and return to the ordinary workflow.

Run `click-gate arm` before the first mutation. Read-only inspection remains available. Enable session-wide strict mode only when the user explicitly asks, with `click-gate mode strict`; otherwise keep adaptive mode.

## Preserve intent without conducting a questionnaire

Treat the requested outcome, user-visible behavior, scope, constraints, and authorization as authoritative. Inspect the repository from the narrowest relevant entry point and widen only while a consequential behavior remains unresolved.

Do not ask a series of technical preference questions before producing the contract. Infer implementation choices from the repository and current requirement. Put consequential assumptions or proposed product choices visibly into the contract so the user can accept or change them in the single approval review. Ask before the contract only when even proposing a safe contract requires missing authority, such as choosing another person's account or committing an irreversible external action.

Do not treat an existing system as blank or infer permission for unrelated cleanup, migration, or product expansion. If the user asks only for a contract or handoff, produce the same contract without implementation.

For broad cross-boundary work, read [references/translation-guide.md](references/translation-guide.md). Whenever a contract will be shown or staged, read [references/directive-format.md](references/directive-format.md) and [references/verification-profiles.md](references/verification-profiles.md).

## Compile one authoritative contract

Generate one compact developer execution contract with all non-empty fields below:

- `boundary`: the owner of the behavior and the limit of the approved outcome;
- `invariants`: observable requirements that must remain true;
- `system_semantics`: only the state, ownership, flow, timing, ordering, concurrency, consistency, failure, security, compatibility, migration, and operational meaning needed by those invariants;
- `plan`: goal, scope, non-goals, and top-down approach;
- `implementation`: concrete design mapped onto the current system;
- `phases`: proportional implementation groupings, not approval gates;
- `steps`: ordered changes, not mandatory verification points;
- `tasks`: concrete code, test, configuration, schema, or documentation units inside the approved boundary;
- `execution_order`: only dependencies or sequencing that materially constrain execution;
- `minimality`: current structure to reuse and the reason for material additions, without banning any technology class;
- `proof`: observable acceptance criteria;
- `verification`: recommended and selected verification scale, rationale, one final check batch, and any exceptional intermediate gate;
- `plain_language`: a faithful easy explanation of the complete contract.

Keep execution fields distinct and proportional. Small work can use one concise item per field. These fields describe one implementation, not separate review or test ceremonies.

The contract is semantic rather than literal: it fixes the approved result, boundary, invariants, material system behavior, constraints, and verification commitment. It deliberately grants freedom to choose necessary in-scope libraries, dependencies, MCP tools, external services, graders, file edits, and low-level tactics during implementation.

## Recommend verification once

Recommend `quick`, `focused`, or `full` from present risk and repository evidence. Set `selected` to the recommendation unless the user requests another scale. Contract approval also approves that selected scale; do not ask a second verification question.

Run the listed `final_checks` together once after implementation. Do not revalidate every contract field after every phase, step, or task. Use `intermediate_gate` only when a later action depends on an irreversible migration, destructive operation, deployment, paid external call, or similarly unrecoverable boundary. Routine edits, builds, and reversible implementation choices are not intermediate gates.

## Show both views and ask once

1. Stage the exact JSON with `click-gate stage '<Execution Contract JSON>'`.
2. Show the complete developer contract.
3. Show its faithful plain-language explanation in the user's language, including the selected verification scale.
4. Ask one compact question: approve, change the proposed contract, simplify the explanation, or cancel.
5. Stop without mutating project files.

The original request is not approval of an unseen contract. Before approval, a requested change replaces the staged proposal and both views are shown again. The easy explanation must not add or hide material meaning.

## Implement the approved contract in one shot

After explicit approval:

1. Run `click-gate arm` in the approval turn.
2. Run `click-gate pass '<Execution Contract JSON>'` with the exact staged JSON.
3. Implement continuously inside the approved semantic boundary.
4. Run the selected final verification batch once and report results and material implementation choices.

Do not create a replacement contract or request reapproval for an in-scope technical choice. MCP tools, external services, dependencies, graders, architecture tactics, files, and implementation order may change when necessary to deliver the approved result while preserving its boundary and invariants. The approved contract remains unchanged because it already grants that implementation freedom.

Stop only when completion needs authority the user has not granted, an irreversible or paid external action not covered by approval, or a change to the approved outcome, user-visible behavior, boundary, invariant, or verification commitment. Report the blocker; do not silently widen the work or substitute a new mid-run contract.

## Prevent overdesign by evidence, not bans

Choose the smallest design that satisfies every invariant. No component category is forbidden. A new dependency, service, queue, store, MCP, grader, abstraction, or operational component is valid when it is a proportionate way to complete the approved work. Prefer existing structure when it is equally capable; do not add speculative architecture for hypothetical scale, teams, or reuse.

The Hook validates contract shape, mutation ordering, and exact staged-versus-passed equality. It cannot prove design truth, semantic implementation fidelity, or authentic human approval. If Hook enforcement is unavailable, preserve the same ordering at instruction level and disclose that fact.

## Communicate plainly

Use the user's language. Lead with the resulting behavior, explain important safeguards and the selected verification cost, then ask the single approval question. Avoid architecture slogans and serial option menus.
