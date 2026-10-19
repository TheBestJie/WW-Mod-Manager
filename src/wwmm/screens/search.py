"""Global character search modal."""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from wwmm.models import CharacterEntry
from wwmm.search import filter_characters


class SearchScreen(ModalScreen[CharacterEntry | None]):
    BINDINGS = [Binding("escape", "cancel", "关闭")]

    def __init__(self) -> None:
        super().__init__()
        self._results: list[CharacterEntry] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Input(
                id="search-input",
                placeholder="搜索角色：中文/英文/拼音/首字母/属性",
            )
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.refresh_view()
        self.query_one("#search-input", Input).focus()

    @property
    def visible_slugs(self) -> list[str]:
        return [entry.character.slug for entry in self._results]

    def refresh_view(self) -> None:
        snapshot = self.app.snapshot
        entries = snapshot.all_characters() if snapshot is not None else []
        query = self.query_one("#search-input", Input).value
        results = filter_characters(entries, query)
        results.sort(
            key=lambda entry: (
                not entry.has_mods,
                entry.character.name_zh,
                entry.character.slug,
            )
        )
        self._results = results

        list_view = self.query_one("#search-results", ListView)
        list_view.clear()
        for entry in results:
            character = entry.character
            list_view.append(
                ListItem(
                    Static(
                        f"{escape(character.name_zh)} · {character.group}"
                        f" · {entry.enabled_count}/{entry.total_count}"
                    )
                )
            )
        list_view.index = 0 if results else None

    def _choose(self, index: int) -> None:
        if not self._results:
            return
        index = max(0, min(index, len(self._results) - 1))
        self.dismiss(self._results[index])

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.refresh_view()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._choose(0)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._choose(event.index)

    def action_cancel(self) -> None:
        self.dismiss(None)
