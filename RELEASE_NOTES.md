# Release notes

## Unreleased — enforcement-boundary hardening

This candidate hardens Click without expanding product scope.

- Git inspection now uses subcommand-specific positive option policies and a dedicated sanitized executor. `git grep` and `git cat-file` are temporarily excluded; pager/config override paths are rejected; inherited `GIT_*` variables are stripped; supported diff rendering is forced through `--no-ext-diff` and `--no-textconv`.
- `click-gate bypass` now requires an exact first-line `@Click bypass` directive, is same-turn and one-use, and does not clear an active contract. `@Click cancel` separately authorizes one `click-gate cancel` that clears active contract state.
- Seven-day cleanup applies only to ephemeral state. Staged and approved-incomplete contracts do not expire automatically; completed contracts use a longer cleanup TTL.
- Final verification now fails stale for every newly created non-ignored untracked path. Source/config classification affects messaging only; expected generated artifacts should be ignored or created during the approved mutation phase.

## Verification

- 139 deterministic tests pass locally.
- Focused regressions cover Git pager/config execution paths, removed Git subcommands, same-turn one-use bypass/cancel authorization, eight-day Manual incomplete-contract persistence, root-level source/config files, generic reports, and ignored verification artifacts.
- The runtime remains standard-library-only and keeps external state content-free.

This is a release-note draft for the next Click release; it does not publish a new version or claim new A/B benchmark results.
