"""Copy text through desktop clipboard commands."""

from __future__ import annotations

import logging
import shutil
import subprocess

log = logging.getLogger(__name__)

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
                encoding="utf-8",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
        except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
            log.debug("剪贴板命令 %s 失败：%s", name, exc)
            continue
        if result.returncode == 0:
            return True
        log.debug("剪贴板命令 %s 退出码 %s", name, result.returncode)
    log.debug("没有可用的桌面剪贴板命令")
    return False
