import json
import os
from pathlib import Path

from config import TAX_RATE
from shared import normalize_name


_DATA = json.loads(
    (Path(__file__).parent / "fixture_data.json").read_text(encoding="utf-8")
)


def total_with_tax(amount: float) -> float:
    return round(amount * (1 + TAX_RATE), 2)


def greeting(name: str) -> str:
    return f"Hello, {normalize_name(name)}!"


def fixture_label() -> str:
    return str(_DATA["label"])


def mode_label() -> str:
    return os.environ.get("CLICK_BENCH_MODE", "test")
