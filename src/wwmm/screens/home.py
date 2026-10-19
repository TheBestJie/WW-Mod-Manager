"""Home screen: choose an element group."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, ListItem, ListView, Static

from wwmm.constants import GROUP_ORDER


class HomeScreen(Screen):
    BINDINGS = [
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

    def on_screen_resume(self) -> None:
        self.refresh_view()

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
                    Static(
                        f"[bold cyan]●[/] {name}  "
                        f"{populated}/{len(entries)} 角色 · {mods} mods"
                    )
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
        # Implemented by the global search task.
        pass

    def action_update(self) -> None:
        # Implemented by the in-TUI roster update task.
        pass

    def action_quit(self) -> None:
        self.app.exit()
