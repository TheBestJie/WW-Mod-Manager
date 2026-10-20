import io

from rich.console import Console
from textual.containers import VerticalScroll
from textual.widgets import Static

from wwmm.hotkeys import Hotkey, HotkeyKind
from wwmm.models import Mod
from wwmm.screens.hotkeys import HotkeysScreen


def _mod(tmp_path, *, enabled: bool = True) -> Mod:
    name = "Test Mod" if enabled else "DISABLED_Test Mod"
    return Mod(path=tmp_path, folder_name=name, enabled=enabled, ini_count=1)


def _sample() -> list[Hotkey]:
    return [
        Hotkey("Ctrl+0", "KeyHair", "mod.ini", HotkeyKind.SWITCH),
        Hotkey("Alt+↑", "KeyHat", "Sub/[X]/mod.ini", HotkeyKind.SWITCH),
        Hotkey("Q", "KeyCycle", "mod.ini", HotkeyKind.SWITCH, True),
        Hotkey("Ctrl", "KeyMenu", "mod.ini", HotkeyKind.HOLD),
        Hotkey("/", "KeyReset", "mod.ini", HotkeyKind.OTHER),
    ]


async def test_modal_groups_rows_and_renders_brackets(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), _sample()))
        await pilot.pause()
        screen = app.screen
        assert "切换 · 3 项" in str(screen.query_one("#hotkey-group-switch", Static).content)
        assert "长按 · 1 项" in str(screen.query_one("#hotkey-group-hold", Static).content)
        assert "其他 · 1 项" in str(screen.query_one("#hotkey-group-other", Static).content)

        table = screen.query_one("#hotkeys-table-switch", Static).content
        console = Console(width=100, record=True, file=io.StringIO())
        console.print(table)
        text = console.export_text()
        assert "Ctrl+0" in text
        assert "KeyHair" in text
        assert "[X]" in text
        assert "反向" in text


async def test_modal_warns_when_mod_disabled(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path, enabled=False), _sample()))
        await pilot.pause()
        warning = app.screen.query_one("#hotkey-warning", Static)
        assert "不会生效" in str(warning.content)


async def test_modal_shows_empty_state(app, tmp_path):
    mod = Mod(path=tmp_path, folder_name="Empty", enabled=True, ini_count=0)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(mod, []))
        await pilot.pause()
        assert "没有 ini 文件" in str(app.screen.query_one("#hotkey-empty", Static).content)


async def test_modal_scrolls_long_list(app, tmp_path):
    hotkeys = [Hotkey(f"Ctrl+{i}", f"Key{i}", "mod.ini", HotkeyKind.SWITCH) for i in range(60)]
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), hotkeys))
        await pilot.pause()
        scroll = app.screen.query_one("#hotkeys-scroll", VerticalScroll)
        assert scroll.max_scroll_y > 0


async def test_escape_closes_modal(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), _sample()))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HotkeysScreen)


async def test_m_closes_modal(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), _sample()))
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        assert not isinstance(app.screen, HotkeysScreen)
