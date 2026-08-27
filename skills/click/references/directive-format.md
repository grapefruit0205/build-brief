# Execution Contract Presentation

Use this format whenever an explicitly invoked Click contract is staged, shown, approved, implemented, or handed off. Keep every field proportional to the work.

## Canonical contract object

Stage and pass one JSON object with exactly these fields:

```json
{
  "boundary": "owner and semantic limit of the approved outcome",
  "invariants": ["observable requirement that must remain true"],
  "system_semantics": ["material state, contract, ordering, failure, or compatibility meaning"],
  "plan": ["goal, scope, non-goal, and top-down approach"],
  "implementation": ["concrete design mapped to current boundaries"],
  "phases": ["proportional implementation grouping, not a review gate"],
  "steps": ["ordered change, not a mandatory verification point"],
  "tasks": ["concrete code, test, configuration, schema, or documentation unit"],
  "execution_order": ["dependency or safe sequencing constraint"],
  "minimality": ["existing structure reused or reason for a material addition"],
  "proof": ["observable acceptance criterion"],
  "verification": {
    "recommended": "focused",
    "selected": "focused",
    "rationale": "why this scale is proportionate to present risk",
    "final_checks": ["one check in the final verification batch"],
    "intermediate_gate": "none, or the one irreversible boundary that must be checked before continuing"
  },
  "plain_language": "Faithful easy explanation of the complete contract and selected verification scale."
}
```

Every list must contain at least one non-empty string. `recommended` and `selected` must be `quick`, `focused`, or `full`. Do not add unsupported top-level or verification fields.

## One semantic contract, not many checkpoints

Show the authoritative fields top-down: plan and boundary; invariants and system semantics; implementation; phases, steps, tasks, and execution order; minimality; proof and verification.

The contract fixes the result, semantic boundary, invariants, material behavior, constraints, and verification commitment. It does not freeze every library, tool, file, or low-level tactic. Necessary in-scope dependencies, MCP tools, external services, graders, and implementation choices are authorized by approval unless the contract explicitly excludes them.

`plan`, `implementation`, `phases`, `steps`, `tasks`, and `execution_order` must remain distinct, but their presence does not create separate approvals or tests. A one-file change may use one compact item in each field.

## Easy-language translation

After the developer contract, show `plain_language` in the user's language. Explain the result, safeguards, unchanged behavior, broad implementation route, selected verification cost, and whether an exceptional intermediate gate exists. Do not add or hide material meaning.

## Single approval

End with one compact question equivalent to:

> Do you approve this execution contract and its selected verification scale? If approved, I will implement it in one shot and run the final checks once.

The original request is not approval of an unseen contract. Before approval, the user may replace the proposal. After approval, pass the exact staged JSON and keep the contract fixed while making any necessary in-scope technical choices.
