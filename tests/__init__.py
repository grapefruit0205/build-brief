"""Support both discovery and package-qualified unittest invocation."""

import sys

from . import click_gate_test_support


sys.modules.setdefault("click_gate_test_support", click_gate_test_support)
