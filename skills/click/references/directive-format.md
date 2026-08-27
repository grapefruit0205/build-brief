# Execution Contract Presentation

Use this format whenever an explicitly invoked Click contract is staged, shown, approved, implemented, or handed off. Keep every field proportional to the work.

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
    "done_when": ["observable completion check in the one final batch"]
  },
  "plain_language": "Faithful easy explanation of the compact contract and verification scale."
}
```

`outcome`, `boundary.in_scope`, `must_hold`, `build.approach`, `verification.scale`, `verification.done_when`, and `plain_language` are required. `boundary.out_of_scope` is required but may be empty when nothing material needs exclusion. `verification.scale` must be `quick`, `focused`, or `full`.

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

The original request is not approval of an unseen contract. Before approval, the user may replace the proposal. After approval, pass the exact staged JSON and keep the contract fixed while making any necessary in-scope technical choices.
