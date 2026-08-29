# Release notes

## v0.19.0 — 2026-08-29

Click v0.19.0 makes the cheapest-evidence policy observable at the Browser boundary and removes the foreground-server failure mode that inflated one-shot game work.

### Structured and bounded primary evidence

- Contracts declare each evidence source once with an id, typed `kind`, and description. Every `done_when` condition references exactly one source id, so one source can cover several conditions without duplicating natural-language evidence text.
- Inline `done_when` strings are rejected with a migration message; contracts now use condition objects and `primary_evidence` references, and unused or unresolved evidence ids fail closed.
- Browser MCP work is available during an approved contract only when one referenced evidence source has `kind: "browser"`. Locale-specific marker and substring matching no longer controls Browser authorization; otherwise the Hook rejects it as shadow verification.
- One representative Browser session is capped at three serial tool calls and 90 seconds of measured tool time. Tool timeouts above 30 seconds and obvious waits above five seconds are rejected in favor of deterministic state or one representative interaction.
- Browser evidence is reset by a later mutation, is required before a Browser-assigned contract can complete, and cannot be repeated after current-revision completion.
- CI runs feature-branch commits through `pull_request` only and reserves the `push` trigger for `main`, eliminating the duplicate three-OS matrix that previously ran when a pushed branch also had a PR.

### Faster local feedback

- Recognizable development servers use `click-gate service` with `start` and `stop` requests. A Click-owned supervisor retains the exact child handle, isolates its process group, stops it on request or `SessionEnd`, and enforces a two-hour final lifetime ceiling.
- Foreground server forms are rejected by `click-gate mutate`, preventing a long-running child from holding the implementation command open. Direct process-control executables remain blocked.
- Exact `node --check <file>` and `node --test <file>` checks qualify as targeted evidence; project-wide `node --test` remains broad, while Node eval/print forms are not verification capabilities.

### Release gate

- The plugin manifest, repository marketplace, deterministic policy tests, READMEs, and release notes identify v0.19.0.
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
