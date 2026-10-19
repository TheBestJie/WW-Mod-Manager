from wwmm.screens.home import HomeScreen
from wwmm.screens.mods import ModsScreen
from wwmm.screens.search import SearchScreen


async def test_slash_search_dn_jumps_to_denia(app):
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("/")
        assert isinstance(app.screen, SearchScreen)
        await pilot.press("d", "n")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ModsScreen)
        assert app.screen.slug == "denia"


async def test_element_alias_search(app):
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("/")
        await pilot.press("雷")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ModsScreen)
        assert app.screen.slug == "hsin"


async def test_escape_closes_search(app):
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("/")
        assert isinstance(app.screen, SearchScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
