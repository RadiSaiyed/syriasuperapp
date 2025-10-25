from __future__ import annotations

import os
from typing import Iterable, List

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name: str, *, default: bool = False) -> bool:
    """
    Read an environment variable as a boolean.

    Accepts common truthy/falsy strings; raises if the value cannot be parsed.
    """
    value = os.getenv(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean for {name!r}: {value!r}")


def env_list(name: str, *, default: Iterable[str] | None = None, separator: str = ",") -> List[str]:
    """
    Read a delimited list from an environment variable.

    Empty and missing values resolve to the provided default.
    """
    value = os.getenv(name)
    if value is None:
        if default is None:
            return []
        return [item for item in default]
    items = [item.strip() for item in value.split(separator)]
    return [item for item in items if item]


__all__ = ["env_bool", "env_list"]
