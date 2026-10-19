"""Command line entry point for WWMM."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from wwmm import __version__
from wwmm.config import ConfigStore
from wwmm.errors import LayoutError, RosterError, RosterUpdateError
from wwmm.logging_setup import setup_logging
from wwmm.paths import config_dir, data_dir, detect_mods_dirs, state_dir
from wwmm.roster import ensure_character_dirs, load_effective_roster
from wwmm.roster_update import update_roster


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wwmm",
        description="鸣潮 XXMI/WWMI Mod 管理器（Linux TUI）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--mods-dir", type=Path, default=None, help="覆盖 Mods 目录")

    subparsers = parser.add_subparsers(dest="command")
    update = subparsers.add_parser("update", help="更新角色表并补全角色目录")
    update.add_argument("--from", dest="from_file", type=Path, help="从本地文件导入角色表")
    update.add_argument("--url", help="角色表 URL（默认使用配置中的地址）")
    update.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    update.add_argument("--force", action="store_true", help="允许覆盖更新的本地角色表")
    update.add_argument("--no-create", action="store_true", help="不补全角色目录")
    update.add_argument("--mods-dir", dest="update_mods_dir", type=Path, default=None)
    return parser


def _selected_mods_dir(args: argparse.Namespace) -> Path | None:
    return args.update_mods_dir or args.mods_dir


def _run_update(args: argparse.Namespace) -> int:
    store = ConfigStore(config_dir())
    config = store.load()

    explicit_mods_dir = _selected_mods_dir(args)
    if explicit_mods_dir is not None:
        # Per-invocation override; update must not write config (especially in dry-run).
        config.mods_dir = Path(explicit_mods_dir)

    if config.mods_dir is None:
        print(
            "错误：未配置 Mods 目录。请先运行 `wwmm` 完成设置，或使用 --mods-dir。",
            file=sys.stderr,
        )
        return 2

    try:
        result = update_roster(
            url=args.url or config.roster_url,
            data_dir=data_dir(),
            from_file=args.from_file,
            dry_run=args.dry_run,
            force=args.force,
        )
    except RosterUpdateError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"角色表版本：{result.game_version}")
    print(f"新增 {len(result.added)}，移除 {len(result.removed)}，变更 {len(result.changed)}")
    print(f"写入：{result.path}" + ("（预演，未写入）" if result.dry_run else ""))

    if result.dry_run or args.no_create:
        return 0

    try:
        roster = load_effective_roster(data_dir())
        ensured = ensure_character_dirs(roster, config.mods_dir)
    except (LayoutError, RosterError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"已补全 {len(ensured.created)} 个角色文件夹")
    for path, message in ensured.errors:
        print(f"警告：{path}：{message}", file=sys.stderr)
    return 0


def _run_tui(args: argparse.Namespace) -> int:
    store = ConfigStore(config_dir())
    config = store.load()
    if args.mods_dir is not None:
        config.mods_dir = Path(args.mods_dir)
        store.save(config)

    from wwmm.app import WWMMApp

    app = WWMMApp(
        config_store=store,
        config=config,
        roster=load_effective_roster(data_dir()),
        data_dir=data_dir(),
        state_dir=state_dir(),
        home_dir=Path.home(),
        updater=update_roster,
        detector=detect_mods_dirs,
    )
    app.run()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(state_dir())
    if args.command == "update":
        return _run_update(args)
    return _run_tui(args)
