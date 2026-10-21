"""Modal screen for editing one mod hotkey expression."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from wwmm.errors import HotkeyEditError
from wwmm.hotkey_edit import validate_key_expr
from wwmm.hotkeys import Hotkey, format_key
from wwmm.models import Mod

_HINT = "Enter 确认 · Esc 取消 · 写法：ctrl alt f7 / VK_INSERT / 0x70 / XB 手柄键"


class HotkeyEditScreen(ModalScreen[str | None]):
    """Ask for a new key expression and return the normalized one on confirm."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "取消", priority=True),
    ]

    def __init__(self, mod: Mod, hotkey: Hotkey) -> None:
        super().__init__()
        self.mod = mod
        self.hotkey = hotkey

    def compose(self) -> ComposeResult:
        with Vertical(id="hotkey-edit-box"):
            yield Static(self._header(), id="hotkey-edit-header")
            yield Input(value=self.hotkey.raw, id="hotkey-edit-input")
            yield Static("", id="hotkey-edit-preview")
            yield Static("", id="hotkey-edit-error")
            yield Static(Text(_HINT, style="dim"), id="hotkey-edit-hint")

    def on_mount(self) -> None:
        key_input = self.query_one("#hotkey-edit-input", Input)
        self._update_preview(key_input.value)
        key_input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_preview(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        normalized = self._update_preview(event.value)
        if normalized is not None:
            self.dismiss(normalized)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _update_preview(self, raw: str) -> str | None:
        """Show the formatted preview and error, returning the normalized expression."""
        preview = self.query_one("#hotkey-edit-preview", Static)
        error = self.query_one("#hotkey-edit-error", Static)
        try:
            normalized = validate_key_expr(raw)
        except HotkeyEditError as exc:
            preview.update(Text(raw, style="dim"))
            error.update(Text(str(exc), style="red"))
            return None
        preview.update(Text(format_key(normalized), style="bold yellow"))
        error.update("")
        return normalized

    def _header(self) -> Text:
        return Text.assemble(
            (self.mod.display_name, "bold"),
            f" · {self.hotkey.section} · 当前 {self.hotkey.display_key}",
        )
