"""Build data/roster.json from Arikatsu datamine data (local or GitHub)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from wwmm.errors import RosterBuildError
from wwmm.roster_build import (
    DEFAULT_REPO,
    build_roster,
    diff_rosters,
    load_textmap,
    validate_roster_dict,
)

SCRIPT_DIR = Path(__file__).resolve().parent
ROLEINFO_PATH = "BinData/role/roleinfo.json"
ZH_PATH = "Textmaps/zh-Hans/multi_text/MultiText.json"
EN_PATH = "Textmaps/en/multi_text/MultiText.json"
USER_AGENT = "wwmm/0.1"


def _headers() -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch(url: str, timeout: float = 300) -> bytes:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = Request(url, headers=_headers())
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - retry all network failures
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RosterBuildError(f"下载失败 {url}：{last_error}")


def _fetch_json(url: str) -> object:
    payload = _fetch(url)
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RosterBuildError(f"远程 JSON 无效 {url}：{exc}") from exc


def _download_json(url: str, destination: Path) -> object:
    payload = _fetch(url)
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RosterBuildError(f"下载的 JSON 无效 {url}：{exc}") from exc
    destination.write_bytes(payload)
    return data


def _resolve_upstream(repo: str, branch: str | None) -> tuple[str, str, str]:
    if branch is None:
        info = _fetch_json(f"https://api.github.com/repos/{repo}")
        if not isinstance(info, dict) or not info.get("default_branch"):
            raise RosterBuildError(f"无法读取 {repo} 的默认分支")
        branch = str(info["default_branch"])

    commit_info = _fetch_json(f"https://api.github.com/repos/{repo}/commits/{branch}")
    if not isinstance(commit_info, dict):
        raise RosterBuildError(f"无法读取 {repo} 的最新提交")
    sha = str(commit_info.get("sha", ""))
    committed_at = str(
        (commit_info.get("commit") or {}).get("committer", {}).get("date", "")
    )
    if not sha:
        raise RosterBuildError(f"{repo}@{branch} 没有 commit sha")
    return branch, sha, committed_at


def _existing_commit(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    source = data.get("source")
    if not isinstance(source, dict):
        return None
    commit = source.get("commit")
    return str(commit) if commit else None


def _load_overrides(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RosterBuildError(f"无法读取 overrides {path}：{exc}") from exc
    if not isinstance(data, dict):
        raise RosterBuildError("overrides 必须是对象")
    return data


def _write_atomic(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the WWMM character roster")
    parser.add_argument("--out", type=Path, default=Path("data/roster.json"))
    parser.add_argument("--bundled-out", type=Path, default=None)
    parser.add_argument("--roleinfo", type=Path, default=None)
    parser.add_argument("--zh", type=Path, default=None)
    parser.add_argument("--en", type=Path, default=None)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--commit", default=None)
    parser.add_argument("--committed-at", default=None)
    parser.add_argument(
        "--overrides", type=Path, default=SCRIPT_DIR / "roster_overrides.json"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--min-characters", type=int, default=50)
    return parser


def _print_diff(old: dict, new: dict) -> None:
    added, removed, changed = diff_rosters(old, new)
    print(
        f"diff: +{len(added)} -{len(removed)} ~{len(changed)}"
        f" (new total {len(new.get('characters', []))})"
    )
    for label, slugs in (("added", added), ("removed", removed), ("changed", changed)):
        if slugs:
            print(f"{label}: {', '.join(slugs)}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        try:
            data = json.loads(args.out.read_text(encoding="utf-8"))
            validate_roster_dict(data, min_characters=args.min_characters)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, RosterBuildError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"roster ok: {len(data['characters'])} characters")
        return 0

    try:
        overrides = _load_overrides(args.overrides)
    except RosterBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    local_paths = (args.roleinfo, args.zh, args.en)
    local_mode = all(path is not None for path in local_paths)
    if any(path is not None for path in local_paths) and not local_mode:
        print("error: --roleinfo、--zh、--en 必须同时提供", file=sys.stderr)
        return 1

    try:
        if local_mode:
            branch = args.branch or "local"
            commit = args.commit or "local"
            committed_at = args.committed_at or datetime.now(timezone.utc).isoformat()
            if (
                args.out.exists()
                and _existing_commit(args.out) == commit
                and not args.force
            ):
                print("unchanged")
                return 0
            roles = json.loads(args.roleinfo.read_text(encoding="utf-8"))
            if not isinstance(roles, list):
                raise RosterBuildError("roleinfo.json 必须是数组")
            zh = load_textmap(args.zh)
            en = load_textmap(args.en)
        else:
            branch, commit, committed_at = _resolve_upstream(args.repo, args.branch)
            if (
                args.out.exists()
                and _existing_commit(args.out) == commit
                and not args.force
            ):
                print("upstream unchanged")
                return 0
            with tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                roleinfo_path = temp / "roleinfo.json"
                zh_path = temp / "zh.json"
                en_path = temp / "en.json"
                base = f"https://raw.githubusercontent.com/{args.repo}/{commit}"
                _download_json(f"{base}/{ROLEINFO_PATH}", roleinfo_path)
                _download_json(f"{base}/{ZH_PATH}", zh_path)
                _download_json(f"{base}/{EN_PATH}", en_path)
                roles = json.loads(roleinfo_path.read_text(encoding="utf-8"))
                zh = load_textmap(zh_path)
                en = load_textmap(en_path)

        built = build_roster(
            roles,
            zh,
            en,
            branch=branch,
            commit=commit,
            committed_at=committed_at,
            overrides=overrides,
            repo=args.repo,
        )
        validate_roster_dict(built, min_characters=args.min_characters)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, RosterBuildError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        if args.out.exists():
            try:
                old = json.loads(args.out.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                old = {"characters": []}
            _print_diff(old, built)
        else:
            print(
                f"dry-run: would write {len(built['characters'])} characters to {args.out}"
            )
        return 0

    try:
        _write_atomic(args.out, built)
        if args.bundled_out is not None:
            _write_atomic(args.bundled_out, built)
    except OSError as exc:
        print(f"error: 写入失败：{exc}", file=sys.stderr)
        return 1

    print(f"wrote {args.out}: {len(built['characters'])} characters ({branch})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
