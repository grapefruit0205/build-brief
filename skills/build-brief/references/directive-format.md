# Execution Contract Presentation

Use this format whenever an explicitly invoked Build Brief contract will be staged, shown, approved, implemented, or handed off. Keep every field proportional to the work.

## Canonical contract object

Stage and later pass one JSON object with exactly these fields:

```json
{
  "boundary": "existing owner of the behavior",
  "invariants": ["observable requirement that must remain true"],
  "system_semantics": ["material state, contract, ordering, failure, or compatibility meaning"],
  "plan": ["goal, scope, non-goal, and top-down approach"],
  "implementation": ["concrete design mapped to current boundaries"],
  "phases": ["proportional implementation checkpoint"],
  "steps": ["ordered change within a phase"],
  "tasks": ["concrete approved code, test, configuration, schema, or documentation unit"],
  "execution_order": ["dependency or safe sequencing constraint"],
  "minimality": ["existing structure reused and evidence for each material addition"],
  "proof": ["acceptance criterion or focused verification"],
  "plain_language": "Faithful easy explanation of the complete contract."
}
```

Every list must contain at least one non-empty string. Do not add unsupported top-level fields. Keep vocabulary open-ended inside the fields so the design language can fit the actual system.

Do not duplicate one generic checklist across `plan`, `implementation`, `phases`, `steps`, `tasks`, and `execution_order`:

- `plan` fixes approved scope and top-down direction;
- `implementation` maps design decisions onto the current system;
- `phases` groups the work into meaningful checkpoints;
- `steps` orders the changes inside those checkpoints;
- `tasks` names concrete approved deliverables;
- `execution_order` records dependency and safety constraints across the work.

## Developer execution contract

Show the authoritative developer fields first, in top-down order:

1. plan and boundary;
2. invariants and system semantics;
3. implementation;
4. phases, steps, tasks, and execution order;
5. minimality and proof.

This contract is the approval target. It must be detailed enough to prevent material implementation guesses without expanding into unrelated architecture.

## Easy-language translation

After the developer contract, show `plain_language` in the user's language. Explain what will change, what will remain unchanged, why the important safeguards matter, how the work will proceed, and what proof will be run.

The explanation is a faithful projection, not a second design. It must not add a promise or decision absent from the developer contract or hide an invariant, compatibility promise, failure behavior, implementation element, approved task, or execution constraint.

## Approval request

End with one compact question equivalent to:

> Do you approve this execution contract? If approved, I will implement only this contract. You can request a revision, ask for a simpler explanation, or cancel.

Approval covers the staged developer contract and its faithful explanation. The original build request is not approval. A material contract change requires staging the revision, showing both views again, and receiving new approval before more mutation.
