---
name: click
description: Compile repository-aware software intent into one approval-bound execution contract, explain it plainly, then implement it in one shot with anti-loop guards and an automatically enforced verification budget. Use when the user explicitly selects Click, or when Hook context says Click Always ON is enabled and the request will change software; use its read-only review guard for code review in Always ON mode. Do not use for questions, explanations, or simple inspection.
---

# Click

Translate the user's natural-language intent and actual repository context into the software-design and execution language the situation needs. Click is a semantic compiler and one-shot approval boundary, not a chooser over fixed architecture labels.

## Respect the selected operating mode

- When Hook context reports `Always ON`, use the complete-contract workflow for software creation, modification, deletion, refactoring, or repair. Do not require `@Click`.
- When Hook context reports `Manual`, activate only when the user selects or mentions `@Click`, or directly invokes `$click`.
- When the mode is unset, do not interrupt questions, explanations, code review, or simple read-only inspection. Before the first software mutation, ask once whether to use **Always ON (recommended)** or **Manual**, then run `click-gate default on` or `click-gate default manual` after the answer.
- Treat “설계해줘”, “구현해줘”, “해줘”, “design it”, “build it”, and equivalent wording in any language as the same complete-contract workflow when Click is active.
- A question about Click is not a mutation request. If the user opts out for one active turn, run `click-gate bypass` and return to the ordinary workflow for that turn.

For a code-review-only request in Always ON mode, run `click-gate review`, inspect without a build contract or approval, reuse successful evidence, and report findings without changing files. Do not activate review mode for a simple lookup or explanation. If the user requests fixes as part of the same request, use the complete contract instead of review mode.

Read [references/modes.md](references/modes.md) whenever choosing, changing, bypassing, or applying a mode. In Manual mode, run `click-gate arm` before staging. Always ON is already armed persistently. Read-only inspection remains available before the contract in either mode.

## Preserve intent without conducting a questionnaire

Treat the requested outcome, user-visible behavior, scope, constraints, and authorization as authoritative. Inspect the repository from the narrowest relevant entry point and widen only while a consequential behavior remains unresolved.

Do not ask a series of technical preference questions before producing the contract. Infer implementation choices from the repository and current requirement. Put consequential assumptions or proposed product choices visibly into the contract so the user can accept or change them in the single approval review. Ask before the contract only when even proposing a safe contract requires missing authority, such as choosing another person's account or committing an irreversible external action.

Do not treat an existing system as blank or infer permission for unrelated cleanup, migration, or product expansion. If the user asks only for a contract or handoff, produce the same contract without implementation.

For broad cross-boundary work, read [references/translation-guide.md](references/translation-guide.md). Whenever a contract will be shown or staged, read [references/directive-format.md](references/directive-format.md) and [references/verification-profiles.md](references/verification-profiles.md). Before post-approval implementation, read [references/anti-loop-policy.md](references/anti-loop-policy.md).

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

The Hook derives the executable ceiling automatically: `quick` has 1 unit, `focused` 4, and `full` 10. A simple targeted command costs 1 unit, a recognized broad suite costs 3, and a recognized security, coverage, end-to-end, audit, or benchmark command costs 5. These are ceilings, not targets. Select the smallest final batch that proves `done_when`.

Run the listed `done_when` checks together once after implementation. Do not revalidate every contract item during implementation. Routine builds, app runs, and narrow feedback needed to implement may occur, but do not turn them into a shadow final suite. Run recognized broad checks only through the final budgeted batch. Use `intermediate_gate` only when a later action depends on an irreversible migration, destructive operation, deployment, paid external call, or similarly unrecoverable boundary. Omit it for routine edits, builds, and reversible implementation choices.

## Show both views and ask once

1. Stage the exact JSON with `click-gate stage '<Execution Contract JSON>'`.
2. Show the compact developer contract.
3. Show its faithful plain-language explanation in the user's language, including the verification scale.
4. Ask one compact question: approve, change the proposed contract, simplify the explanation, or cancel.
5. Stop without mutating project files.

The original request is not approval of an unseen contract. Before approval, a requested change replaces the staged proposal and both views are shown again. The easy explanation must not add or hide material meaning.

## Implement the approved contract in one shot

After explicit approval:

1. In Manual mode, run `click-gate arm` in the approval turn. In Always ON mode this is optional.
2. Run `click-gate pass '<Execution Contract JSON>'` with the exact staged JSON.
3. Implement continuously inside the approved semantic boundary without creating a new plan, restaging the contract, or reopening repository-wide inventory exploration.
4. Submit the smallest sufficient final batch as `click-gate verify '{"commands":["<one shell command per entry>"]}'`. Do not chain checks inside one entry to hide their cost.
5. Report results and material implementation choices.

The Hook executes the accepted batch and records its real exit code. After success, do not run another verification batch unless a later in-scope mutation makes the result stale; then re-run the same batch. After failure, fix the in-scope cause and retry. One unchanged retry is available for a transient failure, after which a code mutation is required. Do not bypass the budget with a renamed wrapper or a direct broad-suite command.

Do not create a replacement contract or request reapproval for an in-scope technical choice. MCP tools, external services, dependencies, graders, architecture tactics, files, and implementation order may change when necessary to deliver the approved result while preserving its boundary and must-hold conditions. The approved contract remains unchanged because it already grants that implementation freedom.

After approval, reuse successful read/search evidence. If more evidence is needed, issue a narrower or materially different query. The Hook blocks an identical successful Bash observation until an in-scope mutation makes it stale, allows one unchanged retry after a failed or oversized observation, rejects repository-wide inventory rescans, and rejects matched plan-tool calls. Do not evade those guards with renamed wrappers or prose-only duplicate plans.

Stop only when completion needs authority the user has not granted, an irreversible or paid external action not covered by approval, or a change to the approved outcome, user-visible behavior, boundary, must-hold condition, or verification commitment. Report the blocker; do not silently widen the work or substitute a new mid-run contract.

## Prevent overdesign by evidence, not bans

Choose the smallest design that satisfies every invariant. No component category is forbidden. A new dependency, service, queue, store, MCP, grader, abstraction, or operational component is valid when it is a proportionate way to complete the approved work. Prefer existing structure when it is equally capable; do not add speculative architecture for hypothetical scale, teams, or reuse.

The Hook validates contract shape, mutation ordering, exact staged-versus-passed equality, recognized shell observation loops, and visible verification breadth. Its review guard covers matched shell reads and searches, not every possible connector read. It cannot see hidden reasoning, prose-only plans, connector reads outside its matcher, design truth, semantic implementation fidelity, or authentic human approval. If Hook enforcement is unavailable, preserve the same ordering at instruction level and disclose that fact.

## Communicate plainly

Use the user's language. Lead with the resulting behavior, explain important safeguards and the verification cost, then ask the single approval question. Avoid architecture slogans and serial option menus.
