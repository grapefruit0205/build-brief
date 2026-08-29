# Google Antigravity Runtime

This reference applies only to the generated Click for Antigravity package.

Locate the installed plugin root once from the active installation:

- workspace IDE: `.agents/plugins/click`
- global IDE: `~/.gemini/config/plugins/click`
- Antigravity CLI: `~/.gemini/antigravity-cli/plugins/click`

Whenever the shared Click instructions say `click-gate`, invoke the bundled
launcher instead:

```text
python3 "<plugin-root>/hooks/antigravity_gate.py" control <action> [value]
```

For example:

```text
python3 "<plugin-root>/hooks/antigravity_gate.py" control stage '<contract JSON>'
python3 "<plugin-root>/hooks/antigravity_gate.py" control pass ctr_<32hex>
python3 "<plugin-root>/hooks/antigravity_gate.py" control verify '<request JSON>'
```

The adapter keeps one execution epoch stable across Antigravity's repeated model
invocations. A fully idle `model_stop` closes that epoch. A new readable user
entry in `transcript.jsonl` plus the following `PreInvocation` creates the later
approval epoch. If no new user entry can be proved, the epoch does not advance
and pass fails closed. Never pass a contract before that boundary. As with
Codex, the Hook proves separation but the Skill remains responsible for
interpreting whether the user's response is approval.

Antigravity's documented Hook output cannot rewrite tool input, so use the
launcher for structured inspect, mutate, service, evidence, and verify
capabilities. Native file and search tools may still be used when relevant, but
their successful reads are not deduplicated by Click's local observation runner.
Do not declare Browser evidence: no Antigravity Browser tool is currently bound
to Click's Browser meter. Use the cheapest sufficient argv, hosted, manual, or
existing source instead.
