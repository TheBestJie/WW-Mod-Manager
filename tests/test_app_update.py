import asyncio
from pathlib import Path

from wwmm.errors import RosterUpdateError
from wwmm.roster_update import UpdateResult


async def _wait_for(pilot, predicate, attempts=100):
    for _ in range(attempts):
        if predicate():
            return True
        await pilot.pause()
        await asyncio.sleep(0.01)
    return predicate()


async def test_update_success_refreshes_roster(app, tmp_path):
    def fake_updater(**kwargs):
        app.data_dir.mkdir(parents=True, exist_ok=True)
        (app.data_dir / "roster.json").write_text(
            (Path("tests/fixtures/roster.json")).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return UpdateResult(
            game_version="test",
            added=(),
            removed=(),
            changed=(),
            path=app.data_dir / "roster.json",
            dry_run=False,
        )

    app.updater = fake_updater
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("enter")
        assert await _wait_for(pilot, lambda: app.last_update is not None)
        assert app.last_update.game_version == "test"


async def test_update_failure_keeps_roster(app):
    def fake_updater(**kwargs):
        raise RosterUpdateError("network down")

    app.updater = fake_updater
    before = app.roster
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("enter")
        assert await _wait_for(pilot, lambda: bool(app.last_error))
        assert "network down" in (app.last_error or "")
        assert app.roster == before
