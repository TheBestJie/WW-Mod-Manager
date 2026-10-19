"""Runtime data models for WWMM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from wwmm.constants import DISABLED_PREFIX, GROUP_ORDER


@dataclass(frozen=True)
class Character:
    """A playable character from the roster."""

    slug: str
    name_zh: str
    name_en: str
    elements: tuple[str, ...] = ()
    folder: str = ""
    special: bool = False
    pinyin: str = ""
    initials: str = ""
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.folder:
            object.__setattr__(self, "folder", self.slug)

    @property
    def group(self) -> str:
        if len(self.elements) > 1:
            return "多属性"
        if not self.elements:
            return "其他" if self.special else "未分类"
        return self.elements[0]


@dataclass(frozen=True)
class Mod:
    """A single mod folder (direct child of a character folder)."""

    path: Path
    folder_name: str
    enabled: bool
    ini_count: int

    @property
    def base_name(self) -> str:
        return self.folder_name.removeprefix(DISABLED_PREFIX)

    @property
    def display_name(self) -> str:
        return self.base_name


@dataclass
class CharacterEntry:
    """A character together with the mods found in its folder."""

    character: Character
    path: Path
    mods: list[Mod] = field(default_factory=list)

    @property
    def has_mods(self) -> bool:
        return bool(self.mods)

    @property
    def enabled_count(self) -> int:
        return sum(1 for mod in self.mods if mod.enabled)

    @property
    def total_count(self) -> int:
        return len(self.mods)


@dataclass
class Snapshot:
    """A full scan of the Mods directory, grouped by element."""

    mods_root: Path
    groups: dict[str, list[CharacterEntry]] = field(
        default_factory=lambda: {name: [] for name in GROUP_ORDER}
    )
    scanned_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        for name in GROUP_ORDER:
            self.groups.setdefault(name, [])

    def find(self, slug: str) -> CharacterEntry | None:
        for entry in self.all_characters():
            if entry.character.slug == slug:
                return entry
        return None

    def all_characters(self) -> list[CharacterEntry]:
        seen: set[str] = set()
        result: list[CharacterEntry] = []
        for entries in self.groups.values():
            for entry in entries:
                if entry.character.slug in seen:
                    continue
                seen.add(entry.character.slug)
                result.append(entry)
        return result

    @property
    def total_mods(self) -> int:
        return sum(entry.total_count for entry in self.all_characters())

    @property
    def enabled_mods(self) -> int:
        return sum(entry.enabled_count for entry in self.all_characters())
