import pytest
from textual.widgets import Button, Input, Static

from wwmm.app import WWMMApp
from wwmm.config import Config, ConfigStore
from wwmm.errors import LayoutError
from wwmm.paths import detect_mods_dirs
from wwmm.screens.home import HomeScreen
from wwmm.screens.settings import SettingsScreen


def _offline_release_checker(**kwargs):
    return


def _unsafe_self_updater(repo_root):
    raise AssertionError(f"tests must monkeypatch self_updater (got {repo_root})")


def _app_with_mods_dir(tmp_path, roster, mods_dir):
    store = ConfigStore(tmp_path / "config")
    config = Config(mods_dir=mods_dir, auto_create_folders=True)
    store.save(config)
    return WWMMApp(
        config_store=store,
        config=config,
        roster=roster,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        home_dir=tmp_path / "home",
        release_checker=_offline_release_checker,
        self_updater=_unsafe_self_updater,
    )


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


async def test_invalid_configured_dir_shows_settings_without_creating(tmp_path, roster):
    plain = tmp_path / "plain"
    plain.mkdir()
    app = _app_with_mods_dir(tmp_path, roster, plain)
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, SettingsScreen)
        assert app.last_error
        assert not (plain / "character").exists()
        status = str(app.screen.query_one("#settings-status", Static).content)
        assert "不是有效的" in status


def test_set_mods_dir_rejects_invalid_dir(app_without_mods, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(LayoutError):
        app_without_mods.set_mods_dir(plain)
    assert app_without_mods.config.mods_dir is None
    assert not (plain / "character").exists()


async def test_settings_prefills_current_dir(app, mods_tree):
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)
        assert app.screen.query_one("#mods-path", Input).value == str(mods_tree)


def test_detect_mods_dirs(tmp_path):
    home = tmp_path / "home"
    mods = (
        home / ".proton" / "pfx" / "drive_c" / "Program Files" / "XXMI Launcher" / "WWMI" / "Mods"
    )
    (mods / "character").mkdir(parents=True)
    assert detect_mods_dirs(home) == [mods]
