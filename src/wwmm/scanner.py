"""Scan the WWMI Mods tree into a grouped snapshot."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from wwmm.constants import DISABLED_PREFIX, GROUP_ORDER
from wwmm.errors import LayoutError
from wwmm.models import Character, CharacterEntry, Mod, Snapshot
from wwmm.roster import Roster

log = logging.getLogger(__name__)


def find_character_root(mods_root: Path) -> Path:
    mods_root = Path(mods_root)
    if mods_root.is_dir():
        for entry in mods_root.iterdir():
            if entry.is_dir() and entry.name.casefold() == "character":
                return entry
    raise LayoutError("Mods 目录下没有 character 子目录")


def count_ini_files(path: Path) -> int:
    total = 0
    for _root, dirnames, filenames in os.walk(path, followlinks=False):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        total += sum(1 for name in filenames if name.lower().endswith(".ini"))
    return total


def scan_mods_in(character_dir: Path) -> list[Mod]:
    mods: list[Mod] = []
    try:
        children = list(character_dir.iterdir())
    except OSError as exc:
        log.warning("无法读取角色目录 %s：%s", character_dir, exc)
        return mods

    for child in children:
        if child.name.startswith(".") or not child.is_dir():
            continue
        mods.append(
            Mod(
                path=child,
                folder_name=child.name,
                enabled=not child.name.startswith(DISABLED_PREFIX),
                ini_count=count_ini_files(child),
            )
        )
    mods.sort(key=lambda mod: (not mod.enabled, mod.base_name.casefold()))
    return mods


def scan(mods_root: Path, roster: Roster) -> Snapshot:
    character_root = find_character_root(mods_root)
    snapshot = Snapshot(mods_root=Path(mods_root))

    for character_dir in sorted(character_root.iterdir(), key=lambda p: p.name.casefold()):
        if character_dir.name.startswith(".") or not character_dir.is_dir():
            continue
        character = roster.by_folder(character_dir.name)
        if character is None:
            character = Character(
                slug=character_dir.name,
                name_zh=character_dir.name,
                name_en=character_dir.name,
                elements=(),
                folder=character_dir.name,
            )
        entry = CharacterEntry(
            character=character,
            path=character_dir,
            mods=scan_mods_in(character_dir),
        )
        snapshot.groups.setdefault(character.group, []).append(entry)

    for name in GROUP_ORDER:
        snapshot.groups.setdefault(name, [])
        snapshot.groups[name].sort(
            key=lambda entry: (
                not entry.has_mods,
                entry.character.name_zh,
                entry.character.slug,
            )
        )

    log.info(
        "扫描完成：%d 个角色目录，%d 个 mod（启用 %d）",
        len(snapshot.all_characters()),
        snapshot.total_mods,
        snapshot.enabled_mods,
    )
    return snapshot
