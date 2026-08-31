# Click Guard Classification

Status: **Living inventory; v0.30 policy migrations complete; dependency-aware receipt reuse completed for v0.31.0; host coverage identity completed for v0.32.0**

Baseline: **v0.24.6 plus the canonical product-boundary change at `73072a9`**

This document applies the [Click Product Constitution](PRODUCT_CONSTITUTION.md)
to the guards shipped in the baseline above and tracks migrations made after
that point. It records current ownership and remaining migration intent; it does
not claim that every hard gate has already been moved to its target layer.

## CORE

| Guard or invariant | Current owner | Why it remains Core |
| --- | --- | --- |
| Canonical contract validation, digest and ID binding, later-turn approval, session and working-directory identity | `hooks/click_contract.py`; approval lifecycle in `hooks/click_gate.py` | Prevents mutation under an unapproved or substituted intent |
| Mutation and external side-effect authorization | mutation paths in `hooks/click_gate.py`; managed-service prepare/claim/record paths in `hooks/click_service.py` | Controls observable effects rather than model strategy |
| Exact one-use runner token, action, request, root and state binding | managed-service claims in `hooks/click_service.py`; remaining runner claim paths in `hooks/click_gate.py` | Prevents replay, request substitution and cross-state execution |
| Canonical state paths, locks, atomic writes and authorized state-root recovery | `hooks/click_state.py` | Preserves approval state across failure without weakening identity checks |
| Cancellation, expiry, consumed-runner and tampering revocation | `hooks/click_state.py`; lifecycle branches in `hooks/click_gate.py` | Prevents stale authority from becoming executable again |
| Evidence registry identity, current-revision state and receipt matching | `hooks/click_evidence.py`; verification claim/result paths in `hooks/click_gate.py` | Prevents evidence from a different request or revision from completing work |
| Browser source admission, serial-call interlock, stable host-call/result mapping, current revision and finalization replay | `hooks/click_browser.py`; host routing in `hooks/click_gate.py` | Prevents an unassigned, parallel, mismatched, stale or replayed Browser result from completing evidence without judging the model's interaction strategy |
| Protected Git-tree, environment and executable fingerprints for argv verification; verification-time mutation detection | verification receipt helpers and runners in `hooks/click_gate.py` | Preserves the identity of the code and environment actually checked by Click's argv runner |
| Opt-in dependency provider, relevant-entry and resolved-path receipts, plus approved mutation pre/post binding | `hooks/click_dependency_cache.py`; mutation-boundary and receipt transitions in `hooks/click_gate.py` | Allows cross-revision reuse without treating a model's post-approval assertion, unrelated manifest content, or later workspace drift as proof |
| Direct-argv capability safety, executable/path/environment checks, process-control rejection and read-only side-effect defenses | capability constants and validators in `hooks/click_gate.py` | Prevents an admitted inspect, verify or service request from gaining unapproved effects |
| Mutation, verification and managed-service interlocks around active runner claims | managed-service reservation and claim state in `hooks/click_service.py`; remaining runner state in `hooks/click_gate.py` | Prevents an authorized side effect or receipt from racing into a different state without treating distinct observation concurrency as authority |
| Host coverage identity, event normalization and state/receipt-preserving result mapping | `hooks/click_host_coverage.py`, `hooks/click_hook.py`, `hooks/antigravity_gate.py`, `hooks/platform_protocol.py` | Keeps the known pre/post surface symmetric and prevents verification receipts from crossing a host or coverage-registry revision while making the limited assurance explicit |

## USER_POLICY

| Policy | Current owner | Constitutional boundary |
| --- | --- | --- |
| Always ON, Manual, review and bypass availability | mode state and `skills/click/references/modes.md` | Choosing the mode is policy; exact one-use enforcement after selection is Core |
| An explicit numeric verification budget | Not currently implemented | A numeric ceiling becomes policy only when the user deliberately opts into that exact restriction; Click's built-in profile suggestions are not a substitute for user choice |
| Acceptance of hosted, manual or existing attestations | evidence-completion handling in `hooks/click_gate.py` | Acceptance must be explicit and must not be described as independent proof |

## HEURISTIC

| Current strategic guard | Current owner | Target behavior |
| --- | --- | --- |
| Advising on a repeated successful read or search and on repeated incomplete/failing reads | observation preparation in `hooks/click_gate.py` | Advisory only — fresh separately authorized repeats use a new one-use runner; an active same-digest reservation remains a Core interlock |
| Advising after broad repository inventory | broad-exploration classifiers, observation preparation and host adapters | Advisory only — cross-digest running/success hard denial removed in v0.30.0; active same-digest reservations and execution interlocks remain separate |
| Advising on `update_plan` or equivalent host plan tools | plan-tool branch in `hooks/click_gate.py`; host matchers and adapters | Advisory only — hard denial removed in v0.30.0 |
| Choosing the proposed evidence source and qualitative verification profile before approval, concrete argv during execution, and the cheapest proof strategy | Skill, eval and documentation policy | Model strategy or an explicit user constraint; Click records the choice but does not interpret it as runtime authority |
| Legacy verification class-unit values | `hooks/click_verification_policy.py` and `hooks/click_verification_meter.py` | Compatibility data only — they do not produce runtime advice, prove cost or sufficiency, or participate in receipt authority |
| Requiring a mutation after a fixed number of otherwise legitimate failed retries | argv verification and Browser retry handling | Advisory only in v0.30.0; fresh authorization remains distinct from replay of an active or consumed runner |
| Browser repeat/retry guidance, preferred timing thresholds and interaction-history depth | `hooks/click_browser_advisory.py`; bounded history compaction in Browser preparation | Advisory only — normalized repeats and long timed interactions remain receipt-bound and allowed; old per-input guidance is compacted instead of blocking a new call |
| Contract compactness, planning prose and workflow-shape preferences beyond parser or transport safety | `hooks/click_contract.py` schema policy | Keep only identity-bearing protocol fields in Core |
| Main Skill authoring compactness | reference split, plugin validation and review | Heuristic documentation quality — no word-count permission gate; required links and protocol structure remain testable without optimizing prose to an arbitrary number |

## Mixed guards that must be split carefully

- Plan-tool guidance is `HEURISTIC`; preventing replacement or widening of an
  approved contract without new approval is `CORE`.
- Broad-inventory count and scope are `HEURISTIC`; exact request identity,
  one-use runner claims, mutation and verification interlocks are `CORE`.
- Selecting verification breadth and interpreting its cost is `HEURISTIC`
  unless the user explicitly constrains it; exact argv, evidence ID, revision,
  check-group reservation and receipt binding are `CORE`. Legacy class
  normalization is compatibility behavior, not a receipt fact, and does not
  deny or advise on an otherwise authorized check.
- Read path, environment, pager, text-conversion and executable-shadow defenses
  are `CORE`; the supported command surface is an implementation compatibility
  choice, and deciding that a read is too broad is `HEURISTIC`.
- Reusing the same one-use runner token is a `CORE` replay violation; limiting
  fresh, separately authorized retries is `HEURISTIC`.
- A verification command that observably changes protected repository content
  violates the read-only evidence boundary and remains `CORE`; limiting fresh
  retries of an ordinary failing argv check is `HEURISTIC`.
- Browser source and current-revision accounting in `hooks/click_browser.py` are
  `CORE` when the host event is observable; duplicate-input and call-count
  tuning in `hooks/click_browser_advisory.py` are `HEURISTIC`.
- The contract digest and approval identity are `CORE`; required planning prose
  and judgments about whether a contract is concise are not.

## Known assurance gaps

- The Hook proves a later user turn and the exact staged ID, while the Skill and
  model still interpret whether the user's words semantically grant approval.
- Natural-language `boundary.in_scope` is digest-bound but is not semantically
  compared with every resulting diff by the runtime.
- Direct `apply_patch`, Edit and Write surfaces receive approval gating,
  revision tracking, and observable pre/post Git snapshots, but they do not use
  the structured runner's one-use request digest. Changes racing inside one
  approved host-tool interval cannot be attributed independently without an
  operating-system monitor.
- Hosted, manual and existing evidence completion is an agent attestation, not
  an independently observed external fact.
- Browser success proves an observed tool result and source binding, not the
  truth of an arbitrary natural-language completion condition.
- Host coverage receipts assert `known-surfaces-only`: they fingerprint the
  configured events Click knows how to consume, but cannot prove that a host
  emitted an event for every capability it may expose.
- Current state and receipts are inspectable, but Click does not keep an
  append-only durable history of every authorization and evidence transition.

## Operational limits requiring disposition

Hardcoded request, command and retained-state size thresholds are operational
constraints, not automatically `USER_POLICY`. Each limit must either document
the observable availability or integrity invariant that qualifies it as a Core
implementation safeguard, become an explicitly configured user policy, or stop
hard-blocking. They must not be promoted as product identity merely because the
current implementation enforces them.

For v0.30.0, contract prose length, verification check count, and the former
6,000-character raw capability threshold stop hard-blocking. Inspection retains
an eight-command cap because one request is one atomic read-runner claim with
bounded output exposure. Decoded transport, actual Windows command-line, argv,
output and retained-state bounds remain implementation safeguards to review
against the same rule rather than workflow-quality judgments.

These gaps must remain explicit. Marketing and documentation must not claim a
stronger guarantee than the runtime can observe.

## Migration order

1. **Complete:** Treat the v0.24.6 state-root recovery, distribution, tests and release as complete.
2. **Complete:** Establish this classification without changing behavior.
3. **Complete in v0.30.0:** Convert plan-tool hard denial to advisory output.
4. **Complete in v0.30.0:** Convert broad-inventory counting to advisory output while retaining active exact-digest reservations and Core execution interlocks.
5. **Complete in v0.30.0:** Convert fresh duplicate-read and fixed legitimate argv-retry denials to advisory output while retaining active-runner and verification-time mutation denials.
6. **Complete in v0.30.0:** Separate model-selected verification strategy, qualitative profile metadata, legacy unit compatibility, and exact receipt binding; remove plugin-authored cumulative ceilings and numeric overage advice from runtime authority.
7. **Complete in v0.30.0:** Separate Browser source, serial-call,
   result, revision and replay integrity from non-blocking repeat, retry and
   timing guidance.
8. **Complete in v0.30.0:** Update Skill, evals, manifest, README and
   host distributions together with the behavior they describe.
9. **Complete in v0.31.0:** Add approval-bound, dependency-aware cross-revision
   argv receipt reuse with exact check, environment, executable, relevant
   manifest entry, resolved-path and mutation-boundary invalidation.
10. **Complete in v0.32.0:** Centralize the known Codex and Antigravity Hook
    surface, test pre/post symmetry, and bind that limited coverage identity to
    argv verification runners and receipts.

Each migration is a separate behavior-preserving-for-Core change. It must retain
approval, side-effect authority, one-use runner, revision, receipt, cancellation,
replay, tampering, recovery, current-state and receipt tests.
