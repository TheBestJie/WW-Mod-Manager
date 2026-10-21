"""TUI tests for editing one mod hotkey and writing it back to the ini."""

from textual.widgets import Input, OptionList, Static

from wwmm.errors import HotkeyEditError
from wwmm.screens.hotkey_edit import HotkeyEditScreen
from wwmm.screens.hotkeys import HotkeysScreen
from wwmm.screens.mods import ModsScreen

INI = "[KeyHair]\nkey = CTRL 0\ntype = cycle\n"
TWO_KEYS_INI = "[KeyHair]\nkey = CTRL 0\nkey = CTRL 1\ntype = cycle\n"
TWO_GROUPS_INI = (
    "[KeyHair]\nkey = CTRL 0\ntype = cycle\n"
    "\n"
    "[KeyHold]\nkey = CTRL 1\ntype = hold\n"
)


def _mod_ini(mods_tree):
    return mods_tree / "character" / "denia" / "达妮娅-红绳捆绑" / "mod.ini"


def _write(path, text=INI):
    path.write_text(text, encoding="utf-8")
    return path


async def _open_hotkeys(app, pilot):
    app.push_screen(ModsScreen("denia"))
    await pilot.pause()
    await pilot.press("m")
    await pilot.pause()
    assert isinstance(app.screen, HotkeysScreen)
    return app.screen


async def _open_editor(app, pilot):
    screen = await _open_hotkeys(app, pilot)
    await pilot.press("r")
    await pilot.pause()
    editor = app.screen
    assert isinstance(editor, HotkeyEditScreen)
    return screen, editor


async def test_edit_flow_rewrites_ini(app, mods_tree):
    ini = _write(_mod_ini(mods_tree))
    async with app.run_test(size=(100, 30)) as pilot:
        screen, editor = await _open_editor(app, pilot)
        assert editor.query_one("#hotkey-edit-input", Input).value == "CTRL 0"
        header = str(editor.query_one("#hotkey-edit-header", Static).content)
        assert "KeyHair" in header

        editor.query_one("#hotkey-edit-input", Input).value = "ctrl k"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, HotkeyEditScreen)
        assert ini.read_text(encoding="utf-8") == "[KeyHair]\nkey = ctrl k\ntype = cycle\n"
        assert [(hotkey.section, hotkey.display_key) for hotkey in screen.hotkeys] == [
            ("KeyHair", "Ctrl+K")
        ]
        option_list = screen.query_one("#hotkeys", OptionList)
        highlighted = option_list.highlighted
        assert highlighted is not None
        assert screen._option_hotkeys[highlighted].display_key == "Ctrl+K"
        assert "Ctrl+K" in str(option_list.get_option_at_index(highlighted).prompt)


async def test_edit_preview_updates_live(app, mods_tree):
    _write(_mod_ini(mods_tree))
    async with app.run_test(size=(100, 30)) as pilot:
        _, editor = await _open_editor(app, pilot)
        editor.query_one("#hotkey-edit-input", Input).value = "ctrl alt k"
        await pilot.pause()
        assert str(editor.query_one("#hotkey-edit-preview", Static).content) == "Ctrl+Alt+K"
        assert str(editor.query_one("#hotkey-edit-error", Static).content) == ""


async def test_invalid_input_stays_open(app, mods_tree):
    ini = _write(_mod_ini(mods_tree))
    async with app.run_test(size=(100, 30)) as pilot:
        _, editor = await _open_editor(app, pilot)
        editor.query_one("#hotkey-edit-input", Input).value = "ctrl 中文"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, HotkeyEditScreen)
        error = str(editor.query_one("#hotkey-edit-error", Static).content)
        assert "不支持的按键" in error
        assert ini.read_text(encoding="utf-8") == INI


async def test_escape_cancels_without_write(app, mods_tree):
    ini = _write(_mod_ini(mods_tree))
    async with app.run_test(size=(100, 30)) as pilot:
        _, editor = await _open_editor(app, pilot)
        editor.query_one("#hotkey-edit-input", Input).value = "ctrl k"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, HotkeysScreen)
        assert ini.read_text(encoding="utf-8") == INI


async def test_edit_second_key_occurrence(app, mods_tree):
    ini = _write(_mod_ini(mods_tree), TWO_KEYS_INI)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await _open_hotkeys(app, pilot)
        option_list = screen.query_one("#hotkeys", OptionList)
        option_list.highlighted = option_list.get_option_index("hotkey-1")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, HotkeyEditScreen)
        assert editor.query_one("#hotkey-edit-input", Input).value == "CTRL 1"

        editor.query_one("#hotkey-edit-input", Input).value = "ctrl 9"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, HotkeyEditScreen)
        assert ini.read_text(encoding="utf-8") == (
            "[KeyHair]\nkey = CTRL 0\nkey = ctrl 9\ntype = cycle\n"
        )


async def test_edit_write_failure_notifies(app, mods_tree, monkeypatch):
    ini = _write(_mod_ini(mods_tree))
    notifications = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )

    def boom(*args, **kwargs):
        raise HotkeyEditError("boom")

    monkeypatch.setattr("wwmm.screens.hotkeys.apply_hotkey", boom)

    async with app.run_test(size=(100, 30)) as pilot:
        screen, _ = await _open_editor(app, pilot)
        editor = app.screen
        editor.query_one("#hotkey-edit-input", Input).value = "ctrl k"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, HotkeyEditScreen)
        assert isinstance(app.screen, HotkeysScreen)
        assert notifications
        message, kwargs = notifications[-1]
        assert message == "boom"
        assert kwargs["title"] == "修改失败"
        assert kwargs["severity"] == "error"
        assert [hotkey.display_key for hotkey in screen.hotkeys] == ["Ctrl+0"]
        assert ini.read_text(encoding="utf-8") == INI


async def test_edit_oserror_notifies_without_crashing(app, mods_tree, monkeypatch):
    ini = _write(_mod_ini(mods_tree))
    notifications = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("wwmm.screens.hotkeys.apply_hotkey", boom)

    async with app.run_test(size=(100, 30)) as pilot:
        screen, _ = await _open_editor(app, pilot)
        editor = app.screen
        editor.query_one("#hotkey-edit-input", Input).value = "ctrl k"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, HotkeyEditScreen)
        assert isinstance(app.screen, HotkeysScreen)
        assert notifications
        message, kwargs = notifications[-1]
        assert message == "disk full"
        assert kwargs["title"] == "修改失败"
        assert kwargs["severity"] == "error"
        assert [hotkey.display_key for hotkey in screen.hotkeys] == ["Ctrl+0"]
        assert ini.read_text(encoding="utf-8") == INI

        # The app survived: the screen still responds to its own bindings.
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ModsScreen)


async def test_reload_keeps_option_hotkeys_aligned_across_groups(app, mods_tree):
    _write(_mod_ini(mods_tree), TWO_GROUPS_INI)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await _open_hotkeys(app, pilot)
        option_list = screen.query_one("#hotkeys", OptionList)
        option_list.highlighted = 1
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, HotkeyEditScreen)
        editor.query_one("#hotkey-edit-input", Input).value = "ctrl k"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        option_list = screen.query_one("#hotkeys", OptionList)
        assert option_list.option_count == len(screen._option_hotkeys)
        headers = [
            index for index, hotkey in enumerate(screen._option_hotkeys) if hotkey is None
        ]
        assert headers == [0, 2]
        assert [hotkey.display_key for hotkey in screen.hotkeys] == ["Ctrl+K", "Ctrl+1"]
        assert [
            hotkey.display_key for hotkey in screen._option_hotkeys if hotkey is not None
        ] == ["Ctrl+K", "Ctrl+1"]
