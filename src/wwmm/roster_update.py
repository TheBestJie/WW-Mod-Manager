"""Update the local roster from a URL or a local file."""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from wwmm.errors import (
    RosterBuildError,
    RosterDowngradeError,
    RosterError,
    RosterUpdateError,
)
from wwmm.roster import Roster, load_roster_file, parse_roster
from wwmm.roster_build import validate_roster_dict

log = logging.getLogger(__name__)

USER_AGENT = "wwmm/0.1"


@dataclass(frozen=True)
class UpdateResult:
    game_version: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    path: Path
    dry_run: bool


def _parse_validated(data: object) -> Roster:
    if not isinstance(data, dict):
        raise RosterUpdateError("角色表根节点必须是对象")
    try:
        validate_roster_dict(data, min_characters=1)
    except RosterBuildError as exc:
        raise RosterUpdateError(f"角色表校验失败：{exc}") from exc
    try:
        return parse_roster(data)
    except RosterError as exc:
        raise RosterUpdateError(f"角色表校验失败：{exc}") from exc


def fetch_roster(url: str, timeout: float = 30) -> Roster:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except OSError as exc:
        raise RosterUpdateError(f"下载角色表失败：{exc}") from exc

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RosterUpdateError(f"远程角色表不是有效 JSON：{exc}") from exc
    return _parse_validated(data)


def _roster_to_dict(roster: Roster) -> dict:
    return {
        "schema_version": roster.schema_version,
        "game_version": roster.game_version,
        "source": asdict(roster.source),
        "characters": [
            {
                "slug": character.slug,
                "name_zh": character.name_zh,
                "name_en": character.name_en,
                "elements": list(character.elements),
                "pinyin": character.pinyin,
                "initials": character.initials,
                "aliases": list(character.aliases),
                "folder": character.folder,
                "special": character.special,
            }
            for character in roster.characters
        ],
    }


def _load_existing(path: Path) -> Roster | None:
    if not path.exists():
        return None
    try:
        return load_roster_file(path)
    except RosterError as exc:
        log.warning("旧角色表无法解析，将忽略其内容：%s", exc)
        return None


def _diff(
    old: Roster | None, new: Roster
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if old is None:
        return tuple(sorted(c.slug for c in new.characters)), (), ()
    old_by_slug = {c.slug: c for c in old.characters}
    new_by_slug = {c.slug: c for c in new.characters}
    added = tuple(sorted(set(new_by_slug) - set(old_by_slug)))
    removed = tuple(sorted(set(old_by_slug) - set(new_by_slug)))
    changed = tuple(
        sorted(
            slug
            for slug in set(old_by_slug) & set(new_by_slug)
            if old_by_slug[slug] != new_by_slug[slug]
        )
    )
    return added, removed, changed


def update_roster(
    *,
    url: str,
    data_dir: Path,
    from_file: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> UpdateResult:
    data_dir = Path(data_dir)
    out_path = data_dir / "roster.json"
    old = _load_existing(out_path)

    if from_file is not None:
        try:
            data = json.loads(Path(from_file).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RosterUpdateError(f"角色表校验失败：{exc}") from exc
        new = _parse_validated(data)
    elif url:
        new = fetch_roster(url)
    else:
        raise RosterUpdateError("没有指定角色表来源（URL 或 --from 文件）")

    if (
        not force
        and old is not None
        and old.source.committed_at
        and new.source.committed_at
        and new.source.committed_at < old.source.committed_at
    ):
        raise RosterDowngradeError(
            f"远程角色表更旧（{new.source.committed_at} < {old.source.committed_at}），"
            "使用 --force 可强制覆盖"
        )

    added, removed, changed = _diff(old, new)
    result = UpdateResult(
        game_version=new.game_version,
        added=added,
        removed=removed,
        changed=changed,
        path=out_path,
        dry_run=dry_run,
    )

    log.info(
        "角色表更新%s：%s，新增 %d，移除 %d，变更 %d",
        "（预演）" if dry_run else "",
        new.game_version,
        len(added),
        len(removed),
        len(changed),
    )
    if dry_run:
        return result

    data_dir.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        try:
            shutil.copy2(out_path, data_dir / "roster.json.bak")
        except OSError as exc:
            raise RosterUpdateError(f"备份旧角色表失败：{exc}") from exc

    tmp_path = data_dir / "roster.json.tmp"
    try:
        tmp_path.write_text(
            json.dumps(_roster_to_dict(new), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, out_path)
    except OSError as exc:
        raise RosterUpdateError(f"写入角色表失败：{exc}") from exc

    return result
