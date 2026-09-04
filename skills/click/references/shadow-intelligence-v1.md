# Shadow Intelligence v1

Shadow Intelligence turns the latest Phase 1 observer aggregate into an
explainable prediction, evaluates that prediction against the real rerun, and
projects the result into a local Evidence Map and ROI view. It remains
permanently non-authoritative.

## Safety boundary

Every compatible argv check still runs exactly once through the established
verification path. Shadow Intelligence cannot skip, reorder, pass, fail,
satisfy, block, or reuse a check. It does not enter approval, evidence,
completion, dependency receipts, safe-change policy, or completion receipts.

All baseline, prediction, and evaluation records carry:

```json
{
  "mode": "shadow",
  "authoritative": false,
  "reuse_authorized": false
}
```

There is no conversion from these records to
`runtime-dependency-observation-v1`. An authoritative observer would require a
new contract and schema; it cannot reinterpret Shadow data as prior authority.

## Baseline fingerprints

After a successful real check with a complete Shadow Observer record, Click
creates a bounded baseline for at most 1,024 observed repository inputs. The
baseline binds the exact evidence key, check digest, mutation revision,
verification environment, executable, known host coverage, collector binary,
and original Observer record digest.

Only the following repository-relative identities are retained:

- regular files: mode and content digest;
- directories: mode and a bounded digest of sorted entry names and types;
- missing lookups: a missing marker;
- safe relative symlinks: link identity and an in-repository target identity.

Absolute, external, broken, cyclic, racing, excessive, or unsupported paths do
not produce a baseline. File content, excerpts, raw directory names, command
arguments, environment values, raw events, and external absolute paths are not
stored. A later type change, deletion, missing-path appearance, file content
change, or directory membership change invalidates the comparison.

## Pre-run prediction

Verification preparation writes a canonical prediction before the one-use
runner can launch the real child process. Its digest covers the prediction
payload, including its preparation time and current revision. The runner may
later add an evaluation, but it cannot rewrite that prediction.

`decision` is one of:

- `reuse-candidate`: observed repository inputs and known bindings match;
- `rerun-required`: an observed input or a known binding changed;
- `not-evaluable`: no prior baseline exists or a safe current snapshot could
  not be made.

A complete record that observed outside-repository inputs may still produce a
Shadow candidate so the real rerun can measure it, but the prediction carries
`external-inputs-unmodeled`. That candidate is not authority-eligible.
Incomplete process coverage and unresolved events never create a new baseline.

## Post-run evaluation

Only after the real command finishes and Click checks the protected workspace
does it attach one outcome:

| Prediction and real result | Outcome |
| --- | --- |
| candidate + pass | `confirmed-candidate` |
| candidate + fail | `contradicted-candidate` |
| rerun + fail | `correct-invalidation` |
| rerun + pass | `conservative-rerun` |
| missing, incomplete, drifted, or mutating observation | `not-evaluable` |

“Confirmed” means only that the candidate agreed with this real rerun. It is
not proof that future reuse is safe. A contradiction is recorded rather than
explained away as a flaky test. Collector drift, execution-binding drift,
incomplete observation, and a verification-time workspace mutation make the
evaluation not evaluable.

One source retains only its previous successful baseline, current pre-run
prediction, and latest post-run evaluation. The data lives only in the current
Click lifecycle.

## Evidence Map and ROI projection

The dashboard receives a separate, strict, bounded projection instead of the
raw Click state. It contains generic source labels, source status, canonical
repository-relative input paths, observed operations, changed markers,
prediction reasons, outcomes, and aggregate counters. At most 512 unique input
nodes are projected; additional nodes are counted but not rendered.

Shadow ROI is intentionally literal:

- `actual_saved_ms` is always `0` because every check ran;
- `gross_potential_ms` includes only a candidate confirmed by its real rerun;
- `observer_overhead_ms` is measured observer setup and normalization work;
- Shadow fingerprint and dashboard rendering cost are not included;
- tracing slowdown is explicitly marked unmeasured;
- no net saving or safety proof is claimed.

Malformed fields, unknown versions, invalid paths, unsupported enums, digest
tampering, and payloads beyond the state or projection limits are rejected
inside the Shadow boundary and cannot alter verification.

## Local dashboard

Use an active Evidence or approved Guarded lifecycle:

```text
click-gate dashboard start
click-gate dashboard status
click-gate dashboard stop
```

Start prints a `127.0.0.1` URL carrying a random access token in the URL
fragment. The fragment is removed from browser history after load and is sent
only as an Authorization header to the single snapshot endpoint. The token is
stored in Click state only as a SHA-256 digest.

The server binds IPv4 loopback only, validates the Host header, sends no CORS
permission, uses `Cache-Control: no-store`, and applies a restrictive Content
Security Policy. HTML, CSS, and JavaScript are embedded immutable assets with
no CDN or external runtime dependency. The HTTP surface has no state-changing
method, arbitrary path reader, file-content endpoint, or raw-state endpoint.

The dashboard starts only on an explicit command, polls the current sanitized
projection, stops explicitly or at session end, and enforces a two-hour maximum
lifetime. Its start and stop do not change the mutation revision or evidence
status because the viewer is read-only.
