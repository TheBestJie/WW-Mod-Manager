"""Tests for the Ctrl+U self update screen.

Every check goes through the fake ``release_checker`` injected by the fixtures, so
nothing here touches the network, git or uv.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest
from textual.containers import Vertical
from textual.widgets import Button, Input, ListView, Static

from wwmm.errors import SelfUpdateError
from wwmm.screens.characters import CharactersScreen
from wwmm.screens.home import HomeScreen
from wwmm.screens.search import SearchScreen
from wwmm.screens.self_update import SelfUpdateScreen
from wwmm.self_update import (
    ReleaseInfo,
    SelfUpdateResult,
    UpdateCheck,
    check_for_update,
)

RELEASE_URL = "https://github.com/TheBestJie/WW-Mod-Manager/releases/tag/v1.4.0"


async def _wait_for(pilot, predicate, attempts=100):
    for _ in range(attempts):
        if predicate():
            return True
        await pilot.pause()
        await asyncio.sleep(0.01)
    return predicate()


def _message(app) -> str:
    return str(app.screen.query_one("#self-update-message", Static).content)


def _confirm(app) -> Button:
    return app.screen.query_one("#self-update-confirm", Button)


def _newer_check() -> UpdateCheck:
    return UpdateCheck(
        current="1.3.0",
        latest=ReleaseInfo(tag="v1.4.0", version="1.4.0", url=RELEASE_URL),
    )


def _capture_notifications(monkeypatch, app) -> list[tuple[str, dict]]:
    notifications: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )
    return notifications


def _update_notifications(notifications: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Notifications that could only come from the release check.

    The app itself already notifies about repaired character folders, so a plain
    "no notifications at all" assertion would be a lie.
    """
    return [
        entry
        for entry in notifications
        if entry[1].get("severity") == "error"
        or any(word in entry[0] for word in ("版本", "更新", "最新"))
    ]


async def _open(pilot) -> None:
    await pilot.press("ctrl+u")
    await pilot.pause()


async def test_ctrl_u_opens_screen(app):
    async with app.run_test(size=(100, 30)) as pilot:
        assert not isinstance(app.screen, SelfUpdateScreen)
        await _open(pilot)

        assert isinstance(app.screen, SelfUpdateScreen)
        assert isinstance(app.screen.query_one("#self-update-box"), Vertical)
        assert _confirm(app).disabled is True
        assert app.screen.query_one("#self-update-cancel", Button).disabled is False

        await pilot.press("ctrl+u")
        await pilot.pause()
        assert (
            len([screen for screen in app.screen_stack if isinstance(screen, SelfUpdateScreen)])
            == 1
        )


def test_conftest_default_updater_refuses_to_run(app, tmp_path):
    """A forgotten monkeypatch must fail loud instead of pulling the real checkout."""
    with pytest.raises(AssertionError, match="monkeypatch self_updater"):
        app.self_updater(tmp_path / "missing")


async def test_ctrl_u_wins_over_focused_input(app):
    """Input binds ctrl+u to delete_left_all, so the app binding needs priority."""
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("/")
        assert isinstance(app.screen, SearchScreen)
        await pilot.press("d")
        await pilot.pause()
        search_input = app.screen.query_one("#search-input", Input)
        assert search_input.value == "d"

        await pilot.press("ctrl+u")
        await pilot.pause()

        assert isinstance(app.screen, SelfUpdateScreen)
        assert isinstance(app.screen.query_one("#self-update-box"), Vertical)
        assert search_input.value == "d"


async def test_check_newer_shows_confirm(app, monkeypatch):
    monkeypatch.setattr(app, "release_checker", lambda **kwargs: _newer_check())
    calls: list[Path] = []

    def fake_update(repo_root):
        calls.append(repo_root)
        return SelfUpdateResult(new_version="1.4.0", reinstalled=True)

    monkeypatch.setattr(app, "self_updater", fake_update)
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        await _open(pilot)
        assert await _wait_for(pilot, lambda: "1.4.0" in _message(app))

        message = _message(app)
        assert "1.3.0" in message
        assert "1.4.0" in message
        assert "git pull --ff-only" in message
        assert _confirm(app).disabled is False

        await pilot.click("#self-update-confirm")
        assert await _wait_for(pilot, lambda: bool(notifications))

        assert "重启" in notifications[-1][0]
        assert await _wait_for(pilot, lambda: not isinstance(app.screen, SelfUpdateScreen))
        assert len(calls) == 1
        assert calls[0].is_dir()


async def test_check_latest_shows_ok(app):
    async with app.run_test(size=(100, 30)) as pilot:
        await _open(pilot)
        assert await _wait_for(pilot, lambda: "已是最新" in _message(app))
        assert _confirm(app).disabled is True
        assert isinstance(app.screen, SelfUpdateScreen)


async def test_check_error_shows_message(app, monkeypatch):
    def boom(**kwargs):
        raise SelfUpdateError("获取 GitHub release 失败：超时")

    monkeypatch.setattr(app, "release_checker", boom)
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        await _open(pilot)
        assert await _wait_for(pilot, lambda: "超时" in _message(app))

        assert _confirm(app).disabled is True
        assert isinstance(app.screen, SelfUpdateScreen)
        assert notifications
        assert "超时" in notifications[-1][0]
        assert notifications[-1][1]["severity"] == "error"


async def test_update_failure_shows_error(app, monkeypatch):
    monkeypatch.setattr(app, "release_checker", lambda **kwargs: _newer_check())

    def boom(repo_root):
        raise SelfUpdateError("git pull 失败：本地改动会被覆盖（冲突）")

    monkeypatch.setattr(app, "self_updater", boom)
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        await _open(pilot)
        assert await _wait_for(pilot, lambda: _confirm(app).disabled is False)

        await pilot.click("#self-update-confirm")
        assert await _wait_for(pilot, lambda: bool(notifications))

        message = _message(app)
        assert "git pull 失败" in message
        assert "冲突" in message
        assert notifications[-1][1]["severity"] == "error"
        assert isinstance(app.screen, SelfUpdateScreen)
        assert _confirm(app).disabled is True

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SelfUpdateScreen)


async def test_startup_notifies_when_newer(app, monkeypatch):
    monkeypatch.setattr(app, "release_checker", lambda **kwargs: _newer_check())
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, HomeScreen)
        assert await _wait_for(
            pilot, lambda: any("发现新版本" in message for message, _ in notifications)
        )

    startup = [entry for entry in notifications if "发现新版本" in entry[0]]
    assert startup, notifications
    message, kwargs = startup[-1]
    assert "1.4.0" in message
    assert "1.3.0" in message
    assert "Ctrl+U" in message
    assert kwargs["timeout"] == 15


async def test_startup_check_failure_is_silent(app, monkeypatch):
    calls: list[int] = []

    def boom(**kwargs):
        calls.append(1)
        raise SelfUpdateError("超时")

    monkeypatch.setattr(app, "release_checker", boom)
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        lv = app.screen.query_one("#groups", ListView)
        assert len(lv.children) >= 8
        lv.index = 0
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert lv.index == 1
        assert await _wait_for(pilot, lambda: bool(calls))
        await pilot.pause()
        await pilot.pause()

    assert _update_notifications(notifications) == []


async def test_startup_check_up_to_date_is_silent(app, monkeypatch):
    calls: list[int] = []

    def up_to_date(**kwargs):
        """An up-to-date install: the real checker returns None."""
        calls.append(1)

    monkeypatch.setattr(app, "release_checker", up_to_date)
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        assert await _wait_for(pilot, lambda: bool(calls))
        await pilot.pause()
        await pilot.pause()

    assert _update_notifications(notifications) == []


async def test_startup_check_runs_only_once_per_app(app, monkeypatch):
    """Leaving and re-entering home (resume + refresh) must not notify again."""
    calls: list[int] = []

    def newer(**kwargs):
        calls.append(1)
        return _newer_check()

    monkeypatch.setattr(app, "release_checker", newer)
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        assert await _wait_for(pilot, lambda: bool(_update_notifications(notifications)))
        assert len(_update_notifications(notifications)) == 1

        app.screen.query_one("#groups", ListView).index = 1
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, CharactersScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)

        await pilot.press("r")  # refresh_view must not re-run the startup check
        await pilot.pause()
        await pilot.pause()

        assert len(calls) == 1
        assert len(_update_notifications(notifications)) == 1


async def test_call_keeps_unexpected_callback_errors_visible(app, caplog):
    """A bug inside a UI callback must stay visible; a dead app must stay quiet."""

    def boom() -> None:
        raise AttributeError("release.latest is missing")

    async with app.run_test(size=(100, 30)) as pilot:
        home = app.screen
        assert isinstance(home, HomeScreen)
        await pilot.pause()

        with caplog.at_level(logging.DEBUG, logger="wwmm.screens.home"):
            await asyncio.to_thread(home._call, boom)  # must not escape the worker

        errors = [
            record
            for record in caplog.records
            if record.name == "wwmm.screens.home" and record.levelno >= logging.ERROR
        ]
        assert len(errors) == 1
        assert errors[0].getMessage() == "UI callback failed"
        assert errors[0].exc_info is not None

        caplog.clear()
        loop = app._loop
        app._loop = None  # exactly the precondition App.call_from_thread checks
        try:
            with caplog.at_level(logging.DEBUG, logger="wwmm.screens.home"):
                await asyncio.to_thread(home._call, boom)
        finally:
            app._loop = loop

        records = [record for record in caplog.records if record.name == "wwmm.screens.home"]
        assert records
        assert all(record.levelno == logging.DEBUG for record in records)
        assert "not running" in records[0].getMessage()


@pytest.mark.parametrize("fixture_name", ["app", "app_without_mods", "sparse_app"])
def test_conftest_default_checker_is_offline(request, monkeypatch, fixture_name):
    def no_network(*args, **kwargs):
        raise AssertionError("测试不应访问网络")

    monkeypatch.setattr("wwmm.self_update.urlopen", no_network)
    fixture_app = request.getfixturevalue(fixture_name)

    assert fixture_app.release_checker is not check_for_update
    assert fixture_app.release_checker() is None


async def test_check_newer_explains_archive_install(app, monkeypatch, tmp_path):
    """A Releases install has no .git, so the dialog must not promise a git pull."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ww-mod-manager"\nversion = "1.3.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("wwmm.screens.self_update.find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(app, "release_checker", lambda **kwargs: _newer_check())

    async with app.run_test(size=(100, 30)) as pilot:
        await _open(pilot)
        assert await _wait_for(pilot, lambda: "1.4.0" in _message(app))

        message = _message(app)
        assert "源码包" in message
        assert "git pull" not in message


async def test_updated_reports_the_backup_path(app, monkeypatch):
    monkeypatch.setattr(app, "release_checker", lambda **kwargs: _newer_check())
    monkeypatch.setattr(
        app,
        "self_updater",
        lambda root: SelfUpdateResult(
            new_version="1.4.0",
            reinstalled=True,
            mode="archive",
            backup="/tmp/WW-Mod-Manager.bak-v1.3.0-20261022-073000",
        ),
    )
    notifications = _capture_notifications(monkeypatch, app)

    async with app.run_test(size=(100, 30)) as pilot:
        await _open(pilot)
        assert await _wait_for(pilot, lambda: _confirm(app).disabled is False)
        await pilot.click("#self-update-confirm")
        assert await _wait_for(pilot, lambda: bool(notifications))

    message = notifications[-1][0]
    assert "备份" in message
    assert "/tmp/WW-Mod-Manager.bak-v1.3.0-20261022-073000" in message
