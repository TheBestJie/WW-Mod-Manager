"""Mod list screen (full implementation added in the next task)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class ModsScreen(Screen):
    def __init__(self, slug: str) -> None:
        super().__init__()
        self.slug = slug

    def compose(self) -> ComposeResult:
        yield Static(self.slug)
