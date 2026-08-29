# Release notes

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
