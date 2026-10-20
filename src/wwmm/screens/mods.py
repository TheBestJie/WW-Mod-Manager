"""Mod list screen with enable/disable toggle."""

from __future__ import annotations

from typing import ClassVar

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, ListItem, ListView, Static

from wwmm.errors import ToggleError
from wwmm.hotkeys import parse_mod_hotkeys
from wwmm.models import CharacterEntry, Mod
from wwmm.screens.hotkeys import HotkeysScreen
from wwmm.search import filter_mods
from wwmm.toggle import toggle_mod


class ModsScreen(Screen):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("space", "toggle", "开关"),
        Binding("m", "show_hotkeys", "快捷键"),
        Binding("slash", "focus_filter", "过滤"),
        Binding("c", "copy_path", "复制路径"),
        Binding("r", "refresh", "刷新"),
        Binding("escape", "app.pop_screen", "返回"),
    ]

    def __init__(self, slug: str) -> None:
        super().__init__()
        self.slug = slug
        self._entry: CharacterEntry | None = None
        self._visible: list[Mod] = []
        self._skip_resume_refresh = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="mod-header")
            yield Input(placeholder="过滤 mod…", id="mod-filter")
            yield ListView(id="mods")
            yield Static(id="mod-detail")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()
        self.query_one("#mods", ListView).focus()

    def on_screen_resume(self) -> None:
        if self._skip_resume_refresh:
            self._skip_resume_refresh = False
            return
        self.refresh_view()

    @property
    def visible_mods(self) -> list[Mod]:
        return list(self._visible)

    def refresh_view(self, keep_base: str | None = None) -> None:
        snapshot = self.app.reload_snapshot()
        self._entry = snapshot.find(self.slug)
        list_view = self.query_one("#mods", ListView)

        current_folder = None
        if (
            self._visible
            and list_view.index is not None
            and 0 <= list_view.index < len(self._visible)
        ):
            current_folder = self._visible[list_view.index].folder_name

        header = self.query_one("#mod-header", Static)
        if self._entry is None:
            header.update(f"[bold]{escape(self.slug)}[/] · 未找到角色目录")
            self._visible = []
            list_view.clear()
            list_view.index = None
            self.query_one("#mod-detail", Static).update("[yellow]未找到角色目录[/]")
            return

        entry = self._entry
        header.update(
            f"[bold]{escape(entry.character.name_zh)}[/] · {entry.character.group}"
            f" · {entry.enabled_count}/{entry.total_count}"
        )

        query = self.query_one("#mod-filter", Input).value
        self._visible = filter_mods(entry.mods, query)

        list_view.clear()
        for mod in self._visible:
            list_view.append(ListItem(Static(self._mod_label(mod))))

        index = 0
        if keep_base is not None:
            for position, mod in enumerate(self._visible):
                if mod.base_name == keep_base:
                    index = position
                    break
        elif current_folder is not None:
            for position, mod in enumerate(self._visible):
                if mod.folder_name == current_folder:
                    index = position
                    break
        if self._visible:
            list_view.index = index
            self._update_detail(index)
        else:
            list_view.index = None
            self._update_detail(None)

    def _mod_label(self, mod: Mod) -> str:
        status = "●" if mod.enabled else "○"
        suffix = f"[dim]{mod.ini_count} ini[/]" if mod.ini_count else "[yellow]⚠ 无 ini[/]"
        return f"{status} {escape(mod.display_name)}  {suffix}"

    def _update_detail(self, index: int | None) -> None:
        detail = self.query_one("#mod-detail", Static)
        if self._entry is None:
            detail.update("[yellow]未找到角色目录[/]")
            return
        if not self._visible:
            if not self._entry.mods:
                detail.update(
                    f"[dim]尚无 mod。将 mod 文件夹放入：{escape(str(self._entry.path))}[/]"
                )
            else:
                detail.update("[dim]没有匹配的 mod[/]")
            return
        if index is None or not (0 <= index < len(self._visible)):
            index = 0
        mod = self._visible[index]
        status = "[green]已启用[/]" if mod.enabled else "[yellow]已禁用[/]"
        detail.update(
            f"文件夹：{escape(mod.folder_name)}\n"
            f"路径：{escape(str(mod.path))}\n"
            f"ini 文件：{mod.ini_count}\n"
            f"状态：{status}\n"
            "快捷操作：m 查看快捷键 · c 复制路径"
        )

    def _selected_mod(self) -> Mod | None:
        if not self._visible:
            return None
        list_view = self.query_one("#mods", ListView)
        index = list_view.index or 0
        if index >= len(self._visible):
            index = 0
        return self._visible[index]

    async def action_copy_path(self) -> None:
        mod = self._selected_mod()
        if mod is None:
            return
        path = mod.path.absolute()
        copied = await self.app.copy_text(str(path))
        if copied:
            self.notify(str(path), title="已复制 mod 路径", markup=False)
        else:
            self.notify(
                f"{path}\n未找到桌面剪贴板工具，已改用终端 OSC 52",
                title="复制可能未生效",
                severity="warning",
                markup=False,
            )

    def action_toggle(self) -> None:
        mod = self._selected_mod()
        if mod is None:
            return
        try:
            new_mod = toggle_mod(mod)
        except ToggleError as exc:
            self.app.last_error = str(exc)
            self.notify(str(exc), title="切换失败", severity="error")
            return

        self.app.last_toggle = new_mod
        self.app.last_error = None
        self.refresh_view(keep_base=new_mod.base_name)
        verb = "启用" if new_mod.enabled else "禁用"
        self.notify(f"已{verb} {new_mod.base_name} · 回游戏按 F10")

    def action_show_hotkeys(self) -> None:
        mod = self._selected_mod()
        if mod is None:
            return
        self._skip_resume_refresh = True
        self.app.push_screen(HotkeysScreen(mod, parse_mod_hotkeys(mod.path)))

    def action_focus_filter(self) -> None:
        self.query_one("#mod-filter", Input).focus()

    def action_refresh(self) -> None:
        self.refresh_view()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "mod-filter":
            self.refresh_view()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "mod-filter":
            self.query_one("#mods", ListView).focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self._update_detail(event.list_view.index)
