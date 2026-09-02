# Evidence-reuse safety benchmark

This benchmark asks one question: after a repository or environment changes,
is it safe for Click to trust an earlier verification result?

It is deterministic, does not call an LLM, and invokes Click's production
cross-revision decision function directly:
`hooks.click_verification.dependency_receipt_matches`.

## Avoiding a circular score

A benchmark would be circular if it labelled every path in Click's dependency
manifest as “must rerun” and everything outside it as “safe to reuse.” That
would only test whether the implementation repeats its own rule.

This suite keeps the inputs independent:

- `scenarios.py` defines a semantic oracle from fixture behavior. It does not
  import or inspect manifest rules.
- `manifests.py` defines five manifest states. It does not import or inspect
  oracle labels.
- `runtime_observations.py` defines the controlled baseline inputs reported by
  each fixture runtime. It imports neither scenarios nor manifest rules.
- `runner.py` crosses every semantic mutation with every manifest state and
  passes the baseline observation into Click's production receipt builder and
  decision function.
- Every case performs the real verification command again as a shadow result.
  The oracle and actual rerun remain separate in JSON.

The five manifest states are:

1. `exact`: complete and narrowly scoped;
2. `broad`: valid, but treats the whole repository as a dependency;
3. `incomplete`: valid JSON that deliberately omits real dependencies;
4. `uncommitted`: changed after the baseline commit; and
5. `malformed`: replaced by invalid JSON after the baseline commit.

The last four are controlled stress inputs. In particular, an incomplete
manifest checks whether the baseline observation fills a silently omitted
runtime dependency. A complete observation refines expanding manifest patterns
to the repository inputs actually consumed. The committed `HEAD` manifest
remains the policy authority, so a malformed or changed working-tree copy
cannot narrow it; if the check itself reads that copy, the observation records
it and its content change still invalidates the receipt.

## The 500-case matrix

There are 100 semantic mutations crossed with five manifest states:

| Fixture | Language/runtime | Semantic mutations | Matrix cases |
| --- | --- | ---: | ---: |
| Python service | Python `unittest` | 20 | 100 |
| Python package | Python `unittest` | 20 | 100 |
| Node CommonJS | Node test runner | 10 | 50 |
| Node ESM | Node test runner | 10 | 50 |
| C project | GCC compile + native binary | 20 | 100 |
| Java project | JDK 21 compile + JVM | 20 | 100 |
| **Total** | **4 languages, 6 repositories** | **100** | **500** |

The semantic mutations contain 40 safe changes and 60 changes that invalidate
old evidence. Across five manifest states, that becomes 200 reuse-safe cases
and 300 must-rerun cases. They cover:

- files the verification command never reads;
- behavior-preserving edits to direct, shared, configuration, and test inputs;
- behavior-breaking edits to those same inputs; and
- environment changes read by the test process.

Behavior-preserving relevant edits are still `reuse_safe: false`: a passing
rerun does not retroactively make stale evidence valid.

## Running it

From the repository root:

```text
python3 -m benchmarks.evidence_reuse
python3 -m benchmarks.evidence_reuse --json
```

Focused runs are available for diagnosis:

```text
python3 -m benchmarks.evidence_reuse --manifest exact
python3 -m benchmarks.evidence_reuse --profile c-native
python3 -m benchmarks.evidence_reuse --profile java-jdk
```

Python, Node.js, and GCC must be installed. Java uses local `javac`/`java`
when available. Otherwise it uses a network-disabled container based on a
digest-pinned Temurin JDK 21 image. The image is never pulled implicitly:

```text
python3 -m benchmarks.evidence_reuse --pull-java-image
```

The benchmark normally exits successfully after producing a report, including
when a stress case exposes unsafe reuse. Use `--fail-on-unsafe` when an unsafe
reuse should fail CI.

## Reading the report

The report leads with the clean `exact` baseline and shows the complete stress
matrix separately. Its key numbers are:

- **Correct reuse:** a semantically irrelevant change reused old evidence.
- **Correct invalidation:** a relevant change caused verification to rerun.
- **Unsafe reuse:** a relevant change incorrectly trusted old evidence.
- **Unnecessary rerun:** an irrelevant change reran verification; safe, but
  slower.
- **Shadow pass/fail:** what the real verification command did when rerun. This
  is an observation, not the oracle.

The target result for the full matrix is 200/200 safe reuse opportunities
taken, 300/300 relevant changes rerun, zero unsafe reuse, and zero unnecessary
reruns. This target still fails closed whenever runtime observation is absent,
failed, external, or incomplete across the process tree.

The JSON report also includes per-manifest, per-language, per-fixture, and
per-semantic-class breakdowns plus every case's separate `oracle`, `decision`,
`baseline_observation`, and `actual_rerun` objects.

This is a controlled synthetic benchmark. Its 500 matrix cells are not 500
independent production repositories, and its fixture observer is a controlled
input source rather than an operating-system tracer. The score therefore tests
receipt merge and decision semantics, not real-world tracing completeness or a
production failure probability. A later shadow-telemetry phase can feed the
same receipt builder and decision/reporting layer with production observations.
