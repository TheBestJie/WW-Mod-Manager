"""Home screen: choose an element group."""

from __future__ import annotations

import logging
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, ListItem, ListView, Static

from wwmm.constants import GROUP_ORDER
from wwmm.self_update import UpdateCheck

log = logging.getLogger(__name__)


class HomeScreen(Screen):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("slash", "search", "搜索"),
        Binding("s", "settings", "设置"),
        Binding("u", "update", "更新"),
        Binding("r", "refresh", "刷新"),
        Binding("q", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="home-header")
            yield ListView(id="groups")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()
        self.query_one("#groups", ListView).focus()
        # Fire-and-forget: the release check must never delay or block the TUI.
        self._startup_update_check()

    def on_screen_resume(self) -> None:
        # Coming back from another screen must not re-run the release check.
        self.refresh_view()

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _startup_update_check(self) -> None:
        """Silently compare the local version with the latest GitHub release."""
        try:
            check = self.app.release_checker()
        except Exception as exc:
            # A startup check failure stays invisible: log only, never notify.
            log.debug("启动版本检查失败：%s", exc, exc_info=True)
            return
        if check is None:
            return
        self._call(self._on_newer_release, check)

    def _call(self, callback, *args) -> None:
        """Hop back to the UI thread, tolerating an app that already quit."""
        try:
            self.app.call_from_thread(callback, *args)
        except RuntimeError:
            # Expected: the app shut down while the worker was still running.
            log.debug("UI callback dropped: app is not running", exc_info=True)
        except Exception:
            # A UI callback must never kill the worker, but a bug in the
            # callback is not a network failure: it has to stay visible.
            log.exception("UI callback failed")

    def _on_newer_release(self, check: UpdateCheck) -> None:
        if not self.is_attached:
            return
        self.notify(
            f"发现新版本 v{check.latest.version}（当前 v{check.current}）· Ctrl+U 立即更新",
            timeout=15,
        )

    @property
    def group_names(self) -> list[str]:
        snapshot = self.app.snapshot
        names = [name for name in GROUP_ORDER if name != "未分类"]
        if snapshot is not None and snapshot.groups.get("未分类"):
            names.append("未分类")
        return names

    def refresh_view(self) -> None:
        snapshot = self.app.reload_snapshot()
        header = self.query_one("#home-header", Static)
        header.update(
            f"[bold]鸣潮 Mod 管理器[/]  ·  {snapshot.total_mods} mods"
            f"（启用 {snapshot.enabled_mods}）"
        )

        list_view = self.query_one("#groups", ListView)
        list_view.clear()
        for name in self.group_names:
            entries = snapshot.groups.get(name, [])
            populated = sum(1 for entry in entries if entry.has_mods)
            mods = sum(entry.total_count for entry in entries)
            list_view.append(
                ListItem(
                    Static(f"[bold cyan]●[/] {name}  {populated}/{len(entries)} 角色 · {mods} mods")
                )
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        from wwmm.screens.characters import CharactersScreen

        group = self.group_names[event.index]
        self.app.push_screen(CharactersScreen(group))

    def action_refresh(self) -> None:
        self.refresh_view()

    def action_settings(self) -> None:
        from wwmm.screens.settings import SettingsScreen

        self.app.push_screen(SettingsScreen())

    def action_search(self) -> None:
        from wwmm.models import CharacterEntry
        from wwmm.screens.mods import ModsScreen
        from wwmm.screens.search import SearchScreen

        def open_entry(entry: CharacterEntry | None) -> None:
            if entry is not None:
                self.app.push_screen(ModsScreen(entry.character.slug))

        self.app.push_screen(SearchScreen(), callback=open_entry)

    def action_update(self) -> None:
        from wwmm.screens.update import UpdateScreen

        self.app.push_screen(UpdateScreen())

    def action_quit(self) -> None:
        self.app.exit()
