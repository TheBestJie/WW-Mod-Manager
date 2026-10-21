from textual.containers import VerticalScroll
from textual.widgets import Input, ListView, OptionList, Static
from textual.widgets.option_list import Option

from wwmm.hotkeys import Hotkey, HotkeyKind
from wwmm.models import Mod
from wwmm.screens.hotkey_edit import HotkeyEditScreen
from wwmm.screens.hotkeys import HotkeysScreen
from wwmm.screens.mods import ModsScreen


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


def _option_list(screen) -> OptionList:
    return screen.query_one("#hotkeys", OptionList)


def _group_headers(option_list: OptionList) -> list[Option]:
    return [option for option in option_list.options if _is_group(option)]


def _rows(option_list: OptionList) -> list[Option]:
    return [option for option in option_list.options if not _is_group(option)]


def _is_group(option: Option) -> bool:
    return (option.id or "").startswith("hotkey-group-")


def _prompt(option) -> str:
    return str(option.prompt)


async def test_modal_groups_rows_and_renders_brackets(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), _sample()))
        await pilot.pause()
        screen = app.screen
        option_list = _option_list(screen)
        assert [_prompt(option) for option in _group_headers(option_list)] == [
            "切换 · 3 项",
            "长按 · 1 项",
            "其他 · 1 项",
        ]

        rows = [_prompt(option) for option in _rows(option_list)]
        assert len(rows) == 5
        assert any("Ctrl+0" in row and "KeyHair" in row for row in rows)
        assert any("Alt+↑" in row and "[X]" in row for row in rows)
        assert any("KeyCycle" in row and "反向" in row for row in rows)
        assert any("mod.ini" in row for row in rows)

        # 分组头与行严格 1:1 对齐，分组头位置为 None。
        assert len(screen._option_hotkeys) == option_list.option_count
        headers = [index for index, item in enumerate(screen._option_hotkeys) if item is None]
        assert headers == [0, 4, 6]


async def test_modal_hint_points_at_r_edit(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), _sample()))
        await pilot.pause()
        hint = app.screen.query_one("#hotkeys-hint", Static)
        assert "↑↓ 选择 · R 修改 · Esc 关闭" in str(hint.content)


async def test_modal_warns_when_mod_disabled(app, tmp_path):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path, enabled=False), _sample()))
        await pilot.pause()
        screen = app.screen
        warning = screen.query_one("#hotkey-warning", Static)
        assert "不会生效" in str(warning.content)
        assert screen.hotkeys
        assert any("Ctrl+0" in _prompt(option) for option in _rows(_option_list(screen)))


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
        # #hotkeys-scroll 只做布局容器，滚动由 OptionList 自己承担。
        assert app.screen.query_one("#hotkeys-scroll", VerticalScroll)
        option_list = _option_list(app.screen)
        assert option_list.max_scroll_y > 0

        option_list.action_last()
        await pilot.pause()
        assert option_list.highlighted == option_list.option_count - 1
        assert option_list.scroll_y > 0


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


async def test_r_opens_edit_for_highlighted_hotkey(app, tmp_path, monkeypatch):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), _sample()))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HotkeysScreen)
        assert any(binding.key == "r" for binding in screen.BINDINGS)

        option_list = _option_list(screen)
        option_list.highlighted = option_list.get_option_index("hotkey-0")
        await pilot.pause()

        resolved: list[Hotkey | None] = []
        original = screen._highlighted_hotkey

        def spy() -> Hotkey | None:
            hotkey = original()
            resolved.append(hotkey)
            return hotkey

        monkeypatch.setattr(screen, "_highlighted_hotkey", spy)
        await pilot.press("r")
        await pilot.pause()

        # 编辑屏在任务 3 接入：R 命中当前高亮行并打开编辑屏。
        assert [hotkey.display_key for hotkey in resolved if hotkey is not None] == ["Ctrl+0"]
        assert isinstance(app.screen, HotkeyEditScreen)
        assert app.screen.query_one("#hotkey-edit-box")


async def test_r_noop_when_no_hotkeys(app, tmp_path):
    mod = Mod(path=tmp_path, folder_name="Empty", enabled=True, ini_count=0)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(mod, []))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HotkeysScreen)
        assert _option_list(screen).highlighted is None
        assert screen._highlighted_hotkey() is None
        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, HotkeysScreen)


def _write_hotkeys(path):
    path.write_text("[KeyHair]\nkey = CTRL 0\ntype = cycle\n", encoding="utf-8")


async def test_m_opens_hotkeys_for_selected_mod(app, mods_tree):
    _write_hotkeys(mods_tree / "character" / "denia" / "达妮娅-红绳捆绑" / "mod.ini")
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HotkeysScreen)
        assert [(h.section, h.display_key) for h in screen.hotkeys] == [("KeyHair", "Ctrl+0")]
        headers = [_prompt(option) for option in _group_headers(_option_list(screen))]
        assert headers == ["切换 · 1 项"]


async def test_m_warns_for_disabled_mod(app, mods_tree):
    _write_hotkeys(mods_tree / "character" / "denia" / "达妮娅-红绳捆绑" / "mod.ini")
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HotkeysScreen)
        assert "不会生效" in str(screen.query_one("#hotkey-warning", Static).content)
        assert [(h.section, h.display_key) for h in screen.hotkeys] == [("KeyHair", "Ctrl+0")]
        assert len(_rows(_option_list(screen))) == 1


async def test_m_shows_empty_state_without_keys(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        assert "没有声明" in str(app.screen.query_one("#hotkey-empty", Static).content)


async def test_escape_returns_to_mod_list(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ModsScreen)


async def test_m_does_not_hijack_filter_input(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, ModsScreen)
        assert app.screen.query_one("#mod-filter", Input).value == "m"


async def test_modal_does_not_truncate_long_key(app, tmp_path):
    hotkeys = [Hotkey("Ctrl+Alt+Shift+小键盘 1", "KeyLong", "mod.ini", HotkeyKind.SWITCH)]
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HotkeysScreen(_mod(tmp_path), hotkeys))
        await pilot.pause()
        rows = [_prompt(option) for option in _rows(_option_list(app.screen))]
        assert len(rows) == 1
        assert "Ctrl+Alt+Shift+小键盘 1" in rows[0]


async def test_closing_hotkey_modal_keeps_selection_and_skips_rescan(app, mods_tree, monkeypatch):
    denia = mods_tree / "character" / "denia"
    (denia / "Foo").mkdir()
    disabled = denia / "DISABLED_Foo"
    disabled.mkdir()
    (disabled / "mod.ini").write_text("[KeyHair]\nkey = CTRL 0\ntype = cycle\n", encoding="utf-8")

    calls = 0
    original = app.reload_snapshot

    def counting():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(app, "reload_snapshot", counting)

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        screen = app.screen
        list_view = screen.query_one("#mods", ListView)
        index = next(
            position
            for position, mod in enumerate(screen.visible_mods)
            if mod.folder_name == "DISABLED_Foo"
        )
        list_view.index = index
        await pilot.pause()
        calls_before = calls

        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, HotkeysScreen)
        await pilot.press("escape")
        await pilot.pause()

        assert calls == calls_before
        assert screen.visible_mods[list_view.index].folder_name == "DISABLED_Foo"
