from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_hook() -> None:
    path = ROOT / "hooks" / "click_gate.py"
    text = path.read_text(encoding="utf-8")
    old = '''def _consume_user_authorization(event: dict[str, Any], expected: str) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        return f"Click {expected} requires a current Codex turn_id."
    state = _read_user_prompt_state(event)
    if str(state.get("turn_id", "")) != turn_id:
        return (
            f"Click {expected} requires an exact first-line `@Click {expected}` "
            "directive in this user turn."
        )
    if state.get("authorization") != expected:
        return (
            f"Click {expected} requires an exact first-line `@Click {expected}` "
            "directive in this user turn."
        )
    state["authorization"] = ""
    state["updated_at"] = int(time.time())
    _write_json(_prompt_path(event), state)
    return ""
'''
    new = '''def _consume_user_authorization(event: dict[str, Any], expected: str) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        return f"Click {expected} requires a current Codex turn_id."
    with _state_lock():
        state = _read_user_prompt_state(event)
        if str(state.get("turn_id", "")) != turn_id:
            return (
                f"Click {expected} requires an exact first-line `@Click {expected}` "
                "directive in this user turn."
            )
        if state.get("authorization") != expected:
            return (
                f"Click {expected} requires an exact first-line `@Click {expected}` "
                "directive in this user turn."
            )
        state["authorization"] = ""
        state["updated_at"] = int(time.time())
        _write_json(_prompt_path(event), state)
    return ""
'''
    path.write_text(
        replace_once(text, old, new, "authorization consumption"), encoding="utf-8"
    )


def patch_tests() -> None:
    path = ROOT / "tests" / "test_click_gate.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from __future__ import annotations\n\nimport importlib.util\n",
        "from __future__ import annotations\n\nfrom concurrent.futures import ThreadPoolExecutor\nimport importlib.util\n",
        "ThreadPoolExecutor import",
    )
    text = replace_once(
        text,
        "import tempfile\nimport time\nimport unittest\n",
        "import tempfile\nimport threading\nimport time\nimport unittest\nfrom unittest import mock\n",
        "threading/mock imports",
    )
    anchor = "    def test_cancel_requires_authorization_and_clears_contract_once(self) -> None:\n"
    regression = '''    def test_authorization_consumption_is_atomic_under_state_lock(self) -> None:
        event = {
            **self.base_event,
            "turn_id": "turn-atomic",
            "prompt": "@Click bypass",
        }
        with mock.patch.dict(
            os.environ,
            {"PLUGIN_DATA": str(self.plugin_data)},
        ):
            CLICK_GATE._record_user_prompt(event)
            started = threading.Event()

            def consume() -> str:
                started.set()
                return CLICK_GATE._consume_user_authorization(event, "bypass")

            with ThreadPoolExecutor(max_workers=1) as executor:
                with CLICK_GATE._state_lock():
                    future = executor.submit(consume)
                    self.assertTrue(started.wait(timeout=1.0))
                    time.sleep(0.05)
                    self.assertFalse(future.done())
                self.assertEqual(future.result(timeout=2.0), "")

            reused = CLICK_GATE._consume_user_authorization(event, "bypass")
            self.assertIn("requires an exact first-line", reused)

'''
    text = replace_once(text, anchor, regression + anchor, "atomic authorization regression")
    path.write_text(text, encoding="utf-8")


def patch_counts() -> None:
    for relative in ("README.md", "README.ko.md", "RELEASE_NOTES.md"):
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if "139" not in text:
            raise RuntimeError(f"{relative}: expected 139 test count")
        path.write_text(text.replace("139", "140"), encoding="utf-8")


def main() -> None:
    patch_hook()
    patch_tests()
    patch_counts()


if __name__ == "__main__":
    main()
