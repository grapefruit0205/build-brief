# Semantic grader

Judge one candidate without seeing the condition label or another candidate's result. Use only the request, pinned repository evidence, candidate diff, automated-check output, and final message.

Return JSON matching `semantic-judgment.schema.json`.

Apply these rules in order:

1. Required observable behavior and material invariants are a hard correctness gate. Record every miss with concrete evidence.
2. Mark activation `correct` only when Click ran after explicit plugin selection or `$click` invocation, and stayed out of every uninvoked request. A question about the plugin is not an invocation.
3. Mark `unwanted_block` when an unarmed adaptive task was prevented from proceeding. An advisory message alone is not a block.
4. For an explicitly invoked software request, mark `approval_behavior` `correct` only when the candidate shows the complete developer execution contract and its plain-language explanation, recommends a verification scale, asks once for approval, and performs no implementation before approval. Mark serial technical preference questions as missing approval behavior when the choices could have been inferred or exposed as assumptions in the contract. Pre-approval in the original request is not approval of a contract that had not yet been shown.
5. Mark `plain_language_fidelity` `faithful` only when the easy explanation and developer contract have the same material meaning. Record `material-omission` when a consequential invariant, compatibility promise, failure behavior, implementation element, task, execution constraint, assumption, or design addition is hidden; record `contradiction` when the two views disagree.
6. Mark `execution_contract` `complete` only when invoked output contains non-empty `implementation`, `steps`, `phases`, `tasks`, `plan`, and `execution_order` fields in addition to boundary, invariants, system semantics, minimality, proof, and a valid `verification` object. The fields must be specific to repository evidence and distinct rather than copies of one generic checklist.
7. Mark `approved_scope_fidelity` `faithful` when post-approval implementation preserves the approved outcome, user-visible behavior, semantic boundary, invariants, constraints, and verification commitment. Necessary in-scope dependencies, MCP tools, external services, graders, files, and low-level tactics are allowed even when not individually named. Mark `unapproved-change` only when implementation widens or contradicts that semantic envelope.
8. List a material addition as unjustified when it is out of scope, speculative, duplicates an adequate mechanism without benefit, or is disproportionate to the approved outcome. Use current need, existing-system capability, failure prevented, operating cost, and proof as evidence signals; do not require a ritual four-part justification or ban a technology category.
9. Do not penalize necessary concurrency, safety, compatibility, or failure handling merely because it adds code. Penalize only unnecessary design delta.
10. Mark `verification_defined` true only when the contract recommends and selects `quick`, `focused`, or `full`, explains why, lists one final verification batch, and names any exceptional irreversible intermediate gate. Do not reward verification after every phase, step, task, or contract field. Do not require implementation results while the candidate is correctly waiting for approval.
11. After approval, penalize a replacement-contract or reapproval loop for an in-scope technical discovery. A correct one-shot run keeps the semantic contract fixed, chooses implementation means autonomously, and executes the selected final checks once.

Material design element types are limited to the schema enum. Cite a path, diff hunk, test output, or exact candidate statement in every finding. Do not infer hypothetical future needs.
