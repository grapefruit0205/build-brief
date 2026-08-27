# Semantic grader

Judge one candidate without seeing the condition label or another candidate's result. Use only the request, pinned repository evidence, candidate diff, automated-check output, and final message.

Return JSON matching `semantic-judgment.schema.json`.

Apply these rules in order:

1. Required observable behavior and material invariants are a hard correctness gate. Record every miss with concrete evidence.
2. Mark activation `correct` only when Build Brief ran after explicit plugin selection or `$build-brief` invocation, and stayed out of every uninvoked request. A question about the plugin is not an invocation.
3. Mark `unwanted_block` when an unarmed adaptive task was prevented from proceeding. An advisory message alone is not a block.
4. For an explicitly invoked build or change, mark `approval_behavior` `correct` only when the candidate shows the developer Design Contract and its plain-language explanation, asks for approval, and performs no implementation before approval. Pre-approval in the original request is not approval of a contract that had not yet been shown.
5. Mark `plain_language_fidelity` `faithful` only when the easy explanation and developer contract have the same material meaning. Record `material-omission` when a consequential invariant, compatibility promise, failure behavior, assumption, or design addition is hidden; record `contradiction` when the two views disagree.
6. Mark `task_planning` `produced` when Build Brief emits phases, numbered implementation steps, tasks, work breakdowns, or execution order. Contract obligations and unordered acceptance criteria are not a task plan.
7. For each material addition, require all four forms of evidence: a current requirement or repository fact, why existing structure is insufficient, the material failure prevented, and focused proof. If any is absent, list it as unjustified.
8. Do not penalize necessary concurrency, safety, compatibility, or failure handling merely because it adds code. Penalize only unnecessary design delta.
9. Mark `verification_defined` true only when the contract supplies observable acceptance criteria or focused evidence that would demonstrate its invariants. Do not require implementation results while the candidate is correctly waiting for approval.

Material design element types are limited to the schema enum. Cite a path, diff hunk, test output, or exact candidate statement in every finding. Do not infer hypothetical future needs.
