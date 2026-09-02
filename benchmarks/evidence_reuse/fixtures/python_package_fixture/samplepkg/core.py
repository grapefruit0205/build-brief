import json
import os
from pathlib import Path

from .settings import MULTIPLIER
from .shared import normalize


_DATA = json.loads(
    (Path(__file__).parent / "data.json").read_text(encoding="utf-8")
)


def compute(value: int) -> int:
    return value * MULTIPLIER


def message(name: str) -> str:
    return f"{_DATA['prefix']} {normalize(name)}"


def mode_label() -> str:
    return os.environ.get("CLICK_BENCH_MODE", "test")
