# Shadow Observer v1 contract

Shadow Observer v1 is a versioned, content-free record emitted beside real argv
verification. Native collection remains Linux-only through `strace`, while the
Phase 3B.0 backend boundary selects collectors consistently on Linux, macOS and
Windows. Collection is automatic when a trusted system `strace` is available,
but its output remains separate from evidence authority, cache, approval,
reuse, and completion paths.

Every v1 record is heuristic telemetry. The following values are mandatory and
immutable:

```json
{
  "version": 1,
  "mode": "shadow",
  "authoritative": false,
  "reuse_authorized": false
}
```

No v1 record can authorize skipping a check, satisfy an evidence source, block
an otherwise valid check, or alter its PASS/FAIL result. A later authoritative
observer requires a new, separately reviewed contract and must not reinterpret
v1 records as authority.

## Canonical record

```json
{
  "version": 1,
  "mode": "shadow",
  "status": "complete",
  "binding": {
    "evidence_key": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "check_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "mutation_revision": 14
  },
  "backend": {
    "name": "strace",
    "version": "6.8",
    "digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  },
  "inputs": [
    {
      "path": "src/auth/token.py",
      "kind": "file",
      "operations": ["read"]
    }
  ],
  "external_input_count": 0,
  "unresolved_event_count": 0,
  "child_process_count": 1,
  "process_tree_complete": true,
  "command_duration_ms": 18400,
  "observer_overhead_ms": 94,
  "authoritative": false,
  "reuse_authorized": false,
  "ineligibility_reasons": ["shadow-mode"]
}
```

`binding` uses Click's prose-free SHA-256 evidence key, the normalized check
group digest, and the mutation revision observed. `backend` records a bounded
collector identity, not its configuration. It is `null` only when the status
is `unavailable`.

`status` is one of:

- `complete`: the collector followed the full process tree and has no
  unresolved event.
- `partial`: collection returned data but identified incomplete process
  coverage or unresolved events.
- `failed`: the selected collector failed and cannot claim complete process
  coverage.
- `unavailable`: no collector ran; inputs and event counters must be empty and
  process coverage must be false.

The input kinds are `file`, `directory`, and `missing`. Operations are
`read`, `metadata`, `enumerate`, and `execute`. A directory path ends in `/`;
all persisted paths are canonical POSIX-style paths relative to the repository.
A missing lookup may retain or omit the trailing `/` according to the lookup
shape.

## Linux Phase 1 collector

The verifier resolves `strace` through the same repository-shadow-safe trust
boundary used by Click's read-only tools, then binds its version and executable
digest into the record. The digest must still match after collection or the
trace is discarded as unavailable. Click does not install `strace`. On
non-Linux systems, when it is absent or untrusted, and when nested tracing is
detected, the real check follows the established execution path and the record
is `unavailable`.

For compatible argv checks, `strace` accompanies the real command with the same
working directory, prepared environment, argument order, inherited streams,
and isolated process-group behavior. The command runs exactly once. If the
collector cannot start, Click falls back once to the established runner. After
the collector starts, missing, truncated, unparsable, or incomplete output
downgrades only the shadow status; Click never reruns the command to repair
telemetry. Commands requiring Click's existing argv transformation or output
redaction also keep that established path and record `unavailable`.

Raw trace bytes are drained through a private FIFO outside the repository, with
only up to 4 MiB retained in memory for normalization, and discarded on every
path. The FIFO is removed on every path; no raw trace file is created or
retained. `observer_overhead_ms` covers
Click-side backend preparation and normalization; it is not an estimate of the
runtime slowdown caused by tracing.

## Event-to-record semantics

The collector observes file reads, metadata lookups, missing-path lookups,
directory enumeration, process execution, process spawning, external input,
and events it cannot resolve. Only the aggregate record above crosses the
collector boundary:

- Repeated operations for the same path and kind are merged and sorted.
- Conflicting kinds for one path are rejected instead of guessed.
- Child process creation increments `child_process_count`; inability to follow
  the full tree clears `process_tree_complete`.
- An input outside the repository increments `external_input_count`. Its
  absolute path is never retained.
- An event that cannot be classified increments `unresolved_event_count`. Its
  raw payload is never retained.
- `ineligibility_reasons` is derived from status and counters, sorted, and
  always contains `shadow-mode`.

Inputs are sorted by path. Unknown fields, unknown enum values, non-canonical
ordering, duplicate entries, path traversal, absolute paths, backslashes,
control characters, invalid digests, contradictory status, and out-of-range
counters fail strict validation. Normalization is deterministic; digests are
created only for already canonical valid records. Unknown schema versions fail
closed instead of being treated as v1.

The limits are 4,096 input entries, 4,096 UTF-8 bytes per path, 256 characters
for bounded identifiers, JSON-safe non-negative integers, and 256 KiB for the
canonical UTF-8 record.

## Privacy and retention

Observer v1 stores no file contents, content excerpts, command arguments, raw
environment variables, secrets, raw process events, or absolute external
paths. The exact field allowlists are part of validation so those values cannot
be smuggled in as extensions. Digests identify the approved check and collector
artifact without copying their source material.

The Phase 1 collector discards raw events after normalization, including on
failure. Its private transient FIFO contains no durable raw file data. The
normalized aggregate is stored as the latest record per evidence
source under `verification.shadow_observer` and lives only for the active Click
lifecycle. It is not included in completion receipts. Shadow Intelligence v1
may derive a separate lifecycle-only fingerprint, prediction, Evidence Map, and
honest ROI projection from this record, but it does not change this schema or
give the record authority. Durable analytics and telemetry upload remain out of
scope and require a separate retention and consent design.

## Compatibility boundary

The existing `runtime-dependency-observation-v1` receipt remains unchanged and
continues to be the only runtime observation shape understood by the current
cross-revision reuse logic. Shadow Observer v1 deliberately has no conversion
or automatic bridge into that receipt. It never feeds Click's authority-bearing
dependency observation. Linux collection, failure, absence, and record storage
therefore cannot change whether a check runs, passes, satisfies evidence, or is
reused. macOS and Windows retain their prior verification behavior and may keep
an `unavailable` record.

## Phase 3B.0 backend boundary

`click_dependency_trace.py` remains the compatibility facade used by the
verification runtime. Operating-system-neutral record combination, lifecycle
storage and advisory rendering live in `click_observer_common.py`; bounded
backend selection and capability states live in `click_observer_backend.py`;
Linux probing, raw-event parsing and command collection live in
`click_observer_linux.py`.

Backend capability state is internal selection provenance rather than a new
Observer v1 field. An implemented adapter may report `available`, `degraded`,
`permission-required`, or `unavailable`, but the persisted record still uses
only the strict v1 statuses above. Linux selection remains subject to its
trusted executable and runtime capability probe. The macOS and Windows entries
are explicit unavailable placeholders until separate native backend contracts
are implemented; they never manufacture events or imply collection coverage.
