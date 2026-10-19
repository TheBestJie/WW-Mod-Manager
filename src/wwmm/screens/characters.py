"""Character list screen (full implementation added in a later task)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class CharactersScreen(Screen):
    def __init__(self, group: str) -> None:
        super().__init__()
        self.group = group

    def compose(self) -> ComposeResult:
        yield Static(self.group)
