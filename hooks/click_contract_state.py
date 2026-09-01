#!/usr/bin/env python3
"""Contract-state persistence shared by Click runtime domains.

This leaf owns only the canonical contract JSON read, atomic save, and clear
operations.  Contract construction and lifecycle transitions remain in their
own domains.
"""

from __future__ import annotations

import json
import time
from typing import Any

if __package__:
    from . import click_import_bootstrap
else:  # Imported from a directly executed bundled hook.
    import click_import_bootstrap


(click_state,) = click_import_bootstrap.load_siblings(__package__, "click_state")


EMPTY_CONTRACT_STATE = {"status": "none", "contract_digest": ""}


def read_contract_state(event: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(
            click_state.contract_path(event).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(EMPTY_CONTRACT_STATE)
    return value if isinstance(value, dict) else dict(EMPTY_CONTRACT_STATE)


def save_contract_state(event: dict[str, Any], state: dict[str, Any]) -> None:
    state["updated_at"] = int(time.time())
    click_state.write_json(click_state.contract_path(event), state)


def clear_contract_state(event: dict[str, Any]) -> None:
    try:
        click_state.contract_path(event).unlink()
    except OSError:
        pass
