"""Tests for the Ctrl+U self update screen.

Every check goes through the fake ``release_checker`` injected by the fixtures, so
nothing here touches the network, git or uv.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.containers import Vertical
from textual.widgets import Button, Static

from wwmm.errors import SelfUpdateError
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


@pytest.mark.parametrize("fixture_name", ["app", "app_without_mods", "sparse_app"])
def test_conftest_default_checker_is_offline(request, monkeypatch, fixture_name):
    def no_network(*args, **kwargs):
        raise AssertionError("测试不应访问网络")

    monkeypatch.setattr("wwmm.self_update.urlopen", no_network)
    fixture_app = request.getfixturevalue(fixture_name)

    assert fixture_app.release_checker is not check_for_update
    assert fixture_app.release_checker() is None
