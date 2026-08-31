---
name: click
description: Compile repository-aware software intent into one approval-bound execution contract, explain it plainly, then implement it in one shot with anti-loop guards and an automatically enforced budget for observable local and Browser verification. Use when the user explicitly selects Click, or when Hook context says Click Always ON is enabled and the request will change software; use its read-only review guard for code review in Always ON mode. Do not use for questions, explanations, or simple inspection.
---

# Click

Translate the user's intent and current repository evidence into one compact semantic execution contract. Click is an approval boundary for the result, scope, invariants, and verification commitment—not a fixed architecture catalog or a second planning system.

## Route by the active mode

Follow [operating modes](references/modes.md) whenever selecting, activating, applying, reviewing, resuming, bypassing, or cancelling Click.

- In **Always ON**, use the contract workflow for software creation, modification, deletion, refactoring, and repair without requiring a mention.
- In **Manual**, activate only when the user selects `@Click` or invokes `$click`, then run `click-gate arm` before staging.
- When unset, leave questions, explanations, review, and simple inspection alone. Before the first software mutation, ask once for Always ON or Manual and record the answer with the documented default command.
- For code-review-only work in Always ON, run `click-gate review`, remain read-only, reuse evidence, and report findings without a build contract. A request that also asks for fixes uses the contract workflow.

Do not treat a question about Click as a mutation. Bypass and cancel require the exact user-authorized first-line forms in the modes reference; never infer them from ordinary prose.

## Compile the smallest faithful contract

Treat the user's requested result, visible behavior, scope, constraints, and authority as primary. A contract-only or handoff request does not authorize implementation. Inspect from the narrowest relevant repository entry point and widen only while consequential behavior is unresolved. Do not treat an existing system as a blank slate or include unrelated cleanup. Resolve ordinary technical choices from repository evidence instead of asking serial preference questions; ask before staging only when missing authority makes every safe faithful contract impossible. Expose other consequential assumptions or product choices in the one contract review.

For broad or cross-boundary work, read the [translation guide](references/translation-guide.md). Before every stage, read the canonical [contract format and approval lifecycle](references/directive-format.md) and [verification profiles](references/verification-profiles.md). Those references own the exact schema, optional-field rules, verification scale, structured evidence registry, and Browser limits; do not restate them as parallel sections.

Keep the contract proportional. Prefer an existing capable structure and add no speculative component. The contract fixes the approved semantic boundary while leaving necessary in-scope libraries, files, tools, dependencies, and low-level tactics open. Give every completion condition one cheapest sufficient primary evidence source, allow one source to cover several conditions, and avoid duplicate proof.

## Stage once and approve by id

1. Run `click-gate stage '<Execution Contract JSON>'` once and capture the emitted `CLICK_CONTRACT_ID=ctr_<32hex>`.
2. Show the compact developer fields (`outcome` through `verification`), then render the exact digest-bound `plain_language` value once as the separate easy-language view in the user's language; show the verification scale and that exact `contract_id` with them.
3. Ask one compact approval/change/cancel question, then stop without mutating project files.

The original request is not approval of an unseen proposal. A revision after another user response must be staged and shown again and receives a new id.

Only in a later turn whose user response explicitly approves the shown proposal, arm if Manual mode requires it and run `click-gate pass ctr_<32hex>` with the emitted id. Never resend or reconstruct the contract JSON in the approval turn. The Hook proves turn separation and binds the id to the staged digest; the Skill remains responsible for interpreting whether the user's words actually grant approval.

## Execute the approved boundary once

Before implementation, read the [anti-loop policy](references/anti-loop-policy.md) and [structured capability protocol](references/capability-protocol.md). Prefer focused follow-up after broad repository context; this is non-blocking strategy guidance, not contract authority. Implement continuously without a replacement plan or contract. Use their canonical inspect, mutate, managed-service, and verify forms rather than duplicating command details here.

Collect each assigned source once after the last mutation that can invalidate it. Reuse current successful evidence, keep Browser or hosted work out of a shadow verification suite, and stop verification when every completion condition has current evidence. Treat repeated-observation and ordinary argv-retry notices as non-authoritative guidance, not permission failures; active runner conflicts and verification-time repository mutation remain hard. Stop any managed service before declaring completion. A failed or stale source may be repaired or replaced under the documented retry rules; it is not a reason to accumulate another proof path.

Do not request reapproval for an in-scope technical choice. Stop only when completion needs missing authority, an uncovered irreversible or paid external action, or a change to the approved outcome, visible behavior, boundary, invariant, or verification commitment. Otherwise finish in one shot and report the result and completion evidence.

The Hook enforces observable contract shape, id/digest binding, turn order, supported tool paths, and verification budgets. It cannot prove semantic approval, hidden reasoning, unmatched connector behavior, architecture truth, or implementation fidelity. If Hook enforcement is unavailable, preserve the same ordering and disclose that limitation.
