"""Textual application shell for WWMM."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from textual.app import App

from wwmm.clipboard import copy_with_command
from wwmm.config import Config, ConfigStore
from wwmm.errors import LayoutError
from wwmm.models import Mod, Snapshot
from wwmm.paths import detect_mods_dirs, looks_like_mods_dir
from wwmm.roster import Roster, ensure_character_dirs
from wwmm.roster_update import UpdateResult, update_roster
from wwmm.scanner import scan
from wwmm.screens.home import HomeScreen
from wwmm.screens.settings import SettingsScreen

log = logging.getLogger(__name__)


class WWMMApp(App):
    """The WWMM TUI."""

    CSS_PATH = "app.tcss"
    TITLE = "WWMM"
    SUB_TITLE = "鸣潮 Mod 管理器"

    def __init__(
        self,
        *,
        config_store: ConfigStore,
        config: Config,
        roster: Roster,
        data_dir: Path,
        state_dir: Path,
        home_dir: Path,
        updater=update_roster,
        detector=detect_mods_dirs,
    ) -> None:
        super().__init__()
        self.config_store = config_store
        self.config = config
        self.roster = roster
        self.data_dir = Path(data_dir)
        self.state_dir = Path(state_dir)
        self.home_dir = Path(home_dir)
        self.updater = updater
        self.detector = detector

        self.snapshot: Snapshot | None = None
        self.created_dirs: list[Path] = []
        self.last_toggle: Mod | None = None
        self.last_update: UpdateResult | None = None
        self.last_error: str | None = None

    def on_mount(self) -> None:
        if self.config.mods_dir is None:
            self.push_screen(SettingsScreen(first_run=True))
            return
        mods_dir = Path(self.config.mods_dir)
        if not looks_like_mods_dir(mods_dir):
            self.last_error = f"不是有效的 WWMI Mods 目录：{mods_dir}"
            self.push_screen(SettingsScreen(first_run=True, error=self.last_error))
            return
        try:
            self._ensure_character_dirs()
            self.snapshot = scan(mods_dir, self.roster)
        except LayoutError as exc:
            self.last_error = str(exc)
            self.push_screen(SettingsScreen(first_run=True, error=str(exc)))
            return
        self.push_screen(HomeScreen())
        if self.created_dirs:
            self.notify(f"已补全 {len(self.created_dirs)} 个角色文件夹")

    def _ensure_character_dirs(self) -> None:
        if self.config.mods_dir is None or not self.config.auto_create_folders:
            return
        result = ensure_character_dirs(self.roster, Path(self.config.mods_dir))
        self.created_dirs.extend(result.created)
        for path, message in result.errors:
            log.warning("角色目录错误 %s：%s", path, message)

    def reload_snapshot(self) -> Snapshot:
        """Re-scan the Mods directory and return the new snapshot."""
        if self.config.mods_dir is None:
            raise LayoutError("尚未设置 Mods 目录")
        self.snapshot = scan(Path(self.config.mods_dir), self.roster)
        return self.snapshot

    def set_mods_dir(self, path: Path) -> Snapshot:
        """Persist a new Mods directory, create missing folders and re-scan."""
        path = Path(path)
        if not looks_like_mods_dir(path):
            raise LayoutError(f"不是有效的 WWMI Mods 目录：{path}")
        self.config.mods_dir = path
        self.config_store.save(self.config)
        self.created_dirs = []
        self._ensure_character_dirs()
        return self.reload_snapshot()

    def apply_roster(self, roster: Roster) -> Snapshot:
        """Replace the roster, create missing folders and re-scan."""
        self.roster = roster
        self.created_dirs = []
        self._ensure_character_dirs()
        return self.reload_snapshot()

    async def copy_text(self, text: str) -> bool:
        """Copy text to the terminal clipboard and desktop clipboard tools.

        Returns True when a desktop clipboard command accepted the text.
        """
        self.copy_to_clipboard(text)
        return await asyncio.to_thread(copy_with_command, text)
