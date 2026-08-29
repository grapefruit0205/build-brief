# Execution Contract Presentation

Use this format whenever an active Click contract is staged, shown, approved, implemented, or handed off, whether activation came from Always ON or an explicit Manual invocation. Keep every field proportional to the work.

## Canonical contract object

Stage one JSON object with exactly these fields:

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

Declare each source once in `evidence` with exactly `id`, `kind`, and `description`. IDs start with a letter, use at most 32 letters, digits, underscores, or hyphens, and are unique. `kind` is one of `argv`, `browser`, `hosted`, `manual`, or `existing`. Each `done_when` object has exactly one non-empty `condition` and one `primary_evidence` id that resolves to the registry. Every source must be referenced, while one id may be reused by several conditions. Do not add a second source for the same condition merely to repeat proof through another tool or surface. Bind every `argv` check to its declared source with `evidence_id` in the final verification batch; even at one targeted unit per argv source, that batch must fit the chosen scale before staging. Use at most one `browser` source and reference that id from every condition covered by its metered representative session. After the last relevant mutation, explicitly finalize a successful Browser source or attest one collected hosted, manual, or existing source with the evidence-completion capability. The Hook independently executes argv checks and observes its matched Browser path; other kinds remain explicit agent attestations rather than independently proven external events.

The Hook treats `condition`, `description`, and the other contract prose as opaque text. Enforcement follows typed fields, ids, references, verification scale, and explicit capability argv; natural-language keywords do not grant permissions or change budgets. Exact executable names, options, tool names, and explicit Click directives remain protocol syntax rather than semantic prose.

Only when material, add `build.semantics` as a non-empty list for state, failure, security, concurrency, migration, or compatibility meaning; `build.order` as a non-empty list for a real sequencing constraint; or `verification.intermediate_gate` as a non-empty string for one irreversible boundary. Otherwise omit them. Do not add unsupported fields.

## One semantic contract, not many checkpoints

Show the authoritative fields top-down: outcome and boundary; must-hold conditions; the compact build approach and any material semantics or order; then verification.

The contract fixes the result, boundary, must-hold conditions, material behavior, and verification commitment. Its selected scale also activates the Hook's automatic argv-batch ceiling; no extra budget field or second approval is added. It does not freeze every library, tool, file, or low-level tactic. Necessary in-scope dependencies, MCP tools, external services, graders, and implementation choices are authorized by approval unless the contract explicitly excludes them.

Do not split the build approach into phases, steps, tasks, or another mirrored plan. The contract exists to approve the result and its boundary, not to make the user review several versions of the same implementation description.

## Easy-language translation

Keep `plain_language` inside the canonical digest-bound object, but do not print the same explanation twice. Show the developer fields from `outcome` through `verification`, then render the exact stored `plain_language` value once as the easy-language view in the user's language. Together the two views expose every approved field exactly once. Explain the result, safeguards, unchanged behavior, broad implementation route, verification cost, and whether an exceptional intermediate gate exists without adding or hiding material meaning.

## Single approval

Run `click-gate stage '<Execution Contract JSON>'` once. The Hook validates and binds the canonical contract digest, creates a fresh opaque lifecycle handle, and returns:

```text
CLICK_CONTRACT_ID=ctr_<32 lowercase hex characters>
```

`contract_id` is not a contract field and does not replace the stored digest. Show the emitted id with the developer contract and its plain-language view, then end with one compact question equivalent to:

> Do you approve contract `ctr_...` and its verification scale? If approved, I will implement it in one shot and run the completion checks once.

Stop without mutation. The original request is not approval of an unseen contract. Staging records `staged_turn_id`; the Hook rejects pass and a replacement stage in that same `UserPromptSubmit` turn. A revised proposal staged after another user response receives a new id, invalidating the old handle.

Only after a later user turn explicitly approves the shown proposal, run `click-gate pass ctr_<32hex>`. Pass only the exact emitted id—never resend or reconstruct the contract JSON. The Hook matches the id to the staged digest, records `approved_turn_id`, and preserves the derived verification state. An approved but incomplete contract reuses the same id when implementation resumes in a later turn. Turn separation proves that another user response occurred; the Skill still must interpret that response faithfully because the Hook does not semantically classify approval words.
