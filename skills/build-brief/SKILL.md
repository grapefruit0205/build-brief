---
name: build-brief
description: When explicitly invoked for a software design or change, translate natural-language intent and repository context into the smallest sufficient developer Design Contract, explain the same contract plainly, and wait for approval before implementation. Never invoke implicitly and never turn the contract into a task plan, phases, or execution steps.
---

# Build Brief

Translate the user's natural-language intent and actual repository context into the software-design language this situation needs. Build Brief is a semantic compiler, not a chooser over fixed architecture labels and not a project-planning system.

## Keep the product boundary exact

Build Brief owns only:

- recovering the requested behavior and consequential constraints;
- discovering the narrow repository evidence needed to resolve them;
- compiling an authoritative developer-facing Design Contract;
- deriving a faithful plain-language explanation of that same contract;
- asking the user to approve, revise, simplify, or cancel the contract.

Do not emit implementation phases, numbered steps, task lists, work breakdowns, or execution order. After approval, the ordinary coding workflow decides how to plan and perform the work while treating the approved Design Contract as binding.

## Activate only when explicitly selected

- Activate when the user selects Build Brief or explicitly invokes `$build-brief` for the current work.
- Do not infer activation because a request is large, architectural, vague, risky, or consequential.
- A question about Build Brief is not an invocation to apply it.
- Do not activate when the user asks to proceed without Build Brief.
- If the user opts out after the current turn was armed, run `build-brief-gate bypass` when needed and immediately return to the ordinary workflow.

Users do not need to choose architecture vocabulary. Infer the relevant design language from the requirement and repository. Enable session-wide strict mode only when the user explicitly asks, with `build-brief-gate mode strict`; leave it with `build-brief-gate mode adaptive`.

## Preserve meaning and authorization

- Treat the requested outcome, scope, product decisions, and authorization as authoritative.
- Use the codebase's boundaries, domain language, runtime, data model, dependencies, failure handling, and tests.
- Do not treat an existing project as a blank system.
- Do not translate a request into permission for a rewrite, migration, new service, or wider product.
- Do not invent scale, latency, organization, deployment, compliance, or compatibility requirements.
- Do not add abstractions or infrastructure for hypothetical future use.

## Inspect from the narrowest evidence frontier

Start at the behavior named by the request. Locate its owning entry point, state or data owner, external contracts, and focused tests. Widen inspection only while a consequential behavior remains unresolved. Do not scan the whole repository or create a complete architecture map by default.

Stop when the owning boundary, observable behavior, material system semantics, minimum justified design delta, and completion evidence are known well enough to form the contract without a consequential guess.

For broad or cross-boundary work with non-obvious state, failure, compatibility, or handoff semantics, read [references/translation-guide.md](references/translation-guide.md).

## Compile the authoritative Design Contract

Use whatever software-engineering language makes the request precise. Relevant language may come from domain modeling, state transitions, contracts, concurrency, consistency, failure handling, data lifecycle, security, performance, observability, migration, or another discipline. This vocabulary is open-ended.

The developer-facing contract must contain:

- **Boundary:** the current component, data owner, or external contract that owns the behavior.
- **Invariants:** observable requirements and facts that must remain true.
- **System semantics:** only the responsibilities, state, data ownership, flow, timing, ordering, concurrency, consistency, failure, security, compatibility, migration, and operational meaning that materially preserve the invariants.
- **Minimality:** existing boundaries and mechanisms to reuse, plus present evidence for every material new design element.
- **Proof:** observable acceptance criteria and focused evidence that would demonstrate the behavior.

These are design obligations, not an ordered implementation sequence. Do not add an `implementation`, `steps`, `phases`, `tasks`, `plan`, or `execution_order` section.

The contract is ready only when consequential behavior no longer depends on an unstated guess, each design term changes an invariant or implementation constraint, and no larger design is chosen when a smaller one preserves the same invariants.

## Explain the same contract plainly

Read [references/directive-format.md](references/directive-format.md) whenever a contract will be shown to the user.

Place a short plain-language explanation before the developer contract. Explain what the resulting software will do, why the important safeguards exist, what remains unchanged, and any material failure or tradeoff the user is approving.

The explanation is a human-readable projection of the contract, not a second design:

- introduce no decision, guarantee, assumption, or scope absent from the developer contract;
- omit no material invariant, compatibility promise, failure behavior, or justified new design element;
- translate necessary technical terms in context rather than removing their consequences;
- regenerate the explanation whenever the developer contract changes.

If the two views disagree, neither is ready for approval. The developer-facing contract is authoritative, while the plain explanation lets the user understand what that contract means.

## Require approval before implementation

For an explicitly invoked build or change request:

- run `build-brief-gate arm` before any mutation; read-only inspection remains available;
- show the plain-language explanation and the developer-facing Design Contract;
- ask whether the user approves, wants a revision, wants a simpler explanation, or wants to cancel;
- stop without passing the gate or modifying code, tests, configuration, schemas, or other local files.

Do not treat the original request, a request to "build it," or approval given before the contract was shown as approval of the compiled contract.

After the user explicitly approves the displayed contract, arm the new turn and run `build-brief-gate pass '<JSON>'` with the exact approved meaning before the first mutation. Then hand control to the ordinary coding workflow. If the user requests a design revision, update the developer contract, regenerate its plain explanation, and request approval again. If the user asks only for an easier explanation, keep the developer contract unchanged, rewrite its plain-language view faithfully, and request approval again. If the user cancels, do not implement.

Use a compact JSON object with:

- `plain_language`: the faithful, non-empty plain-language explanation;
- `boundary`: a non-empty string;
- `invariants`: a non-empty list of observable requirements;
- `system_semantics`: a non-empty list of developer-facing design obligations;
- `minimality`: a non-empty list naming reused structure and justifying each material addition, or stating that none is introduced;
- `proof`: a non-empty list of acceptance criteria or focused completion evidence.

The Hook records only a digest outside the repository. It validates contract shape and mutation ordering, not the truth of the design or the authenticity of human approval; the Skill must preserve that interaction boundary. If the Hook is disabled or untrusted, follow the same ordering at instruction level and disclose that runtime enforcement was inactive.

A design-only, review-only, or handoff-only request makes no mutation. Show the paired explanation and contract, honor the requested deliverable, and do not manufacture an implementation plan.

## Enforce minimum-sufficient design

Required behavior and invariants are the correctness gate. Among candidates that satisfy them, choose the smallest justified design delta and maximize reuse of the current system.

A new deployable unit, store, queue or asynchronous boundary, public contract, framework or dependency, abstraction layer, configuration surface, or operational component belongs only when a current requirement or repository fact requires it, the existing structure cannot preserve an invariant with a smaller change, the prevented failure is concrete, and focused proof is available.

Hypothetical scale, future reuse, imagined teams, and fashionable vocabulary are not evidence. Do not remove necessary concurrency, safety, compatibility, or failure behavior merely to make the design look smaller.

## Resolve ambiguity proportionally

Ask the smallest question only when the answer changes public behavior, cost, data safety, security, or a difficult-to-reverse decision. Otherwise use a conservative, reversible assumption and expose it when consequential. Never ask the user to choose technical vocabulary that repository evidence can resolve.

## Communicate plainly

- Use the user's language and level of technical detail.
- Lead with the easy explanation, followed by the authoritative developer contract.
- Prefer concrete invariants and consequences over architecture slogans.
- When asked to explain more simply, simplify the explanation without weakening or changing the contract.
