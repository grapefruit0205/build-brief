# Structured Capability Protocol

Use protocol version `1` whenever Click routes inspection, implementation commands, managed local services, or final verification through Bash. Every executable and argument is a separate JSON string. The Hook executes accepted argv arrays with `shell=False` in a new POSIX session or Windows process group; never hide a shell, pipeline, redirect, command substitution, or background job inside an entry.

## Inspection

Use before approval for an ambiguous but read-only command, and during approved implementation or `click-gate review` for tracked evidence:

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
```

Every command must match the Hook's read-only argv policy. One request may contain up to eight commands, which run serially and stop on the first failure. Git inspection uses subcommand-specific positive option policies rather than a generic subcommand allowlist plus dangerous-option blacklist; `git grep` and `git cat-file` are not currently accepted. Global pagination and caller-supplied config overrides such as `-p`, `--paginate`, `-c`, and `--config-env` are rejected. Arbitrary `--format` and `--pretty` output, signature-rendering options, and `git status -v/-vv` are also excluded. Accepted Git reads run through a dedicated executor that strips inherited `GIT_*` variables, ignores system/global Git config, forces a safe default log format with signature display disabled, uses `--no-pager` and `--no-optional-locks`, disables fsmonitor and external diff, and adds `--no-ext-diff` plus `--no-textconv` to supported diff-rendering commands. The Hook rejects shell interpreters and write-capable options. In active review and implementation it stores only a request digest and result metadata, applies the existing output cap and retry policy, and detects repository-wide inventory from the validated argv.

Experimental SSH inspection accepts only the same bounded Git policy further narrowed to `status`, `rev-parse HEAD`, `merge-base`, and `remote get-url`. It accepts no caller-supplied SSH options, assumes the remote login shell implements POSIX quoting, requires an already-known host key, disables interactive password flows, host-key updates, forwarding, local commands, and TTY allocation, and uses a 10-second connection timeout plus bounded keepalives. Unknown hosts, non-POSIX remote shells, unreachable hosts, and unsupported SSH implementations fail closed. This convenience is not a general remote-command capability or a security sandbox.

Recognized simple Bash reads remain compatible: the Hook converts safe direct syntax into the same internal argv request. It accepts direct `&&` sequencing only when every segment is independently read-only; it rejects pipelines and other shell control because their behavior is not represented by the protocol. Use explicit `inspect` whenever a legitimate read is not recognized.

## Mutation

After the exact contract is approved, use this for an implementation command that may write files or generated state:

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

Submit one final batch with a cost class for each argv check:

```text
click-gate verify '{"version":1,"checks":[{"argv":["python3","-m","unittest","discover","-s","tests","-q"],"class":"broad"},{"argv":["git","diff","--check"],"class":"targeted"}]}'
```

Classes are `targeted` (1 unit), `broad` (3), and `deep` (5). The Hook infers runner kind and actual target scope from each recognized argv and automatically raises a lower submitted value before charging the batch. Filters, multiple targets, directories, and suites are not treated as one cheap target. Approval of `quick`, `focused`, or `full` still provides ceilings of 1, 4, or 10 units. Legacy shell-string `commands` batches are rejected with a migration message.

Python checks must use an explicit supported pytest, unittest, or coverage module runner; Windows `py -3 -m ...` and `uv run pytest` are recognized. Python `-c` and direct Python scripts are not verification capabilities. Exact-file `node --check` and `node --test` are targeted; project-wide `node --test` is broad, while Node eval/print forms are not verification. In a Git worktree, the runner compares tracked and pre-existing non-ignored untracked content before and after the batch. A protected-content change fails stale and increments the mutation revision. Every new non-ignored untracked path created during the batch also fails stale and advances the mutation revision; source or configuration classification affects only the clarity of the message, not whether the workspace changed. Expected generated artifacts should be ignored or created during the approved mutation phase. Git-ignored paths and non-Git worktrees are outside this content snapshot.

## Browser primary evidence

Browser MCP calls are not a JSON capability, but the Hook observes the canonical `mcp__node_repl__js` tool on `PreToolUse` and `PostToolUse`. During an approved contract it permits that tool only when `verification.evidence` contains one source with `kind: "browser"` and at least one `done_when.primary_evidence` references its id. One assigned representative session receives at most three serial calls and 90 seconds of measured tool time. A single timeout above 30 seconds or an obvious wait above five seconds is rejected. A mutation resets the Browser ledger, a successful Browser result is required for a Browser-assigned contract to complete, and current-revision completion rejects replay. This boundary prevents the measured Browser shadow-verification pattern without claiming semantic understanding of other connectors.

## Enforcement boundary

This protocol removes shell-string classification from accepted capability execution and makes supported argv behavior deterministic. Minimum-class inference closes simple cost underdeclaration but cannot measure work concealed inside an allowed program. Direct process-control names are blocked and child groups are isolated, but an allowed custom program can still target unrelated processes explicitly or conceal other work internally. The protocol does not cover hosted tools, specialized paths that opt out of hooks, hidden reasoning, semantic boundary correctness, or arbitrary custom code executed by an allowed program. Click remains a workflow guardrail, not an operating-system sandbox.
