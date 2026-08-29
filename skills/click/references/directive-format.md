# Execution Contract Presentation

Use this format whenever an active Click contract is staged, shown, approved, implemented, or handed off, whether activation came from Always ON or an explicit Manual invocation. Keep every field proportional to the work.

## Canonical contract object

Stage and pass one JSON object with exactly these fields:

```json
{
  "outcome": "concrete result and user-visible behavior",
  "boundary": {
    "in_scope": ["approved behavior or system boundary"],
    "out_of_scope": ["explicitly unchanged behavior or excluded work"]
  },
  "must_hold": ["observable requirement or compatibility promise that must remain true"],
  "build": {
    "approach": ["smallest repository-aware implementation route"]
  },
  "verification": {
    "scale": "focused",
    "evidence": [
      {
        "id": "E1",
        "kind": "argv",
        "description": "one cheapest sufficient source"
      }
    ],
    "done_when": [
      {
        "condition": "observable completion condition",
        "primary_evidence": "E1"
      }
    ]
  },
  "plain_language": "Faithful easy explanation of the compact contract and verification scale."
}
```

`outcome`, `boundary.in_scope`, `must_hold`, `build.approach`, `verification.scale`, `verification.evidence`, `verification.done_when`, and `plain_language` are required. `boundary.out_of_scope` is required but may be empty when nothing material needs exclusion. `verification.scale` must be `quick`, `focused`, or `full`.

Declare each source once in `evidence` with exactly `id`, `kind`, and `description`. IDs start with a letter, use at most 32 letters, digits, underscores, or hyphens, and are unique. `kind` is one of `argv`, `browser`, `hosted`, `manual`, or `existing`. Each `done_when` object has exactly one non-empty `condition` and one `primary_evidence` id that resolves to the registry. Every source must be referenced, while one id may be reused by several conditions. Do not add a second source for the same condition merely to repeat proof through another tool or surface. Put `argv` sources in the final verification batch. Use at most one `browser` source and reference that id from every condition covered by its metered representative session. Collect other hosted, manual, or existing sources once after the last relevant mutation and reuse them at handoff.

The Hook treats `condition`, `description`, and the other contract prose as opaque text. Enforcement follows typed fields, ids, references, verification scale, and explicit capability argv; natural-language keywords do not grant permissions or change budgets. Exact executable names, options, tool names, and explicit Click directives remain protocol syntax rather than semantic prose.

Only when material, add `build.semantics` as a non-empty list for state, failure, security, concurrency, migration, or compatibility meaning; `build.order` as a non-empty list for a real sequencing constraint; or `verification.intermediate_gate` as a non-empty string for one irreversible boundary. Otherwise omit them. Do not add unsupported fields.

## One semantic contract, not many checkpoints

Show the authoritative fields top-down: outcome and boundary; must-hold conditions; the compact build approach and any material semantics or order; then verification.

The contract fixes the result, boundary, must-hold conditions, material behavior, and verification commitment. Its selected scale also activates the Hook's automatic final-batch ceiling; no extra budget field or second approval is added. It does not freeze every library, tool, file, or low-level tactic. Necessary in-scope dependencies, MCP tools, external services, graders, and implementation choices are authorized by approval unless the contract explicitly excludes them.

Do not split the build approach into phases, steps, tasks, or another mirrored plan. The contract exists to approve the result and its boundary, not to make the user review several versions of the same implementation description.

## Easy-language translation

After the developer contract, show `plain_language` in the user's language. Explain the result, safeguards, unchanged behavior, broad implementation route, verification cost, and whether an exceptional intermediate gate exists. Do not add or hide material meaning.

## Single approval

End with one compact question equivalent to:

> Do you approve this execution contract and its verification scale? If approved, I will implement it in one shot and run the completion checks once.

The original request is not approval of an unseen contract. Staging records `staged_turn_id`; the Hook rejects pass and a replacement stage in that same `UserPromptSubmit` turn. After a later user response, the user may revise the proposal and see it again, or approve it. Approval records `approved_turn_id`, passes the exact staged JSON, and authorizes one-shot implementation while necessary in-scope technical choices remain open. Turn separation proves that another user response occurred; the Skill still must interpret that response faithfully because the Hook does not semantically classify approval words.
