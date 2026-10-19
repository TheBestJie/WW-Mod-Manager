from textual.widgets import Button, Input

from wwmm.paths import detect_mods_dirs
from wwmm.screens.home import HomeScreen
from wwmm.screens.settings import SettingsScreen


async def test_invalid_directory_is_rejected(app_without_mods, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    async with app_without_mods.run_test(size=(100, 30)) as pilot:
        screen = app_without_mods.screen
        assert isinstance(screen, SettingsScreen)
        screen.query_one("#mods-path", Input).value = str(plain)
        screen.query_one("#save-mods", Button).press()
        await pilot.pause()
        assert app_without_mods.config.mods_dir is None
        assert not (plain / "character").exists()


async def test_valid_mods_dir_is_saved_and_scanned(app_without_mods, tmp_path):
    mods = tmp_path / "Mods"
    (mods / "character").mkdir(parents=True)
    async with app_without_mods.run_test(size=(100, 30)) as pilot:
        screen = app_without_mods.screen
        screen.query_one("#mods-path", Input).value = str(mods)
        screen.query_one("#save-mods", Button).press()
        await pilot.pause()
        assert app_without_mods.config.mods_dir == mods
        assert app_without_mods.config_store.load().mods_dir == mods
        assert (mods / "character" / "aemeath").is_dir()
        assert isinstance(app_without_mods.screen, HomeScreen)


def test_detect_mods_dirs(tmp_path):
    home = tmp_path / "home"
    mods = (
        home
        / ".proton"
        / "pfx"
        / "drive_c"
        / "Program Files"
        / "XXMI Launcher"
        / "WWMI"
        / "Mods"
    )
    (mods / "character").mkdir(parents=True)
    assert detect_mods_dirs(home) == [mods]
