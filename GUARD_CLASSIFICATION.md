# Click Guard Classification

Status: **Living inventory; plan, inventory, and logical-repeat advisory migrations applied**

Baseline: **v0.24.6 plus the canonical product-boundary change at `73072a9`**

This document applies the [Click Product Constitution](PRODUCT_CONSTITUTION.md)
to the guards shipped in the baseline above and tracks migrations made after
that point. It records current ownership and remaining migration intent; it does
not claim that every hard gate has already been moved to its target layer.

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
| Mutation, verification and managed-service interlocks around active runner claims | runner reservation and claim state in `hooks/click_gate.py` | Prevents an authorized side effect or receipt from racing into a different state without treating distinct observation concurrency as authority |
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
| Advising on a repeated successful read or search and on repeated incomplete/failing reads | observation preparation in `hooks/click_gate.py` | Advisory only — fresh separately authorized repeats use a new one-use runner; an active same-digest reservation remains a Core interlock |
| Advising after broad repository inventory | broad-exploration classifiers, observation preparation and host adapters | Advisory only — cross-digest running/success hard denial removed in the v0.25 candidate; active same-digest reservations and execution interlocks remain separate |
| Advising on `update_plan` or equivalent host plan tools | plan-tool branch in `hooks/click_gate.py`; host matchers and adapters | Advisory only — hard denial removed in the v0.25 candidate |
| Choosing the proposed evidence source, verification scale or cheapest proof strategy before approval | Skill, eval and documentation policy | Model strategy or explicit user policy; runtime minimum-class enforcement of the approved ceiling remains Core |
| Requiring a mutation after a fixed number of otherwise legitimate failed retries | argv verification and Browser retry handling | Argv verification count is advisory in the v0.25 candidate; Browser tuning remains pending and may become advisory or explicit user policy |
| Browser wait thresholds, duplicate-input blocking, retry tuning, shadow-verification rules and interaction ceilings | Browser preparation and input validation | Advisory or explicit user policy |
| Contract compactness, planning prose and workflow-shape preferences beyond parser or transport safety | `hooks/click_contract.py` schema policy | Keep only identity-bearing protocol fields in Core |

## Mixed guards that must be split carefully

- Plan-tool guidance is `HEURISTIC`; preventing replacement or widening of an
  approved contract without new approval is `CORE`.
- Broad-inventory count and scope are `HEURISTIC`; exact request identity,
  one-use runner claims, mutation and verification interlocks are `CORE`.
- Selecting verification breadth and cost is `HEURISTIC` or `USER_POLICY`;
  exact argv, evidence ID, revision and receipt binding—and conservative
  minimum-class enforcement of the approved budget—are `CORE`.
- Read path, environment, pager, text-conversion and executable-shadow defenses
  are `CORE`; the supported command surface is an implementation compatibility
  choice, and deciding that a read is too broad is `HEURISTIC`.
- Reusing the same one-use runner token is a `CORE` replay violation; limiting
  fresh, separately authorized retries is `HEURISTIC`.
- A verification command that observably changes protected repository content
  violates the read-only evidence boundary and remains `CORE`; limiting fresh
  retries of an ordinary failing argv check is `HEURISTIC`.
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

1. **Complete:** Treat the v0.24.6 state-root recovery, distribution, tests and release as complete.
2. **Complete:** Establish this classification without changing behavior.
3. **Complete in the v0.25 candidate:** Convert plan-tool hard denial to advisory output.
4. **Complete in the v0.25 candidate:** Convert broad-inventory counting to advisory output while retaining active exact-digest reservations and Core execution interlocks.
5. **Complete in the v0.25 candidate:** Convert fresh duplicate-read and fixed legitimate argv-retry denials to advisory output while retaining active-runner and verification-time mutation denials.
6. Separate approved verification policy from automatic strategy and cost inference.
7. Separate Browser receipt integrity from Browser workflow tuning.
8. Update Skill, evals, manifest, README and host distributions together with the
   behavior they describe.

Each migration is a separate behavior-preserving-for-Core change. It must retain
approval, side-effect authority, one-use runner, revision, receipt, cancellation,
replay, tampering, recovery, current-state and receipt tests.
