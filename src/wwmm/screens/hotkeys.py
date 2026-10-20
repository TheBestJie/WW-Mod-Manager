"""Modal screen listing the hotkeys declared by one mod."""

from __future__ import annotations

from typing import ClassVar

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from wwmm.hotkeys import Hotkey, HotkeyKind
from wwmm.models import Mod


class HotkeysScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "关闭"),
        Binding("m", "close", "关闭"),
    ]

    def __init__(self, mod: Mod, hotkeys: list[Hotkey]) -> None:
        super().__init__()
        self.mod = mod
        self.hotkeys = list(hotkeys)

    def compose(self) -> ComposeResult:
        with Vertical(id="hotkeys-box"):
            yield Static(self._header(), id="hotkeys-header")
            if not self.mod.enabled:
                yield Static(
                    Text("该 mod 已禁用，以下快捷键在游戏中不会生效。", style="yellow"),
                    id="hotkey-warning",
                )
            with VerticalScroll(id="hotkeys-scroll"):
                if not self.hotkeys:
                    yield Static(Text(self._empty_message(), style="dim"), id="hotkey-empty")
                else:
                    for kind, rows in self.grouped:
                        yield Static(
                            Text(f"{kind.value} · {len(rows)} 项"),
                            id=f"hotkey-group-{kind.name.lower()}",
                            classes="hotkey-group",
                        )
                        yield Static(
                            self._table(rows),
                            id=f"hotkeys-table-{kind.name.lower()}",
                            classes="hotkey-table",
                        )
            yield Static(
                Text("↑↓ / PgUp / PgDn 滚动 · Esc 关闭", style="dim"),
                id="hotkeys-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#hotkeys-scroll", VerticalScroll).focus()

    @property
    def grouped(self) -> list[tuple[HotkeyKind, list[Hotkey]]]:
        groups: list[tuple[HotkeyKind, list[Hotkey]]] = []
        for kind in HotkeyKind:
            rows = [hotkey for hotkey in self.hotkeys if hotkey.kind is kind]
            if rows:
                groups.append((kind, rows))
        return groups

    def _header(self) -> Text:
        state = "已启用" if self.mod.enabled else "已禁用"
        return Text.assemble(
            (self.mod.display_name, "bold"),
            f" · {state} · {len(self.hotkeys)} 个快捷键",
        )

    def _empty_message(self) -> str:
        if self.mod.ini_count == 0:
            return "该 mod 没有 ini 文件"
        return "该 mod 的 ini 里没有声明 [Key...] 快捷键"

    def _table(self, rows: list[Hotkey]) -> Table:
        table = Table(
            box=None,
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            expand=True,
        )
        table.add_column("按键", style="bold yellow", min_width=14, no_wrap=True)
        table.add_column("功能（ini 段落）", ratio=3, no_wrap=True, overflow="ellipsis")
        table.add_column("来源", style="dim", ratio=2, no_wrap=True, overflow="ellipsis")
        for hotkey in rows:
            section = hotkey.section + (" · 反向" if hotkey.back else "")
            table.add_row(Text(hotkey.display_key), Text(section), Text(hotkey.source))
        return table

    def action_close(self) -> None:
        self.dismiss(None)
