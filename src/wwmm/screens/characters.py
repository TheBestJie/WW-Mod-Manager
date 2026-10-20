"""Character list screen."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, ListItem, ListView, Static

from wwmm.models import CharacterEntry
from wwmm.search import filter_characters


class CharactersScreen(Screen):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("slash", "focus_filter", "过滤"),
        Binding("c", "copy_path", "复制路径"),
        Binding("h", "toggle_empty", "隐藏空角色"),
        Binding("escape", "app.pop_screen", "返回"),
    ]

    def __init__(self, group: str) -> None:
        super().__init__()
        self.group = group
        self.hide_empty = False
        self._visible: list[CharacterEntry] = []
        self._all_entries: list[CharacterEntry] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="char-header")
            yield Input(placeholder="过滤角色…", id="char-filter")
            yield ListView(id="characters")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()
        self.query_one("#characters", ListView).focus()

    def on_screen_resume(self) -> None:
        self.refresh_view()

    @property
    def visible_slugs(self) -> list[str]:
        return [entry.character.slug for entry in self._visible]

    def refresh_view(self) -> None:
        snapshot = self.app.reload_snapshot()
        self._all_entries = list(snapshot.groups.get(self.group, []))

        populated = sum(1 for entry in self._all_entries if entry.has_mods)
        mods = sum(entry.total_count for entry in self._all_entries)
        self.query_one("#char-header", Static).update(
            f"[bold]{self.group}[/] · {populated}/{len(self._all_entries)} 角色 · {mods} mods"
        )

        query = self.query_one("#char-filter", Input).value
        entries = filter_characters(self._all_entries, query)
        if self.hide_empty:
            entries = [entry for entry in entries if entry.has_mods]
        self._visible = entries

        list_view = self.query_one("#characters", ListView)
        list_view.clear()
        for entry in entries:
            character = entry.character
            if entry.has_mods:
                label = (
                    f"{character.name_zh}  [dim]{character.slug}[/]  "
                    f"[green]{entry.enabled_count}[/][dim]/{entry.total_count}[/]"
                )
            else:
                label = f"[dim]{character.name_zh}  {character.slug}  0/0[/]"
            list_view.append(ListItem(Static(label)))

        if entries:
            list_view.index = 0

    def _open(self, index: int) -> None:
        if not self._visible:
            return
        index = max(0, min(index, len(self._visible) - 1))
        from wwmm.screens.mods import ModsScreen

        self.app.push_screen(ModsScreen(self._visible[index].character.slug))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "char-filter":
            self.refresh_view()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "char-filter":
            self._open(0)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._open(event.index)

    def action_focus_filter(self) -> None:
        self.query_one("#char-filter", Input).focus()

    def action_copy_path(self) -> None:
        if not self._visible:
            return
        list_view = self.query_one("#characters", ListView)
        index = list_view.index or 0
        if index >= len(self._visible):
            index = 0
        entry = self._visible[index]
        self.app.copy_text(str(entry.path))
        self.notify(str(entry.path), title="已复制角色路径")

    def action_toggle_empty(self) -> None:
        self.hide_empty = not self.hide_empty
        self.refresh_view()
