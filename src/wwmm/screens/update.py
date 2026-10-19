"""Confirm and run an in-TUI roster update."""

from __future__ import annotations

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from wwmm.roster import load_effective_roster
from wwmm.roster_update import UpdateResult


class UpdateScreen(ModalScreen[UpdateResult | None]):
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def compose(self) -> ComposeResult:
        with Vertical(id="update-box"):
            yield Static(
                "从 GitHub 更新角色表？\n仅更新角色数据，不更新程序。",
                id="update-message",
            )
            with Horizontal():
                yield Button("更新", id="update-confirm", variant="primary")
                yield Button("取消", id="update-cancel")

    def on_mount(self) -> None:
        self.query_one("#update-confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "update-confirm":
            self._start()
        elif event.button.id == "update-cancel":
            self.dismiss(None)

    def _start(self) -> None:
        confirm = self.query_one("#update-confirm", Button)
        confirm.disabled = True
        self._run_update()

    @work(thread=True, exclusive=True)
    def _run_update(self) -> None:
        try:
            result = self.app.updater(
                url=self.app.config.roster_url,
                data_dir=self.app.data_dir,
            )
        except Exception as exc:  # noqa: BLE001 - errors must surface in the TUI
            self.app.call_from_thread(self._on_error, str(exc))
            return
        self.app.call_from_thread(self._on_success, result)

    def _on_success(self, result: UpdateResult) -> None:
        if not self.is_attached:
            return
        try:
            roster = load_effective_roster(self.app.data_dir)
            self.app.apply_roster(roster)
        except Exception as exc:  # noqa: BLE001
            self._on_error(str(exc))
            return
        self.app.last_update = result
        self.app.last_error = None
        self.notify(f"角色表已更新到 {result.game_version}")
        self.dismiss(result)

    def _on_error(self, message: str) -> None:
        if not self.is_attached:
            return
        self.app.last_error = message
        self.query_one("#update-confirm", Button).disabled = False
        self.notify(f"更新失败：{escape(message)}", title="更新失败", severity="error")

    def action_cancel(self) -> None:
        self.dismiss(None)
