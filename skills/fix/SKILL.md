---
name: fix
description: When explicitly invoked with a software defect or unwanted behavior, translate the natural-language report and repository evidence into one compact repair contract, explain it plainly, then fix it in one approved shot. Never invoke implicitly.
---

# Fix

Use `$fix` only when the user explicitly selects it. Do not infer activation from words such as “bug,” “broken,” or “fix,” and do not promise a native `/fix` command. Read Click's [operating modes](../click/references/modes.md) for the exact arm, bypass, cancel, and resume rules. Run `click-gate arm` before staging and again before pass in every later approval or resume turn.

Trace the reported symptom to the narrowest owning behavior, relevant state, public contract, and focused evidence. Keep confirmed repository evidence separate from hypotheses. Resolve ordinary repair tactics yourself and expose only consequential assumptions in the contract instead of asking serial implementation questions.

Use Click's shared [contract format and approval lifecycle](../click/references/directive-format.md) and [verification profiles](../click/references/verification-profiles.md); do not duplicate their schema or evidence rules. Stage the repair JSON once, capture the emitted `contract_id` from `CLICK_CONTRACT_ID`, show that id with both contract views, ask once, and stop without editing. Only after explicit approval in a later user turn, run `click-gate pass ctr_<32hex>` with that id—never resend the contract JSON.

Then follow the shared [anti-loop policy](../click/references/anti-loop-policy.md) and [structured capability protocol](../click/references/capability-protocol.md). Repair continuously inside the approved semantic boundary, collect each assigned completion source once on the final relevant revision, and stop when the repair is proven. Pause only for missing authority, an uncovered irreversible or paid action, or a required change to the approved semantic contract.
