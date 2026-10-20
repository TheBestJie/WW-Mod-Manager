"""Copy text through desktop clipboard commands."""

from __future__ import annotations

import shutil
import subprocess

_CANDIDATES = (
    ("wl-copy", ()),
    ("xclip", ("-selection", "clipboard")),
    ("xsel", ("--clipboard", "--input")),
)


def copy_with_command(text: str) -> bool:
    """Copy text with the first working desktop clipboard command."""
    for name, args in _CANDIDATES:
        executable = shutil.which(name)
        if executable is None:
            continue
        try:
            result = subprocess.run(
                [executable, *args],
                input=text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return True
    return False
