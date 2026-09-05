# Named Verifications v1 and Evidence Shards v1

Evidence Shards lets one repository-declared broad argv suite run as stable,
independently recorded child groups. It is an optimization and provenance
layer, not a new source of test-skip authority.

Manifest schema v2 also lets callers select a committed verification definition
by a stable lowercase id. The id resolves to direct argv and then enters the
same canonical plan, receipt checks, and one-use runner as a raw argv request.
It is a command-selection convenience, not evidence, approval, or reuse
authority.

## Repository manifest

The optional manifest is `.click/evidence-shards.json`. Only the blob committed
at `HEAD` is accepted, and the working copy must be byte-equivalent after line
ending normalization. Schema v2 keeps each exact argv definition in
`verifications`; a sharded entry refers to that definition instead of repeating
the parent command:

```json
{
  "version": 2,
  "verifications": [
    {
      "id": "full-suite",
      "label": "Full test suite",
      "class": "broad",
      "checks": [
        ["python3", "-m", "unittest", "discover", "-s", "tests", "-q"]
      ]
    },
    {
      "id": "auth-unit",
      "label": "Authentication unit tests",
      "class": "targeted",
      "checks": [
        ["python3", "-m", "unittest", "tests.test_auth", "-q"]
      ]
    }
  ],
  "entries": [
    {
      "verification_id": "full-suite",
      "inventory": ["tests/test_*.py"],
      "shards": [
        {
          "id": "auth",
          "checks": [
            ["python3", "-m", "unittest", "tests.test_auth", "-q"]
          ],
          "covers": ["tests/test_auth.py"]
        },
        {
          "id": "billing",
          "checks": [
            ["python3", "-m", "unittest", "tests.test_billing", "-q"]
          ],
          "covers": ["tests/test_billing.py"]
        }
      ]
    }
  ]
}
```

Select one or more definitions without rewriting their argv:

```text
click-gate verify '{"version":2,"workdir":"/absolute/repository","names":["auth-unit"]}'
```

Names are exact, unique, lowercase ids. Definitions remain direct argv arrays;
Click never evaluates a shell string or guesses that `python` and `python3`,
relative and absolute paths, reordered options, verbosity flags, or test target
order are equivalent. Raw `checks` requests remain supported with their existing
exact-comparison rules. Schema v1 shard manifests remain readable, but they do
not provide named selection.

`label` is display-only and is excluded from the executable definition digest.
The id, class, and exact `checks` form the committed definition identity. Any
manifest working-copy edit still disables name resolution, including a label
edit, because Click will not use a partly edited policy file.

`checks` values are direct argv arrays, never shell strings. `inventory` and
`covers` use the same deterministic pattern grammar as the dependency manifest:
`*` stays in one segment, `**` as a complete segment crosses directories, and
a trailing `/` is a prefix. Every current tracked or non-ignored untracked file
matched by `inventory` must be matched by exactly one shard's `covers`; a shard
must not cover a repository path outside that inventory.

The repository owner asserts that the child argv groups together are
semantically equivalent to the parent suite. Click can validate exact command
identity and complete file partitioning, but it does not parse framework output
or prove that an argv command really executes every file named by `covers`.

## Runtime behavior

The caller may submit a v2 parent name or continue submitting a parent evidence
id and the original broad argv group. When a valid exact entry is available,
Click derives stable internal child evidence ids, validates every child with the
normal verification command policy, and runs the children serially.

A named request is expanded before evidence registration. Guarded still rejects
a name whose id was not declared in the approved contract. The one-use runner
rechecks the same committed manifest, HEAD, and byte-identical working copy
before any named command starts; a race or edit executes no check. Workdir,
environment, executable content, host coverage, workspace, and exact check
bindings retain their existing validation.

- Each child owns its own check, environment, executable, host-coverage,
  workspace, result, and reuse lineage.
- A passing child remains current when a later sibling fails.
- A failed or unexecuted child is never treated as passing.
- Submitting the parent again reruns only unresolved children at the same
  revision; the parent is complete only when every child is current.
- Child ids are internal. Direct child submission is rejected so Click can
  revalidate the complete parent plan on every request.
- Immediately before execution, the one-use runner reloads the committed map,
  working copy, and inventory. A race or changed plan executes no child.

## Reuse authority

The shard manifest authorizes decomposition only. After a mutation, a prior
child success may move to the new revision only through Click's existing reuse
rules:

- a complete runtime dependency observation plus an approved or committed
  dependency declaration; or
- an exact child entry in committed `.click/evidence-reuse.json` whose safe
  path policy covers every net change.

Without one of those authorities, all stale children rerun. The shard map,
shard id, inventory partition, or a sibling's result can never authorize a
cross-revision skip. `.click/evidence-shards.json` is itself a protected policy
path and cannot be declared safe by the safe-change policy.

## Fail-closed fallback

Click runs the original parent suite when the map is absent, uncommitted,
edited, malformed, oversized, duplicated, incomplete, unsupported, or no
longer covers the current inventory exactly once. If an already-active plan
loses authority, its partial child results are discarded before the original
parent is prepared. An attempted parent-command substitution remains rejected
rather than becoming a fallback escape.

Fallback is intentionally safe but can cost more time. It never turns a map
problem into a false passing aggregate.

## State and receipts

Shard children use the normal evidence ledger, so mutation invalidation,
partial batch recording, dependency receipts, safe-change receipts, crash-safe
atomic state writes, and host parity stay on the established paths. The active
state stores digests and stable shard ids, not raw parent commands or inventory
paths.

Unsharded completion receipts remain v2. A completion containing shards uses
receipt v3, which adds strict per-source shard provenance: parent source and
parent check digests, shard id and complete shard count, plan, relevant entry,
and inventory digests. Offline verification accepts legacy v1, unsharded v2,
and sharded v3, and rejects a missing or inconsistent v3 shard member.

If a later Evidence task actually reuses a requalified result, its completion
receipt uses v4. A v4 receipt that contains shards preserves every complete
per-source shard provenance field required by v3 and additionally binds the
origin Evidence task and requalification lineage. Candidate retention alone is
not reuse and does not change the receipt version.

## Deliberate exclusions

Evidence Shards v1 does not provide zero-configuration framework discovery,
arbitrary test-output parsing, parallel or distributed execution, remote or CI
caches, cross-contract/global caches, Shadow Observer authority, Evidence Map
UI, release, deployment, or installation behavior.
