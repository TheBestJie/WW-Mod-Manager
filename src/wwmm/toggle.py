"""Enable/disable mods by renaming only the top-level folder."""

from __future__ import annotations

import errno
import logging
import os
from pathlib import Path

from wwmm.constants import DISABLED_PREFIX
from wwmm.errors import ToggleError
from wwmm.models import Mod

log = logging.getLogger(__name__)


def _error_message(exc: OSError, folder_name: str) -> str:
    if exc.errno in (errno.EACCES, errno.EPERM):
        return f"没有权限重命名 {folder_name}：{exc.strerror}"
    if exc.errno == errno.ENAMETOOLONG:
        return f"文件夹名过长，无法重命名 {folder_name}"
    if exc.errno == errno.ENOENT:
        return f"mod 文件夹不存在：{folder_name}"
    return f"重命名失败：{exc.strerror or exc}"


def toggle_mod(mod: Mod, enable: bool | None = None) -> Mod:
    """Rename a mod folder to add/remove one DISABLED_ prefix.

    Never deletes or overwrites anything. On error the filesystem is unchanged.
    """
    if enable is None:
        enable = not mod.enabled

    base_name = mod.base_name
    if not base_name:
        raise ToggleError(f"mod 文件夹名为空，无法重命名：{mod.path}")

    target_name = base_name if enable else DISABLED_PREFIX + base_name
    target = Path(mod.path).with_name(target_name)

    if target.exists() or target.is_symlink():
        raise ToggleError(f"目标已存在：{target}")

    try:
        os.rename(mod.path, target)
    except OSError as exc:
        raise ToggleError(_error_message(exc, mod.folder_name)) from exc

    log.info("mod 重命名：%s → %s", mod.folder_name, target_name)
    return Mod(
        path=target,
        folder_name=target_name,
        enabled=enable,
        ini_count=mod.ini_count,
    )
