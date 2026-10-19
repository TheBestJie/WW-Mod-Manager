"""Settings screen: choose and validate the WWMI Mods directory."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Static

from wwmm.errors import LayoutError
from wwmm.paths import looks_like_mods_dir


class SettingsScreen(Screen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "返回")]

    def __init__(self, first_run: bool = False, error: str | None = None) -> None:
        super().__init__()
        self.first_run = first_run
        self.error = error

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-box"):
            yield Static(
                "[bold]首次设置[/]" if self.first_run else "[bold]设置[/]",
                id="settings-title",
            )
            yield Static(
                "请选择 WWMI 的 Mods 目录（包含 character 子目录）。",
                id="settings-help",
            )
            yield Input(id="mods-path", placeholder="/path/to/XXMI Launcher/WWMI/Mods")
            yield Static(id="settings-status")
            with Horizontal():
                yield Button("保存", id="save-mods", variant="primary")
                yield Button("自动探测", id="detect-mods")
        yield Footer()

    def on_mount(self) -> None:
        status = self.query_one("#settings-status", Static)
        path_input = self.query_one("#mods-path", Input)

        if not self.first_run and self.app.config.mods_dir is not None:
            path_input.value = str(self.app.config.mods_dir)
            status.update("[dim]修改后点击保存[/]")
        elif self.error:
            status.update(f"[red]{escape(self.error)}[/]")
            candidates = self.app.detector(self.app.home_dir)
            if candidates:
                path_input.value = str(candidates[0])
        else:
            candidates = self.app.detector(self.app.home_dir)
            if candidates:
                path_input.value = str(candidates[0])
                status.update(f"[green]已找到 {len(candidates)} 个候选目录[/]")
            else:
                status.update("[yellow]没有自动找到 Mods 目录，请手动输入[/]")
        path_input.focus()

    def _save(self) -> None:
        raw = self.query_one("#mods-path", Input).value.strip()
        status = self.query_one("#settings-status", Static)
        path = Path(raw).expanduser() if raw else None
        if path is None or not looks_like_mods_dir(path):
            status.update("[red]不是有效的 WWMI Mods 目录[/]")
            return

        try:
            self.app.set_mods_dir(path)
        except (LayoutError, OSError) as exc:
            status.update(f"[red]保存失败：{escape(str(exc))}[/]")
            return

        from wwmm.screens.home import HomeScreen

        self.app.switch_screen(HomeScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-mods":
            self._save()
        elif event.button.id == "detect-mods":
            status = self.query_one("#settings-status", Static)
            candidates = self.app.detector(self.app.home_dir)
            if candidates:
                self.query_one("#mods-path", Input).value = str(candidates[0])
                status.update(f"[green]已找到 {len(candidates)} 个候选目录[/]")
            else:
                status.update("[yellow]没有自动找到 Mods 目录，请手动输入[/]")

    def action_cancel(self) -> None:
        if not self.first_run:
            self.app.pop_screen()
