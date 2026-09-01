# Click Gate compatibility surface

Status: transitional architecture boundary, baselined from v0.36.0.

`hooks/click_gate.py` is the executable facade for Codex and the shared host
runtime used by the bundled Antigravity adapter. Domain behavior belongs in the
`click_*` modules below that facade. The facade still exposes historical names
that predate those extractions; those names are migration debt, not a template
for new code.

## Supported user-facing surface

The supported product surface is the Hook and `click-gate` command protocol
documented in the README and capability protocol. Python names beginning with
an underscore are not a general public extension API.

## Transitional host-adapter bridge

The current host adapters still call a small, explicit set of gate symbols:

- `hooks/click_hook.py`: `main`
- `hooks/antigravity_gate.py`: `SHELL_CONTROL_PUNCTUATION`, `_emit`,
  `_handle_post_tool`, `_handle_pre_tool`, `_handle_prompt_submit`,
  `_handle_session_end`, `_is_read_only_bash`, `_set_output_adapter`, and
  `_windows_launcher_path_is_safe`
- `hooks/click_windows.py`: `WINDOWS_COMMAND_LINE_LIMIT`,
  `_encode_runner_transport`, `_runner_shell_command`,
  `_windows_launcher_path_is_safe`, and `_windows_shell_quote`

This bridge is compatibility state, not the desired final host API. A later
refactor should replace it with named host-routing and runner-transport
interfaces before removing the gate symbols.

## Documented legacy symbol

`click_gate._validate_contract` remains bound to
`click_contract.validate_contract` because an earlier extraction explicitly
promised that compatibility. Its removal requires a deliberate compatibility
decision and release note.

## Private module forwarders

The v0.36.0 facade contains **144 private module-forwarding bindings** such as
`_evidence_key = click_evidence.evidence_key`. Their exact names and owners are
recorded in `tests/click_gate_compatibility_baseline.py`.

These bindings follow four rules:

1. New domain code and tests import the owning module instead of adding another
   `click_gate._name` dependency.
2. The baseline must not grow merely to make a local test or adapter convenient.
3. Retargeting, adding, or removing a forwarder requires an explicit baseline
   diff so the compatibility effect is reviewable.
4. Removal happens only after real host callers and compatibility tests have
   migrated to the owning module or a formal host API.

The architecture test intentionally records the current debt without claiming
that all 144 names are supported forever. Its purpose is to make the surface
shrink deliberately and prevent accidental expansion.
