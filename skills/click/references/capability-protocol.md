# Structured Capability Protocol

Use protocol version `1` whenever Click routes inspection, implementation commands, or final verification through Bash. Every executable and argument is a separate JSON string. The Hook executes accepted argv arrays with `shell=False`; never hide a shell, pipeline, redirect, command substitution, or background job inside an entry.

## Inspection

Use before approval for an ambiguous but read-only command, and during approved implementation or `click-gate review` for tracked evidence:

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
```

Every command must match the Hook's read-only argv policy. One request may contain up to eight commands, which run serially and stop on the first failure. The Hook rejects shell interpreters and write-capable options. In active review and implementation it stores only a request digest and result metadata, applies the existing output cap and retry policy, and detects repository-wide inventory from the validated argv.

Recognized simple Bash reads remain compatible: the Hook converts safe direct syntax into the same internal argv request. It accepts direct `&&` sequencing only when every segment is independently read-only; it rejects pipelines and other shell control because their behavior is not represented by the protocol. Use explicit `inspect` whenever a legitimate read is not recognized.

## Mutation

After the exact contract is approved, use this for an implementation command that may write files or generated state:

```text
click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'
```

The Hook requires approved state, rejects shell interpreters, issues a one-use runner token, increments the mutation revision, and invalidates stale observations or verification. A runner that never starts expires instead of leaving the contract permanently blocked. Continue to use `apply_patch`, `Edit`, or `Write` directly for ordinary file edits; their canonical tool names already make mutation intent unambiguous.

## Verification

Submit one final batch with a cost class for each argv check:

```text
click-gate verify '{"version":1,"checks":[{"argv":["python3","-m","unittest","discover","-s","tests","-q"],"class":"broad"},{"argv":["git","diff","--check"],"class":"targeted"}]}'
```

Classes are `targeted` (1 unit), `broad` (3), and `deep` (5). The Hook infers runner kind and actual target scope from each recognized argv and automatically raises a lower submitted value before charging the batch. Filters, multiple targets, directories, and suites are not treated as one cheap target. Approval of `quick`, `focused`, or `full` still provides ceilings of 1, 4, or 10 units. Legacy shell-string `commands` batches are rejected with a migration message.

Python checks must use an explicit supported pytest, unittest, or coverage module runner; Windows `py -3 -m ...` and `uv run pytest` are recognized. Python `-c` and direct Python scripts are not verification capabilities. In a Git worktree, the runner compares tracked and pre-existing non-ignored untracked content before and after the batch. A protected-content change fails stale and increments the mutation revision. Every new non-ignored path is reported; an obvious new source, application, library, configuration, or migration path also fails stale, while a generic report artifact only warns. Git-ignored paths and non-Git worktrees are outside this content snapshot.

## Enforcement boundary

This protocol removes shell-string classification from accepted capability execution and makes supported argv behavior deterministic. Minimum-class inference closes simple cost underdeclaration but cannot measure work concealed inside an allowed program. It does not cover hosted tools, specialized paths that opt out of hooks, hidden reasoning, semantic boundary correctness, or arbitrary custom code executed by an allowed program. Click remains a workflow guardrail, not an operating-system sandbox.
