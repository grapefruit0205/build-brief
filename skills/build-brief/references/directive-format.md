# Design Contract Presentation

Use this format when showing an explicitly invoked Build Brief contract to a user or handing it to another person or agent. Keep both views proportional to the work.

## Plain-language explanation

Explain the contract in the user's language without requiring software-design vocabulary. State what the software will do, why the important safeguards matter, what remains unchanged, and any material failure behavior, tradeoff, or new system element being approved.

This is a faithful view of the developer contract. It must not add a promise or decision absent from the contract, and it must not hide a material invariant, compatibility promise, failure behavior, assumption, or justified design addition. If the user asks for an easier explanation, simplify wording and add a concrete example without changing the contract.

## Developer Design Contract

Present the authoritative design obligations without turning them into an execution plan:

- **Intent and boundary:** the requested outcome and the existing component, data owner, or external contract that owns it.
- **Invariants:** the observable behavior and facts that must remain true.
- **System semantics:** the relevant responsibilities, state, ownership, contracts, flow, timing, ordering, concurrency, consistency, failure, security, compatibility, migration, and operational meaning.
- **Minimum sufficient design:** what existing structure is reused and why each material addition is necessary.
- **Proof:** acceptance criteria and focused evidence that would show the invariants hold.
- **Visible assumptions:** only consequential assumptions that the repository and request cannot settle.

Do not output phases, numbered implementation steps, task lists, work breakdowns, or execution order. Those belong to the ordinary coding workflow after approval.

## Approval request

For a build or change request, ask one compact question after both views:

> Does this explanation match your intent, and do you approve the developer Design Contract for implementation? You can approve, request a design revision, ask for a simpler explanation, or cancel.

Approval applies to the developer Design Contract. The plain-language explanation exists so the user can understand that same contract. A design revision requires regenerating both views; an explanation-only simplification keeps the developer contract unchanged. Either case returns to approval.

After approval, hand the contract to the ordinary coding workflow. Do not append a Build Brief task plan.
