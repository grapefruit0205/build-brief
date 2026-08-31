#!/usr/bin/env python3
"""Approved verification-scale policy for Click.

This leaf module owns only the scale values and numeric ceilings that become
USER_POLICY when the user approves a contract.  It does not choose a scale,
select evidence, inspect argv, infer check breadth, or execute verification.
"""

from __future__ import annotations


VERIFICATION_SCALES = ("quick", "focused", "full")
VERIFICATION_UNIT_LIMITS = {"quick": 1, "focused": 4, "full": 10}


def approved_unit_limit(scale: object) -> int | None:
    """Return the exact approved ceiling, or ``None`` for an invalid scale."""
    if not isinstance(scale, str):
        return None
    return VERIFICATION_UNIT_LIMITS.get(scale)
