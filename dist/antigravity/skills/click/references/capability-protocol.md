# Structured Capability Protocol

Use protocol version `1` for inspection, mutation, managed local services, and explicit non-argv evidence completion. Final argv verification uses version `2` because every check is bound to a declared `evidence_id`. Every executable and argument is a separate JSON string. The Hook executes accepted argv arrays with `shell=False` in a new POSIX session or Windows process group; never hide a shell, pipeline, redirect, command substitution, or background job inside an entry.

## Inspection

Use before approval for an ambiguous but read-only command, and during approved implementation or `click-gate review` for tracked evidence:

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
```

Every command must match the Hook's read-only argv policy. One request may contain up to eight commands, which run serially and stop on the first failure. The executable must be a bare name: names containing `/` or `\\`, Windows drive-prefixed forms such as `C:cat.exe`, and UNC forms are rejected. Immediately before execution, Click removes empty, relative, and repository-resolving PATH entries, rejects a candidate whose lexical path or resolved target is inside the nearest containing Git repository (or the current working directory outside Git), resolves the accepted program to an absolute real path, and executes that path with the sanitized PATH. Read children drop inherited `LD_*`, `DYLD_*`, `GCONV_PATH`, and `LOCPATH`. Recognized direct Bash reads are rewritten through this same runner even when no active contract or review ledger exists; they remain lightweight and untracked in that state, but the original shell no longer resolves their executable. Git inspection uses subcommand-specific positive option policies rather than a generic subcommand allowlist plus dangerous-option blacklist; `git grep` and `git cat-file` are not currently accepted. Global pagination and caller-supplied config overrides such as `-p`, `--paginate`, `-c`, and `--config-env` are rejected. Arbitrary `--format` and `--pretty` output, signature-rendering options, and `git status -v/-vv` are also excluded. Accepted Git reads run through a dedicated executor that additionally strips inherited `GIT_*` variables, ignores system/global Git config, forces a safe default log format with signature display disabled, uses `--no-pager` and `--no-optional-locks`, disables fsmonitor and external diff, and adds `--no-ext-diff` plus `--no-textconv` to supported diff-rendering commands. Local Git and SSH programs use the same absolute executable resolution. The Hook rejects shell interpreters and write-capable options. In active review and implementation it stores only a request digest and result metadata, applies the existing output cap, and detects repository-wide inventory from the validated argv. Before any tracked read executes, the runner atomically claims the managed state path, active status, current revision, request digest, one-use token, replay state, and freshness. An unclaimed startup reservation expires after 30 seconds; a claimed synchronous read has no elapsed-time release and continues to block mutation and final verification until its result is recorded or the user explicitly cancels. Tampered, unmanaged, stale, expired, cancelled, or replayed runners execute no read. A safe synchronous startup failure records failure and clears its claim. Broad classification, completed identical requests, and fixed failure counts are retained for advisory context only. A fresh repeat receives a new one-use token; an active same-digest reservation remains blocked so its exact token and result record cannot be replaced. All preceding runner claims, state and authority checks, mutation and verification interlocks, and operational limits remain unchanged.

Experimental SSH inspection accepts only the same bounded Git policy further narrowed to `status`, `rev-parse HEAD`, `merge-base`, and `remote get-url`. It accepts no caller-supplied SSH options, assumes the remote login shell implements POSIX quoting, requires an already-known host key, disables interactive password flows, host-key updates, forwarding, local commands, and TTY allocation, and uses a 10-second connection timeout plus bounded keepalives. Unknown hosts, non-POSIX remote shells, unreachable hosts, and unsupported SSH implementations fail closed. This convenience is not a general remote-command capability or a security sandbox.

Recognized simple Bash reads remain compatible: the Hook converts safe direct syntax into the same internal argv request. It accepts direct `&&` sequencing only when every segment is independently read-only; it rejects pipelines and other shell control because their behavior is not represented by the protocol. Use explicit `inspect` whenever a legitimate read is not recognized.

## Mutation

After a later approval turn passes the emitted `contract_id` for its digest-bound contract, use this for an implementation command that may write files or generated state:

```text
click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'
```

The Hook requires approved state, rejects shell interpreters and direct process-control executables such as `kill`, `pkill`, `killall`, `taskkill`, and `Stop-Process`, issues a one-use runner token, increments the mutation revision, and invalidates stale observations or verification. Before the requested process starts, the runner atomically claims the managed state path, approved status, exact request digest, one-use token, replay state, and expiry. A tampered, unmanaged, expired, or replayed request therefore executes no mutation command, and result recording accepts only a successfully claimed runner. Stateful rewritten commands carry the Hook-selected canonical `gate-state` root and canonical state path instead of trusting ambient state configuration. Every accepted subprocess starts in an isolated process group so group-directed signals from a child cannot reach the Codex parent group. A reservation that never starts may expire; once claimed, it remains active until the result is recorded or the user explicitly cancels the contract, because elapsed time alone cannot prove that the child stopped. Continue to use `apply_patch`, `Edit`, or `Write` directly for ordinary file edits; their canonical tool names already make mutation intent unambiguous.

Recognizable long-running development servers are rejected here because a foreground server can hold the entire one-shot mutation open. Use the managed service capability instead.

## Managed local service

Start one recognizable local development server after approval and stop it when Browser or integration work is finished:

```text
click-gate service '{"version":1,"action":"start","argv":["python3","-m","http.server","4173","--bind","127.0.0.1"]}'
click-gate service '{"version":1,"action":"stop"}'
```

Only `start` and `stop` are accepted. `start` requires direct argv for a recognizable development server and counts as a mutation, so prior completion evidence becomes stale. `stop` omits `argv`. Before either the start runner or its detached supervisor may spawn a process, it atomically claims the approved service id, request-plus-working-directory digest, and one-use token; replay, tampering, stale state, or cancellation before the corresponding claim therefore launches no additional server. A cancellation racing after a successful claim may briefly launch the child, which is then terminated when its state can no longer be recorded. The supervisor retains the exact child handle, starts the child in its own process group, and terminates only that retained group. It responds to explicit stop and `SessionEnd`, applies bounded start/stop waits, and enforces a final two-hour lifetime ceiling. One managed service may be active per contract. This avoids exposing a general process-control capability to the agent.

## Verification

When argv sources are declared, submit a nonempty subset of unresolved sources with a cost class for each argv check:

```text
click-gate verify '{"version":2,"checks":[{"evidence_id":"E1","argv":["python3","-m","unittest","discover","-s","tests","-q"],"class":"broad"},{"evidence_id":"E2","argv":["git","diff","--check"],"class":"targeted"}]}'
```

Classes are `targeted`, `broad`, and `deep`. They remain in protocol v2 for compatibility and are normalized deterministically, but neither the class nor its legacy unit value is a claim about cost, sufficiency, or evidence strength. `evidence_id` must resolve to a declared source whose kind is `argv`; any nonempty subset of unresolved argv sources may appear, while several adjacent checks may share one id and all must pass to complete it. The first accepted group for a source reserves its normalized check digest for the lifetime of the active contract, and later attempts for that source must match the reserved group. Profile and class values produce no numeric permission or advisory decision. Protocol-v1 verification, an empty request, a missing id, unknown or wrong-kind ids, and legacy shell-string `commands` batches are rejected with migration guidance.

Python checks must use an explicit supported pytest, unittest, or coverage module runner; Windows `py -3 -m ...` and `uv run pytest` are recognized. Python `-c` and direct Python scripts are not verification capabilities. Exact-file `node --check` and `node --test` are targeted; project-wide `node --test` is broad, while Node eval/print forms are not verification. Verification environment binding canonicalizes Hook-owned `PLUGIN_ROOT` alongside existing shell bookkeeping but continues to fingerprint project, user, PATH, and toolchain values. The prepared key/value HMAC records are protected by an aggregate runner-token binding. If a prepared value changes or disappears before the runner claims the batch, the runner projects current values onto the prepared key set, ignores runner-only additions, re-fingerprints the canonical environment, and rebinds the reserved environment digest without another approval. The exact resolved executable fingerprint remains fixed, so an executable change or malformed or tampered binding still fails closed. A successful receipt records the actual rebound environment digest. If runner admission otherwise fails before any check executes, only the exact digest/token-matched unclaimed reservation returns to `ready`; it records no evidence and consumes no test-failure retry. Claimed, stale, unavailable, tampered, and replayed state remains fail-closed. A claimed batch remains running until it records a result or the contract is explicitly cancelled; only an unclaimed reservation may expire into a retry.

The Hook skips a previously successful exact check in the same revision only when the receipt still matches the active contract, normalized check group, protected Git tree digest, canonical execution environment, resolved executable fingerprint, and current host coverage identity. An argv source may additionally opt into dependency-aware cross-revision reuse through its approval-bound `dependencies` declaration, a matching committed repository manifest entry, or both. The recomputed provider, relevant normalized entry, exact resolved path list, path-content digest, check group, contract, Git root, environment, executable, and host coverage identity must match. A stable `PostToolUse` event closes the approved mutation snapshot; a missing post receipt, pre-existing drift, or any change after that event disables reuse and runs the check. Reuse never occurs outside Git.

Host coverage identity is a compact receipt containing the canonical host, a deterministic digest of its registered pre/post tool surface, and the assurance `known-surfaces-only`. Verification preparation binds it to the one-use runner, the runner requires the registry to remain current before execution, and a successful argv source records it for later exact or dependency-aware reuse. Legacy evidence without this receipt remains readable but is rerun. This identity detects host or registry drift; it does not claim that a host emitted an event for a capability outside the registered surface, and it does not turn the Hook into an operating-system monitor.

The optional repository manifest is `.click/evidence-dependencies.json`:

```json
{
  "version": 1,
  "entries": [
    {
      "checks": [["python3", "-m", "pytest", "tests/auth"]],
      "paths": ["src/auth/", "tests/auth/", "pyproject.toml"]
    }
  ]
}
```

The current manifest must be a regular file identical to the committed `HEAD` blob. Each entry maps one exact adjacent argv group to deterministic patterns. Contract and manifest patterns are unioned when both exist. Cache identity uses the relevant entry rather than the whole manifest, so a committed change to an unrelated entry does not invalidate this source; a changed, removed, duplicate, malformed, uncommitted, or unmatched relevant entry does. `*` remains within one segment, `**` as a complete segment crosses directories, and trailing `/` is a prefix. The receipt records the sorted resolved files. Repository-internal relative symlinks are accepted; the link text, resolved path, and target content are hashed, while absolute, external, broken, cyclic, or unsupported special-file targets rerun verification. Ordinary unchanged failures may receive fresh separately authorized retries with advisory context rather than a fixed count denial. A verification batch that observably changed protected repository content remains blocked until an approved mutation repairs or reconciles the workspace.

In a Git worktree, the runner compares tracked and pre-existing non-ignored untracked content before and after the batch. If the initial protected snapshot cannot be established, no check executes. A protected-content change fails stale, increments the mutation revision, and invalidates every evidence source. Every new non-ignored untracked path created during the batch also fails stale and advances the mutation revision; source or configuration classification affects only the clarity of the message, not whether the workspace changed. Expected generated artifacts should be ignored or created during the approved mutation phase. Git-ignored paths, external dependencies, and external system state are outside this protected snapshot. Non-Git worktrees are outside the content snapshot and receipt-reuse boundary.

## Completion receipt export and offline integrity verification

After every declared source is current for the final mutation revision and no
managed service or capability claim remains active, export the canonical
unsigned envelope once:

```text
click-gate receipt export
```

The envelope binds the approved contract identity and turns, capability claim
commitments, final protected workspace digest, and per-source evidence result,
environment, executable, host-coverage, and dependency lineage. It excludes
raw argv, runner tokens and token digests, contract prose, and the workspace
path. Save the stdout JSON separately, then verify it without network access or
active contract state:

```text
click-gate receipt verify ./completion-receipt.json
```

This command performs strict schema, canonicalization, and digest checks and
reports `unsigned-integrity-only`. It does not claim publisher authenticity: a
coordinated rewrite of both body and digest remains detectable only after a
separate public-key signing layer is configured.

## Non-argv evidence completion

After collecting the assigned source, record it once:

```text
click-gate evidence '{"version":1,"evidence_id":"E-browser"}'
```

The id in this command must name a declared non-argv source. The Hook hashes the id before storing its typed per-revision state. It accepts `browser` only after a successful current-revision Browser observation and accepts `hosted`, `manual`, or `existing` as explicit agent attestations. It rejects unknown ids, duplicate current-revision completion, and every `argv` id. This makes each contract source visible to the state machine without pretending an unmatched hosted, manual, or existing event was independently proven.

## Browser primary evidence

Browser MCP calls are not an argv capability, but the Hook observes the canonical `mcp__node_repl__js` tool on `PreToolUse` and `PostToolUse`. During an approved contract it permits that tool only when `verification.evidence` contains one source with `kind: "browser"` and at least one `done_when.primary_evidence` references its id. The source description and condition prose are never searched for Browser keywords. Calls remain serial and require a stable `tool_use_id`; the matching result is recorded only against the assigned source and current mutation revision. The Hook hashes normalized input for advisory context. Repeats after success or repeated failure remain available with guidance, as do calls requesting a timeout above 30 seconds or an obvious wait above five seconds. There is no normal call-count or elapsed-session cap; after 256 normalized inputs, Click compacts the oldest per-input guidance while preserving the source receipt. A successful call marks the source observed, and that status remains observed if a later call fails. The evidence-completion command finalizes it after sufficient assigned proof. A mutation resets the Browser ledger, and current-revision completion rejects replay. Thus source admission, serial result binding, current revision, and finalization replay remain Core while input repetition, retry count, and timing are non-authoritative workflow advice.

## Enforcement boundary

This protocol removes shell-string classification from accepted capability execution and makes supported argv behavior deterministic. Compatibility class normalization cannot measure work concealed inside an allowed program and is not used to judge sufficiency. Direct process-control names are blocked and child groups are isolated, but an allowed custom program can still target unrelated processes explicitly or conceal other work internally. Executable resolution excludes repository-controlled paths but is not an operating-system capability sandbox: concurrent same-user replacement of an accepted executable outside the repository is outside this guardrail. The evidence ledger proves exact argv execution and matched Browser observation at the workflow level; hosted, manual, and existing completion remain declared attestations. Protected Git receipts exclude ignored content and do not prove external dependency or service state. The protocol does not cover unmatched hosted tools, specialized paths that opt out of hooks, hidden reasoning, semantic boundary correctness, or arbitrary custom code executed by an allowed program. Click remains a workflow guardrail, not an operating-system sandbox.
