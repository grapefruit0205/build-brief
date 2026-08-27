---
name: click
description: When explicitly invoked for software work, compile repository-aware intent into one approval-bound execution contract, explain it plainly, then implement it in one shot with a user-approved verification scale. Never invoke implicitly.
---

# Click

Translate the user's natural-language intent and actual repository context into the software-design and execution language the situation needs. Click is a semantic compiler and one-shot approval boundary, not a chooser over fixed architecture labels.

## Activate only when explicitly selected

- Activate when the user selects or mentions `@Click`, or directly invokes the underlying `$click` Skill, for the current software work.
- Treat “설계해줘”, “구현해줘”, “해줘”, “design it”, “build it”, and equivalent wording in any language as the same complete-contract workflow after explicit selection.
- A question about Click is not an invocation. Never activate merely because work is large, architectural, vague, or risky.
- If the user opts out after activation, run `click-gate bypass` and return to the ordinary workflow.

Run `click-gate arm` before the first mutation. Read-only inspection remains available. Enable session-wide strict mode only when the user explicitly asks, with `click-gate mode strict`; otherwise keep adaptive mode.

## Preserve intent without conducting a questionnaire

Treat the requested outcome, user-visible behavior, scope, constraints, and authorization as authoritative. Inspect the repository from the narrowest relevant entry point and widen only while a consequential behavior remains unresolved.

Do not ask a series of technical preference questions before producing the contract. Infer implementation choices from the repository and current requirement. Put consequential assumptions or proposed product choices visibly into the contract so the user can accept or change them in the single approval review. Ask before the contract only when even proposing a safe contract requires missing authority, such as choosing another person's account or committing an irreversible external action.

Do not treat an existing system as blank or infer permission for unrelated cleanup, migration, or product expansion. If the user asks only for a contract or handoff, produce the same contract without implementation.

For broad cross-boundary work, read [references/translation-guide.md](references/translation-guide.md). Whenever a contract will be shown or staged, read [references/directive-format.md](references/directive-format.md) and [references/verification-profiles.md](references/verification-profiles.md).

## Compile one compact contract

Generate one developer execution contract with six top-level areas:

- `outcome`: the concrete result and user-visible behavior;
- `boundary`: `in_scope` work and explicit `out_of_scope` limits;
- `must_hold`: observable behavior, compatibility, safety, and other conditions that cannot change;
- `build`: a repository-aware `approach`, plus `semantics` or `order` only when they materially constrain the result;
- `verification`: one `quick`, `focused`, or `full` scale and observable `done_when` checks, plus `intermediate_gate` only for a real irreversible boundary;
- `plain_language`: a faithful easy explanation of the same contract.

Do not recreate `plan`, `implementation`, `phases`, `steps`, `tasks`, `execution_order`, `minimality`, or `proof` as separate fields or prose sections. Put the smallest sufficient implementation route in `build.approach`, material state or failure meaning in optional `build.semantics`, real sequencing constraints in optional `build.order`, and acceptance evidence in `verification.done_when`.

The contract is semantic rather than literal: it fixes the approved result, boundary, must-hold conditions, material system behavior, and verification commitment. It deliberately grants freedom to choose necessary in-scope libraries, dependencies, MCP tools, external services, graders, file edits, and low-level tactics during implementation.

## Recommend verification once

Choose `quick`, `focused`, or `full` from present risk and repository evidence. Contract approval also approves that scale; do not ask a second verification question.

Run the listed `done_when` checks together once after implementation. Do not revalidate every contract item during implementation. Use `intermediate_gate` only when a later action depends on an irreversible migration, destructive operation, deployment, paid external call, or similarly unrecoverable boundary. Omit it for routine edits, builds, and reversible implementation choices.

## Show both views and ask once

1. Stage the exact JSON with `click-gate stage '<Execution Contract JSON>'`.
2. Show the compact developer contract.
3. Show its faithful plain-language explanation in the user's language, including the verification scale.
4. Ask one compact question: approve, change the proposed contract, simplify the explanation, or cancel.
5. Stop without mutating project files.

The original request is not approval of an unseen contract. Before approval, a requested change replaces the staged proposal and both views are shown again. The easy explanation must not add or hide material meaning.

## Implement the approved contract in one shot

After explicit approval:

1. Run `click-gate arm` in the approval turn.
2. Run `click-gate pass '<Execution Contract JSON>'` with the exact staged JSON.
3. Implement continuously inside the approved semantic boundary.
4. Run the completion checks as one final batch and report results and material implementation choices.

Do not create a replacement contract or request reapproval for an in-scope technical choice. MCP tools, external services, dependencies, graders, architecture tactics, files, and implementation order may change when necessary to deliver the approved result while preserving its boundary and must-hold conditions. The approved contract remains unchanged because it already grants that implementation freedom.

Stop only when completion needs authority the user has not granted, an irreversible or paid external action not covered by approval, or a change to the approved outcome, user-visible behavior, boundary, must-hold condition, or verification commitment. Report the blocker; do not silently widen the work or substitute a new mid-run contract.

## Prevent overdesign by evidence, not bans

Choose the smallest design that satisfies every invariant. No component category is forbidden. A new dependency, service, queue, store, MCP, grader, abstraction, or operational component is valid when it is a proportionate way to complete the approved work. Prefer existing structure when it is equally capable; do not add speculative architecture for hypothetical scale, teams, or reuse.

The Hook validates contract shape, mutation ordering, and exact staged-versus-passed equality. It cannot prove design truth, semantic implementation fidelity, or authentic human approval. If Hook enforcement is unavailable, preserve the same ordering at instruction level and disclose that fact.

## Communicate plainly

Use the user's language. Lead with the resulting behavior, explain important safeguards and the verification cost, then ask the single approval question. Avoid architecture slogans and serial option menus.
