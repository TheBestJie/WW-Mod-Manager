"""Build the roster from Arikatsu datamine data."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pypinyin import lazy_pinyin

from wwmm.constants import ELEMENTS, GROUP_ORDER, ROSTER_SCHEMA_VERSION
from wwmm.errors import RosterBuildError

log = logging.getLogger(__name__)

DEFAULT_REPO = "Arikatsu/WutheringWaves_Data"
ELEMENT_BY_ID: dict[int, str] = {
    1: "冷凝",
    2: "热熔",
    3: "导电",
    4: "气动",
    5: "衍射",
    6: "湮灭",
}
SLUG_RE = re.compile(r"^[a-z0-9]+$")


def load_textmap(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RosterBuildError(f"无法读取文本表 {path}：{exc}") from exc
    if not isinstance(raw, list):
        raise RosterBuildError(f"文本表 {path} 必须是数组")
    result: dict[str, str] = {}
    for item in raw:
        if isinstance(item, dict) and "Id" in item and "Content" in item:
            result[str(item["Id"])] = str(item["Content"])
    return result


def slugify(name_en: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", name_en.casefold())
    if not slug:
        raise RosterBuildError(f"无法从英文名生成 slug：{name_en!r}")
    return slug


def pinyin_keys(name_zh: str) -> tuple[str, str]:
    syllables = []
    for syllable in lazy_pinyin(name_zh):
        cleaned = "".join(char for char in syllable.casefold() if char.isalnum())
        if cleaned:
            syllables.append(cleaned)
    pinyin = "".join(syllables)
    initials = "".join(syllable[0] for syllable in syllables)
    return pinyin, initials


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _build_group(
    name_en: str,
    members: list[tuple[dict, str, str]],
    overrides: dict,
) -> tuple[int, dict]:
    members = sorted(members, key=lambda member: member[0].get("Id", 999999))
    name_zh = "漂泊者" if name_en == "Rover" else members[0][1]

    elements: list[str] = []
    for role, _zh, _en in members:
        element = ELEMENT_BY_ID.get(role.get("ElementId"))
        if element is None:
            raise RosterBuildError(
                f"{name_en} 含未知 ElementId：{role.get('ElementId')!r}"
            )
        if element not in elements:
            elements.append(element)
    elements.sort(key=GROUP_ORDER.index)

    slug = overrides.get("slugs", {}).get(name_en) or slugify(name_en)
    pinyin, initials = pinyin_keys(name_zh)

    aliases = _dedupe(
        [
            name_zh,
            name_en,
            *(
                value
                for member in members
                for value in (member[1], member[2])
            ),
            slug,
            pinyin,
            initials,
            *overrides.get("aliases", {}).get(name_en, []),
        ]
    )

    character = {
        "slug": slug,
        "name_zh": name_zh,
        "name_en": name_en,
        "elements": elements,
        "pinyin": pinyin,
        "initials": initials,
        "aliases": aliases,
        "folder": slug,
        "special": False,
    }
    character_id = min(member[0].get("Id", 999999) for member in members)
    return character_id, character


def build_roster(
    roles: list[dict],
    zh: dict[str, str],
    en: dict[str, str],
    *,
    branch: str,
    commit: str,
    committed_at: str,
    overrides: dict,
    repo: str = DEFAULT_REPO,
) -> dict:
    grouped: dict[str, list[tuple[dict, str, str]]] = {}
    for role in roles:
        if role.get("RoleType") != 1:
            continue
        if role.get("QualityId") not in (4, 5):
            continue
        name_key = str(role.get("Name", ""))
        name_zh = zh.get(name_key)
        name_en = en.get(name_key)
        if not name_zh or not name_en:
            raise RosterBuildError(f"角色 {role.get('Id')} 缺少中英文名（{name_key}）")
        group_name = "Rover" if name_en.startswith("Rover") else name_en
        grouped.setdefault(group_name, []).append((role, name_zh, name_en))

    built = [
        _build_group(name_en, members, overrides)
        for name_en, members in grouped.items()
    ]
    built.sort(key=lambda item: (item[0] or 999999, item[1]["slug"]))
    characters = [character for _id, character in built]

    characters.append(
        {
            "slug": "others",
            "name_zh": "其他",
            "name_en": "Others",
            "elements": [],
            "pinyin": "qita",
            "initials": "qt",
            "aliases": ["其他", "others"],
            "folder": "others",
            "special": True,
        }
    )

    return {
        "schema_version": ROSTER_SCHEMA_VERSION,
        "game_version": branch,
        "source": {
            "repo": repo,
            "branch": branch,
            "commit": commit,
            "committed_at": committed_at,
        },
        "characters": characters,
    }


def validate_roster_dict(data: dict, *, min_characters: int = 50) -> None:
    if not isinstance(data, dict):
        raise RosterBuildError("角色表根节点必须是对象")
    if data.get("schema_version") != ROSTER_SCHEMA_VERSION:
        raise RosterBuildError(f"不支持的 schema：{data.get('schema_version')!r}")

    characters = data.get("characters")
    if not isinstance(characters, list):
        raise RosterBuildError("characters 必须是数组")
    if len(characters) < min_characters:
        raise RosterBuildError(
            f"角色数不足：{len(characters)} < {min_characters}"
        )

    seen_slugs: set[str] = set()
    present_elements: set[str] = set()
    for character in characters:
        if not isinstance(character, dict):
            raise RosterBuildError("角色条目必须是对象")
        slug = character.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            raise RosterBuildError(f"非法 slug：{slug!r}")
        if slug in seen_slugs:
            raise RosterBuildError(f"重复 slug：{slug}")
        seen_slugs.add(slug)
        if not character.get("name_zh") or not character.get("name_en"):
            raise RosterBuildError(f"{slug} 缺少中英文名")
        elements = character.get("elements")
        if not isinstance(elements, list):
            raise RosterBuildError(f"{slug}.elements 必须是数组")
        for element in elements:
            if element not in ELEMENTS:
                raise RosterBuildError(f"{slug} 含未知属性：{element!r}")
            present_elements.add(element)

    if not set(ELEMENTS) <= present_elements:
        missing = [element for element in ELEMENTS if element not in present_elements]
        raise RosterBuildError(f"角色表缺少属性：{missing}")
    if "rover" not in seen_slugs:
        raise RosterBuildError("角色表缺少 rover")
    if "others" not in seen_slugs:
        raise RosterBuildError("角色表缺少 others")


def diff_rosters(old: dict, new: dict) -> tuple[list[str], list[str], list[str]]:
    def by_slug(data: dict) -> dict[str, dict]:
        return {c["slug"]: c for c in data.get("characters", [])}

    old_map = by_slug(old)
    new_map = by_slug(new)
    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    changed = sorted(
        slug
        for slug in set(old_map) & set(new_map)
        if json.dumps(old_map[slug], sort_keys=True, ensure_ascii=False)
        != json.dumps(new_map[slug], sort_keys=True, ensure_ascii=False)
    )
    return added, removed, changed
