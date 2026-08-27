# Verification Profiles

Choose one scale and place it in the contract. Approval of the contract approves that scale.

| Scale | Use when | Final batch |
| --- | --- | --- |
| `quick` | The change is small, local, reversible, and has a narrow failure surface | The nearest meaningful check plus final diff/status inspection |
| `focused` | An ordinary feature or repair affects behavior but has a bounded owner | Direct behavior tests, the closest relevant regression checks, and final diff/status inspection |
| `full` | The work changes payments, authentication, authorization, deletion, migration, public contracts, concurrency across boundaries, or another high-impact surface | Available full suite plus relevant integration, migration, security, or end-to-end checks |

Use present evidence, not task size alone. `focused` is the normal recommendation. Do not inflate `quick` work into broad testing, and do not reduce high-impact work to `quick` merely to save time.

Run `done_when` checks together after implementation. Omit `intermediate_gate` normally. Name it only when continuing past a point would make recovery materially harder—for example applying an irreversible migration, deleting data, deploying, or spending money through an external API. A gate is a safety boundary, not a routine checkpoint.
