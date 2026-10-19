"""Character roster parsing and loading."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from wwmm.constants import ELEMENTS, GROUP_ORDER, ROSTER_SCHEMA_VERSION
from wwmm.errors import LayoutError, RosterError
from wwmm.models import Character

log = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9]+$")


@dataclass(frozen=True)
class RosterSource:
    repo: str
    branch: str
    commit: str
    committed_at: str


@dataclass(frozen=True)
class Roster:
    schema_version: int
    game_version: str
    source: RosterSource
    characters: tuple[Character, ...]

    def by_slug(self, slug: str) -> Character | None:
        wanted = slug.casefold()
        for character in self.characters:
            if character.slug.casefold() == wanted:
                return character
        return None

    def by_folder(self, folder: str) -> Character | None:
        wanted = folder.casefold()
        for character in self.characters:
            if character.folder.casefold() == wanted:
                return character
            if character.slug.casefold() == wanted:
                return character
            if any(alias.casefold() == wanted for alias in character.aliases):
                return character
        return None

    def groups(self) -> dict[str, list[Character]]:
        grouped: dict[str, list[Character]] = {name: [] for name in GROUP_ORDER}
        for character in self.characters:
            grouped.setdefault(character.group, []).append(character)
        for entries in grouped.values():
            entries.sort(key=lambda c: (c.name_zh, c.slug))
        return grouped


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RosterError(f"角色表字段 {field} 不能为空")
    return value.strip()


def _parse_character(raw: object) -> Character:
    if not isinstance(raw, dict):
        raise RosterError("角色表条目必须是对象")

    slug = _text(raw.get("slug"), "slug")
    if not SLUG_RE.match(slug):
        raise RosterError(f"非法 slug：{slug}")

    name_zh = _text(raw.get("name_zh"), f"{slug}.name_zh")
    name_en = _text(raw.get("name_en"), f"{slug}.name_en")

    raw_elements = raw.get("elements", [])
    if not isinstance(raw_elements, list) or not all(isinstance(e, str) for e in raw_elements):
        raise RosterError(f"{slug}.elements 必须是字符串数组")
    unknown = [e for e in raw_elements if e not in ELEMENTS]
    if unknown:
        raise RosterError(f"{slug} 含未知属性：{unknown}")

    special = bool(raw.get("special", False))
    if not raw_elements and not special:
        raise RosterError(f"{slug} 不是特殊角色，但没有任何属性")

    folder = raw.get("folder") or slug
    if not isinstance(folder, str) or not folder.strip():
        raise RosterError(f"{slug}.folder 不能为空")

    raw_aliases = raw.get("aliases", [])
    if not isinstance(raw_aliases, list) or not all(isinstance(a, str) for a in raw_aliases):
        raise RosterError(f"{slug}.aliases 必须是字符串数组")

    return Character(
        slug=slug,
        name_zh=name_zh,
        name_en=name_en,
        elements=tuple(raw_elements),
        folder=folder.strip(),
        special=special,
        pinyin=str(raw.get("pinyin", "")),
        initials=str(raw.get("initials", "")),
        aliases=tuple(raw_aliases),
    )


def parse_roster(data: dict) -> Roster:
    if not isinstance(data, dict):
        raise RosterError("角色表根节点必须是对象")
    if data.get("schema_version") != ROSTER_SCHEMA_VERSION:
        raise RosterError(f"不支持的角色表 schema：{data.get('schema_version')!r}")

    raw_characters = data.get("characters")
    if not isinstance(raw_characters, list) or not raw_characters:
        raise RosterError("角色表 characters 不能为空")

    characters = [_parse_character(raw) for raw in raw_characters]

    seen_slugs: set[str] = set()
    seen_folders: set[str] = set()
    for character in characters:
        slug_key = character.slug.casefold()
        folder_key = character.folder.casefold()
        if slug_key in seen_slugs:
            raise RosterError(f"重复 slug：{character.slug}")
        if folder_key in seen_folders:
            raise RosterError(f"重复角色目录：{character.folder}")
        seen_slugs.add(slug_key)
        seen_folders.add(folder_key)

    if "others" not in seen_slugs:
        characters.append(
            Character(
                slug="others",
                name_zh="其他",
                name_en="Others",
                elements=(),
                folder="others",
                special=True,
                pinyin="qita",
                initials="qt",
                aliases=("其他", "others"),
            )
        )

    source = data.get("source") or {}
    if not isinstance(source, dict):
        raise RosterError("角色表 source 必须是对象")
    roster_source = RosterSource(
        repo=str(source.get("repo", "")),
        branch=str(source.get("branch", "")),
        commit=str(source.get("commit", "")),
        committed_at=str(source.get("committed_at", "")),
    )

    return Roster(
        schema_version=ROSTER_SCHEMA_VERSION,
        game_version=str(data.get("game_version", "")),
        source=roster_source,
        characters=tuple(characters),
    )


def load_roster_file(path: Path) -> Roster:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise RosterError(f"无法读取角色表 {path}：{exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RosterError(f"角色表 JSON 无效 {path}：{exc}") from exc
    return parse_roster(data)


def load_bundled_roster() -> Roster:
    return load_roster_file(Path(__file__).with_name("data") / "roster.json")


def load_effective_roster(data_dir: Path) -> Roster:
    local_path = Path(data_dir) / "roster.json"
    if local_path.exists():
        try:
            return load_roster_file(local_path)
        except RosterError as exc:
            log.warning("本地角色表损坏，回退到内置角色表：%s", exc)
    return load_bundled_roster()


@dataclass
class DirEnsureResult:
    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def _find_character_root(mods_root: Path) -> Path | None:
    for entry in mods_root.iterdir():
        if entry.is_dir() and not entry.is_symlink() and entry.name.casefold() == "character":
            return entry
    return None


def ensure_character_dirs(roster: Roster, mods_root: Path) -> DirEnsureResult:
    """Create any missing `character/<folder>` directories.

    Never deletes or overwrites anything. Missing Mods root is an error.
    """
    mods_root = Path(mods_root)
    if not mods_root.is_dir():
        raise LayoutError(f"Mods 目录不存在或不是目录：{mods_root}")

    character_root = _find_character_root(mods_root)
    if character_root is None:
        character_root = mods_root / "character"
        try:
            character_root.mkdir()
        except OSError as exc:
            raise LayoutError(f"无法创建 character 目录：{exc}") from exc

    result = DirEnsureResult()
    existing = {entry.name.casefold(): entry for entry in character_root.iterdir()}

    for character in roster.characters:
        key = character.folder.casefold()
        target = character_root / character.folder
        if key in existing:
            found = existing[key]
            if found.is_symlink() or not found.is_dir():
                result.errors.append((found, "同名路径已存在且不是目录，未覆盖"))
            else:
                result.skipped.append(found)
            continue
        try:
            target.mkdir()
        except OSError as exc:
            result.errors.append((target, str(exc)))
            log.warning("创建角色目录失败 %s：%s", target, exc)
            continue
        result.created.append(target)

    log.info("角色目录补全：创建 %d，跳过 %d，错误 %d",
             len(result.created), len(result.skipped), len(result.errors))
    return result
