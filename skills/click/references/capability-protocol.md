# Structured Capability Protocol

Use protocol version `1` for inspection, mutation, managed local services, and explicit non-argv evidence completion. Final argv verification uses version `2` because every check is bound to a declared `evidence_id`. Every executable and argument is a separate JSON string. The Hook executes accepted argv arrays with `shell=False` in a new POSIX session or Windows process group; never hide a shell, pipeline, redirect, command substitution, or background job inside an entry.

## Inspection

Use before approval for an ambiguous but read-only command, and during approved implementation or `click-gate review` for tracked evidence:

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
```

Every command must match the Hook's read-only argv policy. One request may contain up to eight commands, which run serially and stop on the first failure. Git inspection uses subcommand-specific positive option policies rather than a generic subcommand allowlist plus dangerous-option blacklist; `git grep` and `git cat-file` are not currently accepted. Global pagination and caller-supplied config overrides such as `-p`, `--paginate`, `-c`, and `--config-env` are rejected. Arbitrary `--format` and `--pretty` output, signature-rendering options, and `git status -v/-vv` are also excluded. Accepted Git reads run through a dedicated executor that strips inherited `GIT_*` variables, ignores system/global Git config, forces a safe default log format with signature display disabled, uses `--no-pager` and `--no-optional-locks`, disables fsmonitor and external diff, and adds `--no-ext-diff` plus `--no-textconv` to supported diff-rendering commands. The Hook rejects shell interpreters and write-capable options. In active review and implementation it stores only a request digest and result metadata, applies the existing output cap and retry policy, and detects repository-wide inventory from the validated argv.

Experimental SSH inspection accepts only the same bounded Git policy further narrowed to `status`, `rev-parse HEAD`, `merge-base`, and `remote get-url`. It accepts no caller-supplied SSH options, assumes the remote login shell implements POSIX quoting, requires an already-known host key, disables interactive password flows, host-key updates, forwarding, local commands, and TTY allocation, and uses a 10-second connection timeout plus bounded keepalives. Unknown hosts, non-POSIX remote shells, unreachable hosts, and unsupported SSH implementations fail closed. This convenience is not a general remote-command capability or a security sandbox.

Recognized simple Bash reads remain compatible: the Hook converts safe direct syntax into the same internal argv request. It accepts direct `&&` sequencing only when every segment is independently read-only; it rejects pipelines and other shell control because their behavior is not represented by the protocol. Use explicit `inspect` whenever a legitimate read is not recognized.

## Mutation

After a later approval turn passes the emitted `contract_id` for its digest-bound contract, use this for an implementation command that may write files or generated state:

```text
click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'
```

The Hook requires approved state, rejects shell interpreters and direct process-control executables such as `kill`, `pkill`, `killall`, `taskkill`, and `Stop-Process`, issues a one-use runner token, increments the mutation revision, and invalidates stale observations or verification. Every accepted subprocess starts in an isolated process group so group-directed signals from a child cannot reach the Codex parent group. A runner that never starts expires instead of leaving the contract permanently blocked. Continue to use `apply_patch`, `Edit`, or `Write` directly for ordinary file edits; their canonical tool names already make mutation intent unambiguous.

Recognizable long-running development servers are rejected here because a foreground server can hold the entire one-shot mutation open. Use the managed service capability instead.

## Managed local service

Start one recognizable local development server after approval and stop it when Browser or integration work is finished:

```text
click-gate service '{"version":1,"action":"start","argv":["python3","-m","http.server","4173","--bind","127.0.0.1"]}'
click-gate service '{"version":1,"action":"stop"}'
```

Only `start` and `stop` are accepted. `start` requires direct argv for a recognizable development server and counts as a mutation, so prior completion evidence becomes stale. `stop` omits `argv`. A detached Click supervisor retains the exact child handle, starts the child in its own process group, and terminates only that retained group. It responds to explicit stop and `SessionEnd`, applies bounded start/stop waits, and enforces a final two-hour lifetime ceiling. One managed service may be active per contract. This avoids exposing a general process-control capability to the agent.

## Verification

When argv sources are declared, submit one final batch with a cost class for each argv check:

```text
click-gate verify '{"version":2,"checks":[{"evidence_id":"E1","argv":["python3","-m","unittest","discover","-s","tests","-q"],"class":"broad"},{"evidence_id":"E2","argv":["git","diff","--check"],"class":"targeted"}]}'
```

Classes are `targeted` (1 unit), `broad` (3), and `deep` (5). `evidence_id` must resolve to a declared source whose kind is `argv`; every unresolved argv source must appear in the one batch, while several adjacent checks may share one id and all must pass to complete it. The Hook infers runner kind and actual target scope from each recognized argv and automatically raises a lower submitted value before charging the batch. Filters, multiple targets, directories, and suites are not treated as one cheap target. Approval of `quick`, `focused`, or `full` still provides ceilings of 1, 4, or 10 units. Protocol-v1 verification, a missing id, unknown or wrong-kind ids, and legacy shell-string `commands` batches are rejected with migration guidance.

Python checks must use an explicit supported pytest, unittest, or coverage module runner; Windows `py -3 -m ...` and `uv run pytest` are recognized. Python `-c` and direct Python scripts are not verification capabilities. Exact-file `node --check` and `node --test` are targeted; project-wide `node --test` is broad, while Node eval/print forms are not verification. In a Git worktree, the runner compares tracked and pre-existing non-ignored untracked content before and after the batch. A protected-content change fails stale, increments the mutation revision, and invalidates every evidence source. Every new non-ignored untracked path created during the batch also fails stale and advances the mutation revision; source or configuration classification affects only the clarity of the message, not whether the workspace changed. Expected generated artifacts should be ignored or created during the approved mutation phase. Git-ignored paths and non-Git worktrees are outside this content snapshot.

## Non-argv evidence completion

After collecting the assigned source, record it once:

```text
click-gate evidence '{"version":1,"evidence_id":"E-browser"}'
```

The id in this command must name a declared non-argv source. The Hook hashes the id before storing its typed per-revision state. It accepts `browser` only after a successful current-revision Browser observation and accepts `hosted`, `manual`, or `existing` as explicit agent attestations. It rejects unknown ids, duplicate current-revision completion, and every `argv` id. This makes each contract source visible to the state machine without pretending an unmatched hosted, manual, or existing event was independently proven.

## Browser primary evidence

Browser MCP calls are not an argv capability, but the Hook observes the canonical `mcp__node_repl__js` tool on `PreToolUse` and `PostToolUse`. During an approved contract it permits that tool only when `verification.evidence` contains one source with `kind: "browser"` and at least one `done_when.primary_evidence` references its id. The source description and condition prose are never searched for Browser keywords. One assigned representative session receives at most three serial calls and 90 seconds of measured tool time. A single timeout above 30 seconds or an obvious wait above five seconds is rejected. A successful call marks the source observed; the evidence-completion command finalizes it after the representative session. A mutation resets the Browser ledger, and current-revision completion rejects replay. This boundary prevents the measured Browser shadow-verification pattern without claiming semantic understanding of other connectors.

## Enforcement boundary

This protocol removes shell-string classification from accepted capability execution and makes supported argv behavior deterministic. Minimum-class inference closes simple cost underdeclaration but cannot measure work concealed inside an allowed program. Direct process-control names are blocked and child groups are isolated, but an allowed custom program can still target unrelated processes explicitly or conceal other work internally. The evidence ledger proves exact argv execution and matched Browser observation at the workflow level; hosted, manual, and existing completion remain declared attestations. The protocol does not cover unmatched hosted tools, specialized paths that opt out of hooks, hidden reasoning, semantic boundary correctness, or arbitrary custom code executed by an allowed program. Click remains a workflow guardrail, not an operating-system sandbox.
