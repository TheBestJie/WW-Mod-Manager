"""Settings screen (full implementation added in a later task)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class SettingsScreen(Screen):
    def __init__(self, first_run: bool = False, error: str | None = None) -> None:
        super().__init__()
        self.first_run = first_run
        self.error = error

    def compose(self) -> ComposeResult:
        text = "设置"
        if self.error:
            text += f"\n{self.error}"
        yield Static(text)
