from pathlib import Path

from textual.widgets import Input, ListView, Static

from wwmm.screens.characters import CharactersScreen
from wwmm.screens.mods import ModsScreen


async def test_lists_mods_and_details(app):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        screen = app.screen
        labels = [
            str(item.query_one(Static).content)
            for item in screen.query_one("#mods", ListView).children
        ]
        assert any("达妮娅-红绳捆绑" in label and "2 ini" in label for label in labels)
        detail = str(screen.query_one("#mod-detail", Static).content)
        assert "达妮娅-红绳捆绑" in detail


async def test_space_toggles_folder(app, mods_tree):
    denia = mods_tree / "character" / "denia"
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert (denia / "DISABLED_达妮娅-红绳捆绑").is_dir()
        assert app.last_toggle is not None
        assert app.last_toggle.enabled is False


async def test_toggle_collision_shows_error_and_keeps_files(app, mods_tree):
    denia = mods_tree / "character" / "denia"
    (denia / "Foo").mkdir()
    (denia / "DISABLED_Foo").mkdir()
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        lv = app.screen.query_one("#mods", ListView)
        lv.index = 0
        await pilot.press("space")
        await pilot.pause()
        assert (denia / "Foo").is_dir()
        assert (denia / "DISABLED_Foo").is_dir()
        assert app.last_error


async def test_back_rescans_parent_counts(app, mods_tree):
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(CharactersScreen("热熔"))
        await pilot.pause()
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert app.snapshot.find("denia").enabled_count == 0
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, CharactersScreen)
        assert app.snapshot.find("denia").enabled_count == 0


async def test_c_copies_selected_mod_path(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        screen = app.screen
        mod = screen.visible_mods[0]
        await pilot.press("c")
        await pilot.pause()
        assert app.clipboard == str(mod.path)
        assert "达妮娅-红绳捆绑" in app.clipboard


async def test_c_copies_disabled_mod_path(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    notifications = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("aemeath"))
        await pilot.pause()
        screen = app.screen
        list_view = screen.query_one("#mods", ListView)
        index = next(
            position for position, mod in enumerate(screen.visible_mods) if not mod.enabled
        )
        list_view.index = index
        await pilot.press("c")
        await pilot.pause()
        path = str(screen.visible_mods[index].path.absolute())
        assert app.clipboard == path
        assert "DISABLED_" in app.clipboard
        assert notifications[-1][0] == path
        assert notifications[-1][1]["markup"] is False


async def test_c_in_mod_filter_does_not_copy(app, monkeypatch):
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        await pilot.press("slash")
        await pilot.press("c")
        await pilot.pause()
        assert app.screen.query_one("#mod-filter", Input).value == "c"
        assert app.clipboard == ""


async def test_c_copies_absolute_path_for_relative_mods_dir(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("wwmm.app.copy_with_command", lambda text: True)
    app.config.mods_dir = Path("Mods")
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ModsScreen("denia"))
        await pilot.pause()
        screen = app.screen
        mod = screen.visible_mods[0]
        await pilot.press("c")
        await pilot.pause()
        assert Path(app.clipboard).is_absolute()
        assert Path(app.clipboard) == tmp_path / "Mods/character/denia" / mod.folder_name
