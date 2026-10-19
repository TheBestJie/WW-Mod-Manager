from textual.widgets import ListView

from wwmm.screens.characters import CharactersScreen
from wwmm.screens.settings import SettingsScreen


async def test_home_lists_all_groups(app):
    async with app.run_test(size=(100, 30)):
        lv = app.screen.query_one("#groups", ListView)
        assert len(lv.children) >= 8
        assert app.screen.group_names[:8] == [
            "冷凝",
            "热熔",
            "导电",
            "气动",
            "衍射",
            "湮灭",
            "多属性",
            "其他",
        ]
        assert "未分类" in app.screen.group_names  # 测试 fixture 里有 unknown 目录


async def test_enter_group_opens_characters(app):
    async with app.run_test(size=(100, 30)) as pilot:
        lv = app.screen.query_one("#groups", ListView)
        lv.index = 1  # 热熔
        await pilot.press("enter")
        assert isinstance(app.screen, CharactersScreen)
        assert app.screen.group == "热熔"


async def test_missing_mods_dir_opens_settings(app_without_mods):
    async with app_without_mods.run_test():
        assert isinstance(app_without_mods.screen, SettingsScreen)


async def test_startup_creates_missing_folders(sparse_app):
    async with sparse_app.run_test():
        assert (sparse_app.config.mods_dir / "character" / "aemeath").is_dir()
        assert (sparse_app.config.mods_dir / "character" / "others").is_dir()
        assert sparse_app.created_dirs
