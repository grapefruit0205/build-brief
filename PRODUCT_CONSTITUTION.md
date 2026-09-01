# Click Product Constitution

Status: **Canonical**

Effective: **2026-08-31**

> **Click binds AI execution to approved intent and returns verifiable evidence.**
>
> **Click은 사용자가 승인한 의도에 AI 실행을 결속하고, 실제 수행 증거를 돌려준다.**

This document defines the stable product boundary for Click. Runtime behavior,
documentation, tests, host adapters, and future features must remain consistent
with it.

## Core purpose

Click is an authorization-and-evidence runtime for AI execution. It binds a
canonical statement of user intent to a later approval, mediates observable
mutations and external side effects, and records evidence that is tied to the
execution revision. When Click directly runs argv verification, it records a
stronger receipt for the protected workspace, environment, and executable that
produced the result.

Click Core does not decide how a capable model should explore, plan, or choose
the best implementation or verification strategy. It supplies guarantees that
remain necessary even if the model is perfect.

## Core admission test

A feature may enter Click Core only when the answer to **all three** questions
is yes:

1. Would an external guarantee still be necessary if the model were perfect?
2. Can the runtime observe the relevant action or result?
3. Would failure threaten authority, side-effect control, or evidence integrity?

If any answer is no, the feature does not belong in Core. Hidden reasoning,
semantic guesses, and model-quality assumptions are not runtime observations.

## Policy layers

### CORE

Cross-model, cross-host invariants that may fail closed because they protect
authority, side effects, or evidence integrity. Core behavior must be grounded
in an observable event or result and covered by deterministic tests.

### USER_POLICY

Optional restrictions or budgets that the user explicitly selects or approves.
Core may enforce an approved policy value exactly, but selecting the value is
not itself a Core judgment. A user policy must not silently become a universal
product invariant.

### HEURISTIC

Advice, telemetry, or experimental strategy intended to improve model workflow.
Heuristics must not grant authority, manufacture evidence, mark work complete,
or hard-block otherwise authorized execution. They may be tuned per model or
host without changing Click's constitutional guarantees.

## Core guarantees

Click Core owns:

- binding later user approval to the exact canonical contract digest;
- controlling authority for mutations and observable external side effects;
- binding one-use runners to the exact approved action and request;
- preventing cancellation bypass, replay, token substitution, and state tampering;
- binding every evidence ledger entry to the contract and mutation revision;
- binding argv verification receipts additionally to the protected workspace
  state, execution environment, and executable identity;
- invalidating stale evidence when the protected implementation changes;
- recovering outstanding approved runner state without weakening exact binding,
  expiry, cancellation, or replay checks;
- preserving auditable current authorization state and evidence receipts;
- exporting a deterministic completion receipt that binds approval, observable
  capability claims, the final workspace revision, and evidence lineage; and
- adapting Codex, Antigravity, and other hosts onto the same Core protocol.

Host adapters may normalize host events and output formats. They may not weaken
the Core identity, authorization, runner-binding, or receipt invariants.

## Outside Core

The following are not Click Core responsibilities:

- the model's file-exploration order;
- forced blocking of duplicate reads;
- repository-wide scan counts;
- replan counts or plan-tool usage;
- choosing the optimal verification strategy;
- model-specific workflow tuning; and
- a large context scheduler.

These features may exist as explicit `USER_POLICY`, non-blocking `HEURISTIC`, or
isolated experiments. They must not be presented as universal runtime security
or evidence guarantees.

## Constitutional execution chain

```text
approved intent
    -> canonical contract digest
    -> later user authorization
    -> exact one-use execution request
    -> observable action or side effect
    -> contract- and revision-bound evidence record
    -> stronger tree-, environment-, and executable-bound argv receipt
    -> canonical completion receipt with capability-claim lineage
    -> auditable current state and receipts
```

The runtime can prove only the observable bindings in this chain. It cannot by
itself prove that natural-language approval was semantically informed, that a
natural-language scope matches every changed line, or that an unmatched manual
or external attestation is true. The current implementation maintains an
append-only capability-claim ledger for one contract and can export its
unsigned completion receipt; it does not yet provide a signed, independently
authentic durable history of every state transition.

## Change rule

Every proposal for a new Core hard gate must document:

1. the observable event or result;
2. the authority, side-effect, or evidence invariant it protects;
3. the concrete failure if it is omitted;
4. why all three Core admission questions are answered yes; and
5. deterministic tests for allow, deny, replay, tampering, cancellation, and
   recovery paths as applicable.

Classification alone does not change shipped behavior. Moving an existing guard
between layers requires a separate behavior change with regression tests and
matching documentation. The current inventory and migration order live in
[GUARD_CLASSIFICATION.md](GUARD_CLASSIFICATION.md).
