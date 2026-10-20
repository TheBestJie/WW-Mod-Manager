from textual.widgets import Input, ListView

from wwmm.screens.characters import CharactersScreen
from wwmm.screens.home import HomeScreen
from wwmm.screens.mods import ModsScreen


async def test_lists_characters_with_counts(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        assert app.screen.visible_slugs == ["aemeath", "denia"]  # 都有 mod，按中文名排序


async def test_filter_and_hide_empty(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        screen = app.screen
        await pilot.press("slash")
        await pilot.press("d", "n")
        await pilot.pause()
        assert screen.visible_slugs == ["denia"]

        app.push_screen(CharactersScreen("衍射"))
        await pilot.pause()
        empty_screen = app.screen
        assert empty_screen.visible_slugs == ["lynae"]
        await pilot.press("h")
        await pilot.pause()
        assert empty_screen.visible_slugs == []
        await pilot.press("h")
        await pilot.pause()
        assert empty_screen.visible_slugs == ["lynae"]


async def test_enter_opens_mods_screen(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        lv = app.screen.query_one("#characters", ListView)
        lv.index = 1
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ModsScreen)
        assert app.screen.slug == "denia"


async def test_escape_returns_home(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


async def test_c_copies_character_path(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        list_view = app.screen.query_one("#characters", ListView)
        list_view.index = 1
        await pilot.press("c")
        await pilot.pause()
        assert app.clipboard == str(app.snapshot.find("denia").path)


async def test_c_in_filter_does_not_copy(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        await pilot.press("slash")
        await pilot.press("c")
        await pilot.pause()
        assert app.screen.query_one("#char-filter", Input).value == "c"
        assert app.clipboard == ""


async def test_c_still_copies_when_desktop_tool_missing(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: False)
    notifications = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        list_view = app.screen.query_one("#characters", ListView)
        list_view.index = 1
        await pilot.press("c")
        await pilot.pause()
        path = str(app.snapshot.find("denia").path.absolute())
        assert app.clipboard == path
        assert notifications[-1][0].startswith(path)
        assert "终端 OSC 52" in notifications[-1][0]
        assert notifications[-1][1]["severity"] == "warning"
        assert notifications[-1][1]["markup"] is False


async def test_c_notification_keeps_path_literal(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    notifications = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        list_view = app.screen.query_one("#characters", ListView)
        list_view.index = 1
        await pilot.press("c")
        await pilot.pause()
        assert notifications[-1][0] == str(app.snapshot.find("denia").path.absolute())
        assert notifications[-1][1]["markup"] is False
