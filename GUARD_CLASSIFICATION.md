# Click Guard Classification

Status: **Initial inventory; no runtime behavior change**

Baseline: **`origin/main` at `388d3b6` after v0.24.6**

This document applies the [Click Product Constitution](PRODUCT_CONSTITUTION.md)
to the guards shipped in the baseline above. It records ownership and migration
intent; it does not claim that every current hard gate has already been moved to
its target layer.

## CORE

| Guard or invariant | Current owner | Why it remains Core |
| --- | --- | --- |
| Canonical contract validation, digest and ID binding, later-turn approval, session and working-directory identity | `hooks/click_contract.py`; approval lifecycle in `hooks/click_gate.py` | Prevents mutation under an unapproved or substituted intent |
| Mutation and external side-effect authorization | mutation and managed-service prepare/claim/record paths in `hooks/click_gate.py` | Controls observable effects rather than model strategy |
| Exact one-use runner token, action, request, root and state binding | runner claim paths in `hooks/click_gate.py` | Prevents replay, request substitution and cross-state execution |
| Canonical state paths, locks, atomic writes and authorized state-root recovery | `hooks/click_state.py` | Preserves approval state across failure without weakening identity checks |
| Cancellation, expiry, consumed-runner and tampering revocation | `hooks/click_state.py`; lifecycle branches in `hooks/click_gate.py` | Prevents stale authority from becoming executable again |
| Evidence registry identity, current-revision state and receipt matching | `hooks/click_evidence.py`; verification claim/result paths in `hooks/click_gate.py` | Prevents evidence from a different request or revision from completing work |
| Protected Git-tree, environment and executable fingerprints for argv verification; verification-time mutation detection | verification receipt helpers and runners in `hooks/click_gate.py` | Preserves the identity of the code and environment actually checked by Click's argv runner |
| Enforcement of an approved verification budget against observable argv, including minimum-class inference from the submitted command | verification request validation and preparation in `hooks/click_gate.py` | Prevents an underdeclared check from bypassing the user's approved ceiling |
| Direct-argv capability safety, executable/path/environment checks, process-control rejection and read-only side-effect defenses | capability constants and validators in `hooks/click_gate.py` | Prevents an admitted inspect, verify or service request from gaining unapproved effects |
| Concurrency interlocks for mutation, observation, verification and managed services | runner reservation and claim state in `hooks/click_gate.py` | Prevents an authorized action or receipt from racing into a different state |
| Host event normalization and state/receipt-preserving result mapping | `hooks/click_hook.py`, `hooks/antigravity_gate.py`, `hooks/platform_protocol.py` | Ensures observable host actions reach the same authorization protocol |

## USER_POLICY

| Policy | Current owner | Constitutional boundary |
| --- | --- | --- |
| Always ON, Manual, review and bypass availability | mode state and `skills/click/references/modes.md` | Choosing the mode is policy; exact one-use enforcement after selection is Core |
| Verification scale and numeric unit ceilings | `VERIFICATION_UNIT_LIMITS` and contract verification policy | Choosing or approving the ceiling is policy; Core measures the actual argv conservatively and enforces that value |
| Acceptance of hosted, manual or existing attestations | evidence-completion handling in `hooks/click_gate.py` | Acceptance must be explicit and must not be described as independent proof |

## HEURISTIC

| Current strategic guard | Current owner | Target behavior |
| --- | --- | --- |
| Blocking a repeated successful read or search and allowing only one unchanged retry | observation preparation in `hooks/click_gate.py` | Advisory or telemetry |
| Allowing one broad repository inventory per revision | broad-exploration classifiers and observation preparation | Advisory or explicit user policy |
| Blocking `update_plan` or counting replans | plan-tool branch in `hooks/click_gate.py` | Advisory only |
| Choosing the proposed evidence source, verification scale or cheapest proof strategy before approval | Skill, eval and documentation policy | Model strategy or explicit user policy; runtime minimum-class enforcement of the approved ceiling remains Core |
| Requiring a mutation after a fixed number of otherwise legitimate failed retries | verification and Browser retry handling | Advisory or explicit user policy |
| Browser wait thresholds, duplicate-input blocking, retry tuning, shadow-verification rules and interaction ceilings | Browser preparation and input validation | Advisory or explicit user policy |
| Contract compactness, planning prose and workflow-shape preferences beyond parser or transport safety | `hooks/click_contract.py` schema policy | Keep only identity-bearing protocol fields in Core |

## Mixed guards that must be split carefully

- Blocking the plan tool is `HEURISTIC`; preventing replacement of an approved
  contract without new approval is `CORE`.
- Selecting verification breadth and cost is `HEURISTIC` or `USER_POLICY`;
  exact argv, evidence ID, revision and receipt binding—and conservative
  minimum-class enforcement of the approved budget—are `CORE`.
- Read path, environment, pager, text-conversion and executable-shadow defenses
  are `CORE`; the supported command surface is an implementation compatibility
  choice, and deciding that a read is too broad is `HEURISTIC`.
- Reusing the same one-use runner token is a `CORE` replay violation; limiting
  fresh, separately authorized retries is `HEURISTIC`.
- Browser source and current-revision accounting are `CORE` when the host event
  is observable; duplicate-input and call-count tuning are `HEURISTIC`.
- The contract digest and approval identity are `CORE`; required planning prose
  and judgments about whether a contract is concise are not.

## Known assurance gaps

- The Hook proves a later user turn and the exact staged ID, while the Skill and
  model still interpret whether the user's words semantically grant approval.
- Natural-language `boundary.in_scope` is digest-bound but is not semantically
  compared with every resulting diff by the runtime.
- Direct `apply_patch`, Edit and Write surfaces receive approval gating and
  revision tracking but do not all use the structured runner's one-use request
  digest and result record.
- Hosted, manual and existing evidence completion is an agent attestation, not
  an independently observed external fact.
- Browser success proves an observed tool result and source binding, not the
  truth of an arbitrary natural-language completion condition.
- Current state and receipts are inspectable, but Click does not keep an
  append-only durable history of every authorization and evidence transition.

## Operational limits requiring disposition

Hardcoded request, command and retained-state size thresholds are operational
constraints, not automatically `USER_POLICY`. Each limit must either document
the observable availability or integrity invariant that qualifies it as a Core
implementation safeguard, become an explicitly configured user policy, or stop
hard-blocking. They must not be promoted as product identity merely because the
current implementation enforces them.

These gaps must remain explicit. Marketing and documentation must not claim a
stronger guarantee than the runtime can observe.

## Migration order

1. Treat the v0.24.6 state-root recovery, distribution, tests and release as complete.
2. Preserve this classification without changing behavior.
3. Convert plan-tool hard denial to advisory output.
4. Convert broad-inventory counting to advisory output.
5. Convert duplicate-read and fixed legitimate-retry denials to advisory output.
6. Separate approved verification policy from automatic strategy and cost inference.
7. Separate Browser receipt integrity from Browser workflow tuning.
8. Update Skill, evals, manifest, README and host distributions together with the
   behavior they describe.

Each migration is a separate behavior-preserving-for-Core change. It must retain
approval, side-effect authority, one-use runner, revision, receipt, cancellation,
replay, tampering, recovery, current-state and receipt tests.
