"""Stays app package bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

__all__: list[str] = []


def _ensure_shared_lib_on_path() -> None:
    """Add libs/superapp_shared to sys.path for app and tests.

    Keeps imports stable when running tests or scripts directly from the app
    directory without relying on external PYTHONPATH configuration.
    """
    try:
        root = Path(__file__).resolve().parents[3]
    except IndexError:
        return
    libs_dir = root / "libs"
    if not libs_dir.exists():
        return
    for child in libs_dir.iterdir():
        if not child.is_dir():
            continue
        direct_init = child / "__init__.py"
        nested_init = child / child.name / "__init__.py"
        if direct_init.exists() or nested_init.exists():
            target = child
        else:
            continue
        path_str = str(target)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


_ensure_shared_lib_on_path()
