from pathlib import Path

import pytest

from wwmm.hotkeys import HotkeyKind, format_key, parse_mod_hotkeys


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_parses_and_groups_hotkeys(tmp_path):
    mod = tmp_path / "Mod"
    _write(
        mod / "mod.ini",
        """
        [KeyHair]
        key = CTRL 0
        type = cycle

        [KeyMenu]
        key = VK_CONTROL
        type = hold

        [KeyReset]
        key = no_modifiers /
        run = CommandListReset

        [NotAKey]
        key = VK_F2
        """,
    )
    hotkeys = parse_mod_hotkeys(mod)
    assert [(h.section, h.display_key, h.kind) for h in hotkeys] == [
        ("KeyHair", "Ctrl+0", HotkeyKind.SWITCH),
        ("KeyMenu", "Ctrl", HotkeyKind.HOLD),
        ("KeyReset", "/", HotkeyKind.OTHER),
    ]


def test_parses_multiple_keys_and_back(tmp_path):
    mod = tmp_path / "Mod"
    _write(
        mod / "mod.ini",
        """
        [KeyMulti]
        Key = X
        Key = XB_X
        type = toggle

        [KeyCycle]
        Key = E
        Back = Q
        type = cycle
        """,
    )
    hotkeys = parse_mod_hotkeys(mod)
    assert [(h.section, h.display_key, h.kind, h.back) for h in hotkeys] == [
        ("KeyMulti", "X", HotkeyKind.SWITCH, False),
        ("KeyMulti", "手柄 X", HotkeyKind.SWITCH, False),
        ("KeyCycle", "E", HotkeyKind.SWITCH, False),
        ("KeyCycle", "Q", HotkeyKind.SWITCH, True),
    ]
    assert [(h.raw, h.field, h.occurrence) for h in hotkeys] == [
        ("X", "key", 0),
        ("XB_X", "key", 1),
        ("E", "key", 0),
        ("Q", "back", 0),
    ]


def test_skips_hidden_and_disabled_ini(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyA]\nkey = 1\ntype = cycle")
    _write(mod / "DISABLED_old" / "mod.ini", "[KeyB]\nkey = 2\ntype = cycle")
    _write(mod / "DISABLED_extra.ini", "[KeyC]\nkey = 3\ntype = cycle")
    _write(mod / ".hidden" / "mod.ini", "[KeyD]\nkey = 4\ntype = cycle")
    assert [h.section for h in parse_mod_hotkeys(mod)] == ["KeyA"]


def test_section_and_field_names_are_case_insensitive(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[keylower]\nKEY = VK_F1\nTYPE = CYCLE\n\n[KeyEmpty]\ntype = cycle")
    hotkeys = parse_mod_hotkeys(mod)
    assert len(hotkeys) == 1
    assert hotkeys[0].section == "keylower"
    assert hotkeys[0].kind is HotkeyKind.SWITCH


def test_semicolon_key_is_not_a_comment(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeySemi]\nkey = ;\ntype = cycle")
    assert parse_mod_hotkeys(mod)[0].display_key == ";"


def test_reads_nested_ini_and_keeps_relative_source(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyA]\nkey = 1\ntype = cycle")
    _write(mod / "Sub Folder" / "[X]" / "extra.ini", "[KeyB]\nkey = 2\ntype = hold")
    hotkeys = parse_mod_hotkeys(mod)
    assert [(h.section, h.source) for h in hotkeys] == [
        ("KeyA", "mod.ini"),
        ("KeyB", "Sub Folder/[X]/extra.ini"),
    ]


def test_utf8_bom_is_tolerated(tmp_path):
    mod = tmp_path / "Mod"
    mod.mkdir()
    (mod / "mod.ini").write_text("\ufeff[KeyA]\nkey = 1\ntype = cycle\n", encoding="utf-8")
    assert [h.section for h in parse_mod_hotkeys(mod)] == ["KeyA"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CTRL 0", "Ctrl+0"),
        ("no_ctrl no_shift alt VK_RBUTTON", "Alt+右键"),
        ("VK_NUMPAD1", "小键盘 1"),
        ("NUMPAD1", "小键盘 1"),
        ("ALT UP", "Alt+↑"),
        ("no_modifiers up", "↑"),
        ("shift /", "Shift+/"),
        ("VK_OEM_7", "'"),
        ("SEMICOLON", ";"),
        ("k", "K"),
        ("VK_F10", "F10"),
        ("CTRL VK_SPACE", "Ctrl+Space"),
        ("RBUTTON", "右键"),
        ("0x70", "F1"),
        ("0x31", "1"),
        ("XB_X", "手柄 X"),
        ("XB2_LEFT_TRIGGER", "手柄2 LT"),
        ("ALT", "Alt"),
        ("VK_DECIMAL VK_NUMPAD0", "小键盘 .+小键盘 0"),
        ("CTRL SHIFT Q", "Ctrl+Shift+Q"),
        ("ctrl no_shift no_alt VK_LEFT", "Ctrl+←"),
        ("NO_MODIFIERS F6", "F6"),
        ("VK_SOME_UNKNOWN", "SOME_UNKNOWN"),
    ],
)
def test_format_key(raw, expected):
    assert format_key(raw) == expected


def test_empty_or_missing_mod_returns_empty(tmp_path):
    empty = tmp_path / "Empty"
    empty.mkdir()
    assert parse_mod_hotkeys(empty) == []
    assert parse_mod_hotkeys(tmp_path / "missing") == []
