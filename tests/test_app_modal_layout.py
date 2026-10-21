"""Geometry contracts for the three modal dialogs.

A bare ``Vertical`` inside a ``ModalScreen`` defaults to ``1fr`` width and height,
so the dialog used to fill the whole terminal and its content stuck to the
top-left corner. These tests pin the centred geometry instead of the CSS text, so
any layout regression is caught by behaviour rather than by string matching.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.containers import Vertical
from textual.css.query import NoMatches

from wwmm.hotkeys import Hotkey, HotkeyKind
from wwmm.models import Mod
from wwmm.screens.hotkey_edit import HotkeyEditScreen
from wwmm.screens.self_update import SelfUpdateScreen
from wwmm.screens.update import UpdateScreen

WIDTH = 100
HEIGHT = 30

MOD = Mod(
    path=Path("/tmp/fixture-mod"),
    folder_name="Fixture Mod",
    enabled=True,
    ini_count=1,
)
HOTKEY = Hotkey(
    display_key="Ctrl+0",
    section="KeyHair",
    source="mod.ini",
    kind=HotkeyKind.SWITCH,
    raw="CTRL 0",
)


async def _settle(pilot, predicate, attempts=100):
    for _ in range(attempts):
        if predicate():
            return True
        await pilot.pause()
        await asyncio.sleep(0.01)
    return predicate()


async def _assert_centered(app, pilot, selector: str) -> None:
    def box():
        try:
            return app.screen.query_one(selector, Vertical)
        except NoMatches:
            return None

    def laid_out():
        widget = box()
        return widget is not None and widget.region.width > 0

    assert await _settle(pilot, laid_out)
    region = box().region
    assert region.width < WIDTH, f"{selector} still stretches the whole terminal"
    assert region.height < HEIGHT, f"{selector} still stretches the whole terminal"
    assert abs((region.x + region.width // 2) - WIDTH // 2) <= 1, f"{selector} is not centred"
    assert abs((region.y + region.height // 2) - HEIGHT // 2) <= 1, f"{selector} is not centred"


async def test_update_dialog_is_centered(app):
    async with app.run_test(size=(WIDTH, HEIGHT)) as pilot:
        await app.push_screen(UpdateScreen())
        await _assert_centered(app, pilot, "#update-box")


async def test_self_update_dialog_is_centered(app):
    async with app.run_test(size=(WIDTH, HEIGHT)) as pilot:
        await app.push_screen(SelfUpdateScreen())
        await _assert_centered(app, pilot, "#self-update-box")


async def test_hotkey_edit_dialog_is_centered(app):
    async with app.run_test(size=(WIDTH, HEIGHT)) as pilot:
        await app.push_screen(HotkeyEditScreen(MOD, HOTKEY))
        await _assert_centered(app, pilot, "#hotkey-edit-box")
