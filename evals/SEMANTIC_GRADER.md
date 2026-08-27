# Semantic grader

Judge one candidate without seeing the condition label or another candidate's result. Use only the request, pinned repository evidence, candidate diff, automated-check output, and final message.

Return JSON matching `semantic-judgment.schema.json`.

Apply these rules in order:

1. Required observable behavior and material invariants are a hard correctness gate. Record every miss with concrete evidence.
2. Mark activation `correct` only when Build Brief ran after explicit plugin selection or `$build-brief` invocation, and stayed out of every uninvoked request. A question about the plugin is not an invocation.
3. Mark `unwanted_block` when an unarmed adaptive task was prevented from proceeding. An advisory message alone is not a block.
4. For each material addition, require all four forms of evidence: a current requirement or repository fact, why existing structure is insufficient, the material failure prevented, and focused proof. If any is absent, list it as unjustified.
5. Do not penalize necessary concurrency, safety, compatibility, or failure handling merely because it adds code. Penalize only unnecessary design delta.
6. Mark proof complete only when the candidate supplies focused passing evidence for the changed behavior, not just a claim.

Material design element types are limited to the schema enum. Cite a path, diff hunk, test output, or exact candidate statement in every finding. Do not infer hypothetical future needs.
