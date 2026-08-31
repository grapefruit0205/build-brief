# Release notes

## Unreleased v0.25 candidate — authorization and evidence core

Click now states its stable product boundary directly: bind AI execution to
approved intent and return verifiable evidence. Model workflow strategy is not
runtime authority.

### Plan tools become non-blocking advisory

- `update_plan` and equivalent host plan tools remain available while a Click
  workflow is armed, staged, approved, or in read-only review.
- Plan output cannot stage, approve, replace, or widen an execution contract. It
  does not change the contract digest, mutation authority, revision, or evidence
  state.
- Skill guidance may still recommend implementing directly from the compact
  contract and avoiding unnecessary parallel planning, but that recommendation
  is non-blocking and non-authoritative.

### Broad-inventory counts become non-blocking advisory

- A distinct-digest broad repository inventory may run even while another broad
  inventory is running or after one succeeds; narrowing context is advisory.
- The decision depends on observable argv, request digest, revision, and runtime
  state—not model identity or a model-specific workflow score.
- An active exact-digest observation reservation remains blocked by a separate
  runner-state interlock. A completed exact-digest request is handled by the
  logical-repeat advisory below. Broad advice cannot alter contract, digest,
  mutation, or evidence authority.
- Structured read admission, one-use claims, path and environment safety,
  cancellation, replay and tamper checks, mutation and verification interlocks,
  output caps, and retained-state limits remain unchanged.

### Logical repetition and fixed argv retries become non-blocking advisory

- A fresh request for an identical successful read or search is allowed through
  a newly issued one-use runner and receives reuse or narrowing guidance. This
  is a new authorization, not replay of the consumed runner token.
- An observation that has already failed or produced incomplete output twice,
  and an ordinary argv evidence source that has already failed twice, may be
  retried under fresh authorization with non-blocking repair guidance.
- The decision remains model-neutral and depends only on the request digest,
  revision, result state, and exact runner authorization.
- A same-digest observation already running remains blocked because issuing a
  second reservation would conflict with its active token and result record.
  Verification that changed protected repository content also remains blocked
  until an approved mutation repairs or reconciles the workspace.
- Consumed-token replay, request substitution, active mutation or verification
  races, receipt mismatch, cancellation, tampering, and verification budget
  enforcement remain hard. Browser duplicate and retry tuning is intentionally
  deferred to its separate migration.

### Runtime authority remains hard

- Distinct-turn approval and exact contract-digest binding remain required.
- Unauthorized mutations, mid-run contract replacement, runner replay,
  cancellation bypass, state tampering, and evidence-integrity failures remain
  fail-closed.
- One-use runners remain bound to their exact request, and evidence receipts
  remain bound to the active contract, mutation revision, protected workspace,
  execution environment, and executable fingerprint.

## v0.24.6 — 2026-08-31

Click v0.24.6 is a focused Windows/Codex Desktop compatibility and runner-state
recovery patch. Contract shape, approval semantics, evidence protocol,
verification budgets, and the observable workflow policy remain unchanged.

### Recover approved runner state before strict path resolution

- Stateful mutation, verification, and managed-service runners keep the final
  canonical `Path.resolve(strict=True)` admission check, but an already-issued
  approved runner may now restore its exact missing session-contract state from
  a short-lived recovery mirror before that strict check runs.
- Recovery requires the explicit bound state path plus the existing request or
  service binding and one-use runner token to match. Wrong tokens, mismatched
  requests, cancelled contracts, expired reservations, and consumed-runner
  replay remain fail-closed.
- Explicit contract cancellation removes the recovery mirror. Recovery-only
  paths use non-strict canonicalization so macOS aliases such as `/var` and
  `/private/var` resolve to the same snapshot without weakening the final state
  path validation.

### Windows Python launcher fallback

- Windows lifecycle Hooks no longer assume that `py -3` can resolve an
  installed interpreter. The launcher probes Python 3 through `py -3`, then
  `python`, then `python3`, and a broken `py` launcher can fall through to a
  working `python.exe`.
- Once the Hook starts, rewritten Click runners reuse the exact selected
  `sys.executable` instead of returning to `py -3`. Existing encoded transport,
  runner claims, state-root binding, and shell-free capability execution remain
  unchanged.
- The Windows regression suite includes a fake `py` launcher that reports
  `No installed Python found!` while a real `python.exe` remains available.

### Codex Desktop exec routing and Hook launch

- The existing canonical `Bash|apply_patch|...` PreToolUse matcher remains
  unchanged. A separate Desktop execution matcher covers `exec_command`,
  `shell_command`, `unified_exec`, function-qualified forms, and observed Code
  Mode aliases.
- Direct execution aliases are normalized onto Click's canonical Bash policy
  before the core state machine sees the event, so `click-gate` control commands
  and structured reads receive the same rewrite and enforcement when the host
  dispatches the matching Hook event.
- Windows lifecycle Hooks invoke the quoted `.cmd` launcher directly instead of
  wrapping the entrypoint in an embedded PowerShell `-Command` payload.
  UserPromptSubmit, PreToolUse, PostToolUse, and SessionEnd keep their existing
  lifecycle semantics and timeouts.
- This does not claim to solve a host path that never dispatches PreToolUse.
  If Codex Code Mode executes through a surface for which the client emits no
  matching Hook event, Click cannot observe or enforce that execution.

### Regression and release gate

- Focused regressions cover deleted state-root/state-file recovery, wrong-token
  rejection, cancel/replay revocation, Windows encoded-runner recovery, broken
  `py` fallback, direct `cmd.exe` UserPromptSubmit context, Desktop
  `exec_command` rewriting, structured inspection, and rewritten runner
  execution through PowerShell and `cmd.exe`.
- The compatibility patches passed deterministic CI on Ubuntu, macOS, and
  Windows and the Plugin Security Scan before this release metadata was staged.
- The immutable `v0.24.6` tag and GitHub Release must point to the exact merged
  main commit that passes the final release CI and security checks.

## v0.24.5 — 2026-08-31

Click v0.24.5 is a focused Windows internal-runner shell compatibility
release. Contract shape, evidence transport, approval behavior, and
non-Windows runner rendering remain unchanged from v0.24.4.

### Cross-shell Windows runner launch

- Rewritten `inspect`, observation, mutation, service, and verification
  runners now reuse the bare `py -3` launcher already required by the Windows
  lifecycle hooks.
- The generated command no longer places a quoted absolute `sys.executable`
  path in command position, where PowerShell treats it as a string expression
  unless an incompatible shell-specific call operator is added.
- The resolved Click script path remains quoted, while every action, state
  path, token, and request stays inside the bounded encoded-runner transport.

### End-to-end Windows regression

- The Windows integration suite now asks the real PreToolUse hook to rewrite
  structured `click-gate inspect` requests, then executes the returned
  commands through both PowerShell and `cmd.exe`.
- Normal and space-containing plugin roots are covered. Stateless inspection
  and separately authorized stateful review runners must both return the
  inspected file contents successfully from both shells.
- Platform-independent tests pin the bare `py -3` prefix, exclude the
  interpreter's absolute path from the emitted command, and retain expansion-
  token hiding, launcher-path rejection, payload bounds, and decode fidelity.

### Compatibility and release gate

- POSIX rendering still uses `shlex.join`; Windows command-length limits and
  fail-closed launcher-path checks are unchanged.
- Fail-closed state-root validation is also unchanged: this release verifies
  reachable state bindings cross-shell but does not recreate a missing or
  inaccessible approval state.
- The shared source hook and generated Antigravity distribution remain byte-
  equivalent. On Windows, the Antigravity adapter translates the portable
  launcher back to its active interpreter argv before direct shell-free
  execution, avoiding a new launcher dependency or behavior change.
- The exact merged-main commit must pass the deterministic suite on Linux,
  macOS, and Windows plus Plugin Security Scan before the immutable `v0.24.5`
  tag and GitHub Release are published and reinstalled.

## v0.24.4 — 2026-08-31

Click v0.24.4 is a focused contract-boundary extraction and verification
environment recovery release. Existing contract shape, evidence protocol,
mode behavior, and the v0.24.3 runner-claim lifecycle remain unchanged.

### Contract validation leaf extraction

- Contract constants and pure validation now live in `hooks/click_contract.py`,
  which has no upward runtime dependency on `click_gate` or state/process
  modules.
- `click_gate._validate_contract` remains the exact validator function through
  a direct compatibility alias. Validation order, accepted values, returned
  contract objects, and error messages are unchanged.
- Focused unit and architecture-policy tests pin the new leaf boundary and
  compatibility surface.

### Self-healing verification environment admission

- Prepared environment key/value HMAC records now carry an authenticated
  aggregate binding tied to the one-use runner token.
- If a prepared project, user, PATH, or toolchain value changes or disappears
  before runner claim, Click projects current values onto the prepared key
  set, ignores runner-only additions, and rebinds the canonical environment
  digest automatically without another approval.
- Successful evidence receipts store the actual rebound environment digest.
  Exact executable fingerprints remain fixed; changed executables and
  malformed or tampered bindings still fail closed before any check executes.

### Compatibility and release gate

- The source and Antigravity distribution share the extracted validator and
  verification recovery behavior; unrelated adapter behavior is unchanged.
- Focused regressions cover changed and missing environment values,
  runner-only additions, Windows case-insensitive keys, tampered bindings,
  executable changes, receipt identity, and exact contract errors.
- The exact merged-main commit must pass the deterministic suite on Linux,
  macOS, and Windows plus Plugin Security Scan before the immutable `v0.24.4`
  tag and GitHub Release are published and reinstalled.

## v0.24.3 — 2026-08-30

Click v0.24.3 is a focused observation-runner lifecycle hardening patch.
Contract shape, evidence protocol, mode behavior, module boundaries, and the
v0.24.2 Windows launcher repair remain unchanged.

### Claim before read

- A tracked inspection now writes an unclaimed reservation, then atomically
  claims its managed state path, active status, current revision, exact request
  digest, one-use token, replay state, and freshness immediately before any
  read executes.
- An unclaimed startup reservation expires after 30 seconds. Once claimed, a
  synchronous read does not expire merely because time passes; it continues to
  block mutation and final verification until the runner records its result or
  the user explicitly cancels the contract.
- Tampered, unmanaged, stale-revision, expired, cancelled, or replayed runners
  execute no read. Successful, failed, and incomplete results clear the claim;
  a safe no-child startup failure records exit 127 and releases the claim for
  the existing bounded retry path.

### Recoverable verification admission

- Verification environment binding now canonicalizes the Hook-owned
  `PLUGIN_ROOT` value as launcher bookkeeping while retaining project, user,
  PATH, toolchain, executable, tree, and exact-check binding.
- When verification admission fails before any check executes, the runner may
  release only the exact digest/token-matched unclaimed reservation. Its
  sources return to `ready` without fabricated evidence or a consumed
  test-failure retry. Claimed, stale, unavailable, tampered, and replayed state
  remains fail-closed.

### Compatibility and release gate

- Focused regressions cover claim-before-execution, replay rejection,
  unclaimed expiry, claimed-read interlocks, startup-failure cleanup,
  Hook-owned environment normalization, verification admission cleanup,
  tampered/claimed fail-closed behavior, parallel result recording, and
  existing inspection behavior on Linux, macOS, and Windows.
- The Antigravity distribution is regenerated from the same source, while its
  documented host limitations remain unchanged.
- Issue #25 remains open because this patch does not claim to repair a host
  path that does not deliver Click's matching PreToolUse event.
- The exact merged-main commit must pass the deterministic suite on Linux,
  macOS, and Windows plus Plugin Security Scan before the immutable `v0.24.3`
  tag and GitHub Release are published and reinstalled.

## v0.24.2 — 2026-08-30

Click v0.24.2 is a focused Windows Codex hook-launch compatibility patch.
Contract shape, evidence protocol, mode behavior, and runtime authorization
rules remain unchanged from v0.24.1.

### Windows plugin-root template compatibility

- `hooks/hooks.json` now uses Codex's `${PLUGIN_ROOT}` template in every
  `commandWindows` hook command instead of the cmd-style `%PLUGIN_ROOT%` form.
  The path remains quoted and uses Windows separators after host rendering.
- A Windows regression suite pins all four lifecycle commands and, on the
  Windows CI runner, executes them through PowerShell from both an ordinary
  plugin root and a plugin root containing spaces.
- The patch covers UserPromptSubmit, PreToolUse, PostToolUse, and SessionEnd
  launcher rendering without changing their Click modes or authorization
  semantics. SessionEnd remains capped at the host-supported three seconds.

### Scope and release gate

- This patch does not claim to fix host-side hook dispatch paths that do not
  invoke Click's PreToolUse hook. The separately reported Windows Codex Desktop
  unified-exec dispatch issue remains an upstream/host compatibility boundary
  unless the host begins delivering the matching hook event.
- Existing Always ON or Manual preferences and active-state formats require no
  migration. Users refresh the `click` marketplace, reinstall `click@click`,
  restart the desktop app, review the updated Hook, and begin a new task.
- The exact release commit must pass the deterministic suite on Linux, macOS,
  and Windows, repository distribution checks, and Plugin Security Scan before
  the immutable `v0.24.2` tag and GitHub Release are published.

## v0.24.1 — 2026-08-30

Click v0.24.1 is a focused host-compatibility patch for the SessionEnd
lifecycle hook. Contract shape, evidence protocol, mode behavior, and all
runtime authorization rules remain unchanged from v0.24.0.

### SessionEnd timeout compatibility

- `hooks/hooks.json` now declares the SessionEnd command timeout as three
  seconds, matching the host's supported maximum and removing the startup
  clamping warning.
- UserPromptSubmit, PreToolUse, and PostToolUse retain their seven-second
  timeouts, and every hook command and matcher remains unchanged.
- The deterministic hook-configuration regression test now pins all four
  timeout values to prevent this compatibility setting from drifting.

### Compatibility and release gate

- Existing Always ON or Manual preferences and active-state formats require no
  migration. Users refresh the `click` marketplace, reinstall `click@click`,
  restart the desktop app, review the updated Hook, and begin a new task.
- The exact release commit must pass the full deterministic suite on Linux,
  macOS, and Windows, the repository distribution checks, and Plugin Security
  Scan before the immutable `v0.24.1` tag and GitHub Release are published.

## v0.24.0 — 2026-08-30

Click v0.24.0 changes normal anti-loop decisions from raw call counts to
current, revision-bound evidence. Authorization, process claims, concurrent
execution guards, and verification-time mutation detection remain fail-closed.

### Content-free evidence boundary

- `click_evidence.py` now owns deterministic evidence-ID hashing, registry
  digests, initial source and Browser-session state, ledger-shape validation,
  and pure current-revision and kind lookups.
- `click_gate.py` retains contract and protocol validation, transition timing,
  verification budgets and retries, Browser admission, completion policy,
  persistence, and runner orchestration. Dependency direction remains
  `click_gate → click_evidence`.
- Compatibility aliases preserve direct callers and legacy state keeps its
  distinct fail-closed migration path. Codex and Antigravity bundle the same
  standard-library-only evidence module.

### Evidence-driven inspection and verification

- Approved implementation and read-only review may perform the first broad
  repository inventory for the current mutation revision. A concurrent broad
  inventory, or any later broad inventory after success, is blocked even when
  it uses different argv; narrower inspection remains available.
- Verification protocol v2 may submit any nonempty subset of unresolved argv
  sources. The first accepted check group for each source reserves its exact
  normalized digest and Hook-inferred units for the active contract, and the
  cumulative reservations must fit the approved scale. Partial requests cannot
  split around the budget.
- A current successful exact argv check is skipped only when the same active
  contract and mutation revision, check group, protected Git tree digest,
  Hook-prepared execution context, and resolved executable fingerprint still
  match. A new mutation revision never auto-promotes stale evidence; non-Git
  worktrees and missing or mismatched receipts rerun the check.
- Click binds every prepared environment key and value with keyed content-free
  hashes before issuing the rewritten runner. The runner requires every bound
  value to match, excludes launcher-only additions from the child check, then
  fingerprints the resolved target and pins the selected launcher path
  immediately before execution, preserving virtual-environment and shim
  semantics. Hardened structured SSH policy and remote-URL redaction also
  remain active after executable pinning.
  macOS and Windows shell bookkeeping therefore cannot invalidate an unchanged
  receipt, while a changed prepared value or executable fails closed.

### Browser input deduplication

- Assigned Browser work remains serial but no longer uses a normal three-call
  or 90-second session cap. A normalized input that succeeds is blocked on
  repetition for the current revision. A failed input gets one identical retry
  and is then blocked, while a different input remains available.
- The 30-second per-call timeout and five-second explicit-wait maximum remain.
  A 256-unique-input ceiling protects state growth and is not an expected usage
  target. Once a source is observed, a later distinct failure does not demote
  it before finalization.
- These receipts and counters remain workflow guardrails, not a sandbox.
  Protected Git snapshots exclude ignored content and do not prove external
  dependencies, services, or semantic sufficiency.

### Distribution and release gate

- Codex and the generated Antigravity distribution bundle byte-equivalent gate,
  evidence, and policy sources where their host capabilities overlap.
- The exact release candidate is gated by the deterministic suite on Linux,
  macOS, and Windows plus plugin, marketplace, skill, compilation, whitespace,
  distribution-consistency, and Plugin Security Scan checks.

## v0.23.0 — 2026-08-30

Click v0.23.0 extracts the shared shell-free process mechanics into a small,
standard-library-only module. Contract JSON, evidence protocol, modes, approval
behavior, executable trust, and Git/SSH policy remain unchanged.

### Shared process boundary

- `click_process.py` now owns synchronous argv execution, managed-process
  spawning, platform-specific child-process-group isolation and termination,
  and bounded runner-output copying.
- Every shared runner still executes an already-authorized argv with
  `shell=False`; synchronous execution also remains `check=False`. The gate
  continues to resolve trusted executables and construct sanitized environments
  before invoking this process layer.
- `click_gate.py` retains contract and capability policy, state transitions,
  one-use runner claims, Git/SSH restrictions, service and verification
  orchestration, workspace snapshots, budgets, and evidence semantics.
  Compatibility aliases preserve the existing internal test and direct-caller
  surface while modularization proceeds incrementally.
- Evidence-ledger modularization is intentionally not included in this release;
  verification protocol version `2` and its stored completion state are unchanged.

### Distribution and release gate

- Codex and the generated Antigravity distribution bundle the same
  `click_process.py` and `click_gate.py` sources. Antigravity's adapter-specific
  host launcher remains separate because its lifecycle semantics differ.
- Dedicated regressions cover POSIX and Windows isolation, graceful and forced
  termination paths, shell-free run/spawn calls, bounded output, one-way module
  dependencies, and sibling-only distribution startup.
- The exact release candidate is gated by the deterministic suite on Linux,
  macOS, and Windows plus plugin, marketplace, skill, compilation, whitespace,
  distribution-consistency, and Plugin Security Scan checks.

## v0.22.0 — 2026-08-30

Click v0.22.0 hardens the experimental Antigravity adapter and extracts the
shared runtime state-storage boundary into a dedicated module. Contract JSON,
evidence protocol, modes, and the one-approval workflow remain unchanged.

### Antigravity launcher boundary

- The experimental Antigravity adapter accepts only the exact absolute Python
  and adapter paths injected by its current `PreInvocation`; basename lookalikes,
  relative launchers, and substituted interpreters cannot authorize a Click
  control command.
- The accepted launcher is parsed as one expansion-free Bash command before its
  absolute argv prefix is compared. Appended or glued shell operators,
  redirects, substitutions, globs, and multiline suffixes fail closed.
- Because Antigravity cannot rewrite `run_command` argv, direct read-only
  `run_command` calls now fail closed and use `control inspect` instead. Native
  file/search tools and unrelated MCP, Skill, and Plugin tools remain available.
- Antigravity parses Click's encoded Windows runner command with the native
  Windows argv parser and still executes the resulting argv without a shell.

### Shared state-storage boundary

- `click_state.py` now owns configuration and state paths, hashed workspace and
  thread identities, canonical managed-state validation, atomic JSON writes,
  and the cross-process state lock used by both Codex and Antigravity adapters.
- Contract policy, capability classification, process execution, and evidence
  semantics remain in `click_gate.py`; this release intentionally moves only
  storage primitives so the refactor does not change authorization behavior.
- Source and Antigravity distribution tests launch each gate with only its
  sibling runtime modules available, preventing accidental imports from the
  repository source tree. Existing managed state remains compatible.

### Compatibility and release gate

- Direct `click-gate` integrations continue to use verification protocol
  version `2`; no contract or evidence migration is required.
- The exact release candidate is gated by the deterministic suite on Linux,
  macOS, and Windows plus plugin, marketplace, skill, compilation, whitespace,
  distribution-consistency, and Plugin Security Scan checks.

## v0.21.1 — 2026-08-30

Click v0.21.1 is a focused workflow-security maintenance release. It closes executable-resolution and runner-authorization gaps without changing the compact contract schema or one-approval workflow.

### Read-only execution boundary

- Read-only capabilities now accept only bare executable names. Names containing `/` or `\\`, Windows drive-prefixed forms such as `C:cat.exe`, and UNC forms fail closed before execution.
- Direct recognized reads are always rewritten through Click's shell-free inspection runner, including when no contract or review ledger is active. This preserves lightweight reads while preventing the original shell from resolving a workspace-controlled lookalike.
- The runner removes empty, relative, and repository-resolving PATH entries, rejects repository executables and symlinks in either direction, resolves the accepted executable to an absolute real path, and executes that path. The boundary is the nearest containing Git repository, or the current working directory outside Git. The same rule covers local Git and SSH inspection.
- Read and Git children also drop inherited `LD_*`, `DYLD_*`, `GCONV_PATH`, and `LOCPATH`; Git additionally drops inherited `GIT_*` configuration. Internal Git snapshots resolve Git through the same executable boundary.

### Mutation authorization and runner state

- A structured mutation runner now atomically claims its managed state path, approved status, request digest, one-use token, replay state, and expiry before starting the requested process. Invalid, expired, tampered, unmanaged, or replayed runners execute zero mutation commands. An unstarted reservation may expire; after claim, it remains active until result recording or explicit cancellation rather than guessing that the child stopped.
- Managed-service start and supervisor launches now use the same digest-bound, one-use pre-execution claim, preventing replay from spawning another server. A claimed verification batch likewise cannot expire into a parallel retry while its process may still be running.
- Unclaimed verification and managed-service reservations are rechecked for malformed, future, or expired timestamps at the execution claim itself. On Windows, rewritten runner arguments travel in a bounded compressed encoding so legal `%...%` and `!...!` path text cannot be expanded by `cmd.exe`; launcher paths containing cmd.exe or PowerShell expansion characters fail closed.
- Mutation-result recording accepts only a successfully claimed runner. Every stateful rewritten command carries the Hook-selected canonical `gate-state` root and canonical state path, so child runners do not depend on an ambient `PLUGIN_DATA` value or accept a symlinked/mismatched state file.
- In a detected Git worktree, failure to establish the initial protected-content snapshot fails closed before any verification check runs.

### Compatibility and release gate

- Contract JSON, evidence protocol, modes, and user approval behavior are unchanged from v0.21.0. Existing users should refresh the marketplace snapshot, reinstall Click, restart the app, review the updated Hook, and begin a new task.
- The deterministic suite includes path-qualified, PATH-shadow, symlink, absolute-executable, state-tamper, expiry, and replay regressions. The tag is published only after the exact release branch passes the full local gate and Linux, macOS, Windows, and Plugin Security Scan workflows.
- These changes harden Click's observable workflow boundary. Click still does not claim to be an operating-system sandbox or to protect secrets, network access, external paths, concurrent same-user replacement of an executable outside the repository, or arbitrary behavior hidden inside an approved custom program.

## v0.21.0 — 2026-08-29

Click v0.21.0 connects every declared completion source to current-revision Hook state. It removes the ceremonial local verification batch from contracts whose sufficient evidence is Browser, hosted, manual, or existing, while binding every local argv check to the exact approved evidence ID it proves.

### Upgrade required

Existing Click users must refresh the marketplace snapshot and reinstall the plugin:

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

Direct `click-gate` callers must send verification protocol version `2` and include an approved argv `evidence_id` on every check. A v0.20 contract that was staged or approved but not completed has no reconstructable per-source ledger; complete it before upgrading, or use the exact `@Click cancel` flow after upgrading and then stage and approve a fresh contract.

### Per-source execution state

- Final argv verification now uses protocol version `2`; every check carries an `evidence_id` that must resolve to a declared source with `kind: "argv"`.
- The Hook stores a content-free, hashed per-id ledger whose source count and typed registry digest detect partial entry loss, and completes a contract only when every declared source passed at the current mutation revision and no managed service remains active. A contract whose evidence is entirely Browser, hosted, manual, or existing no longer needs an unrelated local verification command.
- One final argv batch must cover every unresolved argv source. Staging rejects an argv registry whose minimum one-check-per-source cost or check count cannot fit the selected scale. Several adjacent checks may share one id, and all must pass. If an earlier source succeeds before a later source fails, its result remains current while the unresolved source receives the bounded retry. The rewritten runner is atomically claimed before checks execute, so replay cannot rerun them.
- Successful Browser work is observed first and explicitly finalized with `click-gate evidence`. The same command records hosted, manual, or existing completion as an explicit attestation; it cannot complete argv evidence and does not claim to independently prove unmatched external events.
- A mutation, including protected workspace content created by verification, invalidates every source. Evidence IDs are hashed in persistent state; descriptions, conditions, argv, and output remain absent. The deterministic hashes avoid plaintext storage but do not make predictable IDs confidential.
- Incomplete contracts staged before the evidence ledger cannot be reconstructed from a digest. They fail closed with cancel-and-restage guidance. A legacy contract that had already completed under its prior current-revision rule still permits normal rollover.

### Smaller entrypoint, honest cumulative cost

- `plain_language` remains canonical and digest-bound, but presentation now renders its exact value once instead of duplicating the easy explanation outside and inside the displayed contract.
- Measured from v0.18 to v0.21, the always-loaded Click entry skill shrank from 12,996 to 6,029 bytes (53.6%), while the root plus all six references grew from 38,358 to 44,774 bytes (16.7%). The usual pre-stage bundle (root, modes, directive format, and verification profiles) moved from 25,047 to 24,669 bytes (-1.5%). Relative to v0.20, the cumulative root-plus-reference source grew 10.9% to document the evidence protocol. This is progressive disclosure and a smaller entrypoint, not a claim that every full-workflow prompt became half as large.

## v0.20.0 — 2026-08-29

Click v0.20.0 keeps the one-contract, one-approval workflow while making its purpose clearer: agree once on what will change, what must stay true, and what evidence will count, then keep implementation and necessary verification inside that boundary without observable replanning, repository-wide rescans, or duplicate proof.

### Upgrade required

Existing Click users must refresh the marketplace snapshot and reinstall the plugin to load v0.20.0:

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

Restart the ChatGPT desktop app, review and trust the updated Click Hook, and start a new task so the new Skill and Hook definitions are loaded.

If you call `click-gate` directly, update `pass` to send the emitted `contract_id` instead of contract JSON, and migrate inline `done_when` strings to structured condition objects that reference `verification.evidence` ids.

### Contract-id approval and lean skill routing

- `click-gate stage` validates the canonical contract once, stores its digest and derived runtime state, binds them to a fresh opaque 128-bit `contract_id`, and returns that content-free lifecycle handle.
- A later approval or interrupted-run resume passes only the emitted id. Contract JSON is never reconstructed in the approval turn; same-turn pass, malformed ids, stale ids after a revised stage, and corrupted digests fail closed.
- Pre-id active state receives a deterministic digest-derived compatibility handle so an already staged or incomplete session can finish without exposing contract plaintext or deleting state.
- Click and Fix now route exact schema, verification, anti-loop, capability, and mode rules to their canonical references instead of repeating those details in both entry skills.

### Structured and bounded primary evidence

- Contracts declare each evidence source once with an id, typed `kind`, and description. Every `done_when` condition references exactly one source id, so one source can cover several conditions without duplicating natural-language evidence text.
- Inline `done_when` strings are rejected with a migration message; contracts now use condition objects and `primary_evidence` references, and unused or unresolved evidence ids fail closed.
- Browser MCP work is available during an approved contract only when one referenced evidence source has `kind: "browser"`. Locale-specific marker and substring matching no longer controls Browser authorization; otherwise the Hook rejects it as shadow verification.
- One representative Browser session is capped at three serial tool calls and 90 seconds of measured tool time. Tool timeouts above 30 seconds and obvious waits above five seconds are rejected in favor of deterministic state or one representative interaction.
- Browser evidence is reset by a later mutation, is required before a Browser-assigned contract can complete, and cannot be repeated after current-revision completion.
- CI runs feature-branch commits through `pull_request` only and reserves the `push` trigger for `main`, eliminating the duplicate three-OS matrix that previously ran when a pushed branch also had a PR.

### Managed local execution

- Recognizable development servers use `click-gate service` with `start` and `stop` requests. A Click-owned supervisor retains the exact child handle, isolates its process group, stops it on request or `SessionEnd`, and enforces a two-hour final lifetime ceiling.
- Foreground server forms are rejected by `click-gate mutate`, preventing a long-running child from holding the implementation command open. Direct process-control executables remain blocked.
- Exact `node --check <file>` and `node --test <file>` checks qualify as targeted evidence; project-wide `node --test` remains broad, while Node eval/print forms are not verification capabilities.

### Release gate

- The plugin manifest, repository marketplace, deterministic policy tests, READMEs, and release notes identify v0.20.0.
- The tag and GitHub Release must point to the exact protected-main commit that passes the full local suite and required GitHub Actions checks.

## v0.18.0 — 2026-08-29

Click v0.18.0 turns the hardened post-v0.17 source into one reproducible stable release without expanding the one-contract workflow.

### Enforcement boundary

- Git inspection uses subcommand-specific positive option policies and a dedicated sanitized executor. `git grep` and `git cat-file` remain excluded; pager and caller-supplied config overrides are rejected; inherited `GIT_*` variables and system/global Git config are isolated; supported diff rendering forces `--no-ext-diff` and `--no-textconv`.
- Arbitrary `--format` and `--pretty` output, signature-rendering paths, and `git status -v/-vv` are no longer read capabilities. Ordinary bounded status, diff, log, show, ref, revision, merge-base, and remote-URL reads remain available through their explicit allowlists.
- SSH Git inspection remains Experimental and is limited to the existing bounded `status`, `rev-parse HEAD`, `merge-base`, and `remote get-url` forms. It assumes a POSIX remote shell, rejects caller-supplied SSH options, requires an already-known host key, disables interactive password flows and forwarding, and uses fail-fast connection and keepalive settings.
- `click-gate bypass` requires an exact first-line `@Click bypass` directive, is same-turn and one-use, and does not clear an active contract. `@Click cancel` separately authorizes one same-turn contract cancellation.
- Staged and approved-incomplete contracts no longer expire on the ephemeral seven-day cleanup window. Final verification fails stale for every newly created non-ignored path.

### Reproducible distribution

- The plugin manifest, three READMEs, and release notes identify v0.18.0.
- The repository marketplace pins the immutable `v0.18.0` tag instead of following `main`.
- Required CI keeps the Linux, macOS, and Windows deterministic suite and adds Ubuntu release checks for the repository-owned plugin/marketplace/Click/Fix validator, Python compilation, and `git diff --check`.
- The Hook remains standard-library-only, external Click state remains content-free and outside target repositories, and Git/SSH inspection remains a workflow guardrail rather than a security sandbox.

### Release gate

The tag and GitHub Release must point to the exact protected-main commit that passed the full local suite and every required GitHub Actions check. The installed plugin is compared with that tagged artifact after publication. No unmeasured accuracy, time, token, or overdesign improvement is claimed.
