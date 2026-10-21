"""Check the latest GitHub release and run a self update from the TUI."""

from __future__ import annotations

import logging
from typing import ClassVar

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from wwmm import __version__
from wwmm.self_update import SelfUpdateResult, UpdateCheck, find_repo_root

log = logging.getLogger(__name__)

CHECKING_MESSAGE = "正在检查 GitHub release…"
UPDATING_MESSAGE = "正在更新，请稍候…"


class SelfUpdateScreen(ModalScreen[None]):
    """Modal that checks for a newer release and optionally updates the install."""

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "取消")]

    def compose(self) -> ComposeResult:
        with Vertical(id="self-update-box"):
            yield Static(CHECKING_MESSAGE, id="self-update-message")
            with Horizontal():
                yield Button(
                    "更新",
                    id="self-update-confirm",
                    variant="primary",
                    disabled=True,
                )
                yield Button("取消", id="self-update-cancel")

    def on_mount(self) -> None:
        self.query_one("#self-update-cancel", Button).focus()
        self._run_check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "self-update-confirm":
            self._start_update()
        elif event.button.id == "self-update-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _set_message(self, message: str) -> None:
        self.query_one("#self-update-message", Static).update(escape(message))

    def _call(self, callback, *args) -> None:
        """Hop back to the UI thread, tolerating an app that already quit."""
        try:
            self.app.call_from_thread(callback, *args)
        except RuntimeError:
            # Expected: the app shut down while the worker was still running.
            log.debug("UI callback dropped: app is not running", exc_info=True)
        except Exception:
            # A UI callback must never kill the worker, but a bug in the
            # callback is not a network failure: it has to stay visible.
            log.exception("UI callback failed")

    @work(thread=True, exclusive=True)
    def _run_check(self) -> None:
        try:
            check = self.app.release_checker()
        except Exception as exc:  # noqa: BLE001 - must never reach Textual's callbacks
            self._call(self._on_check_error, str(exc))
            return
        if check is None:
            self._call(self._on_latest)
        else:
            self._call(self._on_newer, check)

    def _on_latest(self) -> None:
        if not self.is_attached:
            return
        self._set_message(f"已是最新版本（v{__version__}），无需更新。")

    def _on_newer(self, check: UpdateCheck) -> None:
        if not self.is_attached:
            return
        self._set_message(
            f"当前 v{check.current} → 最新 v{check.latest.version}\n"
            "更新将执行 git pull --ff-only 与 uv 重装，完成后需重启 wwmm。"
        )
        confirm = self.query_one("#self-update-confirm", Button)
        confirm.disabled = False
        confirm.focus()

    def _on_check_error(self, message: str) -> None:
        self._show_error(f"检查更新失败：{message}", title="检查更新失败")

    def _start_update(self) -> None:
        confirm = self.query_one("#self-update-confirm", Button)
        if confirm.disabled:
            return
        confirm.disabled = True
        self._set_message(UPDATING_MESSAGE)
        self._run_update()

    @work(thread=True, exclusive=True)
    def _run_update(self) -> None:
        try:
            result = self.app.self_updater(find_repo_root())
        except Exception as exc:  # noqa: BLE001 - must never reach Textual's callbacks
            self._call(self._on_update_error, str(exc))
            return
        self._call(self._on_updated, result)

    def _on_updated(self, result: SelfUpdateResult) -> None:
        if not self.is_attached:
            return
        self.notify(f"已更新到 v{result.new_version}，重启 wwmm 后生效")
        self.dismiss(None)

    def _on_update_error(self, message: str) -> None:
        # The message already names the failing stage (git pull, uv tool install),
        # so never prefix it with a blanket "更新失败".
        self._show_error(message, title="自更新未完成")

    def _show_error(self, message: str, *, title: str) -> None:
        if not self.is_attached:
            return
        escaped = escape(message)
        self.query_one("#self-update-message", Static).update(escaped)
        self.query_one("#self-update-confirm", Button).disabled = True
        self.notify(escaped, title=title, severity="error")
