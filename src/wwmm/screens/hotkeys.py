"""Modal screen listing the hotkeys declared by one mod."""

from __future__ import annotations

from typing import ClassVar

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from wwmm.errors import HotkeyEditError
from wwmm.hotkey_edit import apply_hotkey
from wwmm.hotkeys import Hotkey, HotkeyKind, format_key, parse_mod_hotkeys
from wwmm.models import Mod
from wwmm.screens.hotkey_edit import HotkeyEditScreen

# Width of the key column in a row prompt, in terminal cells.
_KEY_WIDTH = 14


class HotkeysScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("r", "edit_selected", "修改"),
        Binding("m", "close", "关闭"),
        Binding("escape", "close", "关闭"),
    ]

    def __init__(self, mod: Mod, hotkeys: list[Hotkey]) -> None:
        super().__init__()
        self.mod = mod
        self.hotkeys = list(hotkeys)
        # Parallel to the OptionList options: one entry per option index, where a
        # ``None`` marks a group header (not editable) and a ``Hotkey`` marks a
        # selectable row.
        self._option_hotkeys: list[Hotkey | None] = []

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
                yield self._build_option_list()
            yield Static(
                Text("↑↓ 选择 · R 修改 · Esc 关闭", style="dim"),
                id="hotkeys-hint",
            )

    def on_mount(self) -> None:
        option_list = self.query_one("#hotkeys", OptionList)
        option_list.focus()
        first = self._first_row_index()
        if first is not None:
            option_list.highlighted = first

    @property
    def grouped(self) -> list[tuple[HotkeyKind, list[Hotkey]]]:
        groups: list[tuple[HotkeyKind, list[Hotkey]]] = []
        for kind in HotkeyKind:
            rows = [hotkey for hotkey in self.hotkeys if hotkey.kind is kind]
            if rows:
                groups.append((kind, rows))
        return groups

    def action_edit_selected(self) -> None:
        """Hand the highlighted hotkey to the editor screen."""
        hotkey = self._highlighted_hotkey()
        if hotkey is None:
            return
        self.app.push_screen(HotkeyEditScreen(self.mod, hotkey), callback=self._on_edit)

    def _on_edit(self, new_raw: str | None) -> None:
        """Write the edited key back to the ini and refresh the list in place."""
        hotkey = self._highlighted_hotkey()
        if new_raw is None or hotkey is None:
            return
        try:
            apply_hotkey(
                self.mod.path,
                hotkey.source,
                hotkey.section,
                hotkey.field,
                hotkey.occurrence,
                new_raw,
            )
        except (HotkeyEditError, OSError) as exc:
            self.notify(str(exc), title="修改失败", severity="error")
            return
        self.hotkeys = parse_mod_hotkeys(self.mod.path)
        self._reload_options()
        self.notify(f"已修改 {hotkey.section}：{hotkey.display_key} → {format_key(new_raw)}")

    def action_close(self) -> None:
        self.dismiss(None)

    def _build_option_list(self) -> OptionList:
        return OptionList(*self._options(), id="hotkeys", markup=False)

    def _reload_options(self) -> None:
        """Rebuild the option list in place, keeping the highlight where it was."""
        option_list = self.query_one("#hotkeys", OptionList)
        highlighted = option_list.highlighted
        option_list.clear_options()
        option_list.add_options(self._options())
        if highlighted is not None and option_list.option_count:
            option_list.highlighted = min(highlighted, option_list.option_count - 1)
        self.query_one("#hotkeys-header", Static).update(self._header())

    def _options(self) -> list[Option | None]:
        options: list[Option | None] = []
        self._option_hotkeys = []
        groups = self.grouped
        row = 0
        for position, (kind, rows) in enumerate(groups):
            options.append(
                Option(
                    Text(f"{kind.value} · {len(rows)} 项"),
                    id=f"hotkey-group-{kind.name.lower()}",
                    disabled=True,
                )
            )
            self._option_hotkeys.append(None)
            for hotkey in rows:
                options.append(Option(self._row(hotkey), id=f"hotkey-{row}"))
                self._option_hotkeys.append(hotkey)
                row += 1
            if position < len(groups) - 1:
                # A ``None`` option only draws a rule under the previous option.
                options.append(None)
        return options

    def _row(self, hotkey: Hotkey) -> Text:
        key = hotkey.display_key
        padding = " " * max(1, _KEY_WIDTH - cell_len(key))
        section = hotkey.section + (" · 反向" if hotkey.back else "")
        return Text.assemble(
            (key, "bold yellow"),
            padding,
            section,
            ("  " + hotkey.source, "dim"),
        )

    def _first_row_index(self) -> int | None:
        for index, hotkey in enumerate(self._option_hotkeys):
            if hotkey is not None:
                return index
        return None

    def _highlighted_hotkey(self) -> Hotkey | None:
        """Return the hotkey of the highlighted row, or ``None`` for headers."""
        if not self.hotkeys:
            return None
        index = self.query_one("#hotkeys", OptionList).highlighted
        if index is None or not (0 <= index < len(self._option_hotkeys)):
            return None
        return self._option_hotkeys[index]

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
