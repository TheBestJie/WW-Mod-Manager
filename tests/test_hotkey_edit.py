from pathlib import Path

import pytest

from wwmm.hotkey_edit import HotkeyEditError, apply_hotkey, validate_key_expr
from wwmm.hotkeys import parse_mod_hotkeys


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_validate_accepts_supported_syntax():
    assert validate_key_expr("ctrl alt f7") == "ctrl alt f7"
    assert validate_key_expr("Ctrl+Alt+K") == "Ctrl+Alt+K".replace("+", " ")
    assert validate_key_expr("VK_INSERT") == "VK_INSERT"
    assert validate_key_expr("0x70") == "0x70"
    assert validate_key_expr("XB_LEFT_TRIGGER") == "XB_LEFT_TRIGGER"
    assert validate_key_expr("no_modifiers /") == "no_modifiers /"


def test_validate_rejects_unsupported():
    for bad in ("", "   ", "ctrl 中文", "foo", "ctrl +"):
        with pytest.raises(HotkeyEditError):
            validate_key_expr(bad)
    with pytest.raises(HotkeyEditError, match="不支持的按键"):
        validate_key_expr("ctrl 中文")


def test_apply_targets_exact_occurrence(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyMulti]\nKey = X\nKey = Y\nBack = Q")
    apply_hotkey(mod, "mod.ini", "KeyMulti", "key", 1, "ctrl k")
    lines = (mod / "mod.ini").read_text(encoding="utf-8-sig").splitlines()
    assert lines == ["[KeyMulti]", "Key = X", "Key = ctrl k", "Back = Q"]


def test_apply_preserves_bom_comments_and_sibling_lines(tmp_path):
    mod = tmp_path / "Mod"
    mod.mkdir()
    ini = mod / "mod.ini"
    original = (
        "\ufeff[KeyHair]\n"
        "; 注释\n"
        "key = ctrl 1\n"
        "Back = VK_F8\n"
        + "；GBK 未知字节行\n".encode("gbk").decode("utf-8", errors="surrogateescape")
        + "\n[TextureOverrideFoo]\n"
        "hash = abc\n"
    ).encode("utf-8", errors="surrogateescape")
    ini.write_bytes(original)

    apply_hotkey(mod, "mod.ini", "KeyHair", "key", 0, "ctrl 2")

    expected = original.replace(b"key = ctrl 1\n", b"key = ctrl 2\n")
    assert ini.read_bytes() == expected
    assert ini.read_bytes().startswith(b"\xef\xbb\xbf")


def test_apply_section_field_case_insensitive(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KEYHAIR]\nKey = X\ntype = cycle")
    apply_hotkey(mod, "mod.ini", "keyhair", "key", 0, "ctrl 2")
    lines = (mod / "mod.ini").read_text(encoding="utf-8-sig").splitlines()
    assert lines == ["[KEYHAIR]", "Key = ctrl 2", "type = cycle"]


def test_apply_missing_section_or_occurrence_raises(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyHair]\nkey = X\ntype = cycle")
    original = (mod / "mod.ini").read_bytes()
    with pytest.raises(HotkeyEditError):
        apply_hotkey(mod, "mod.ini", "KeyNope", "key", 0, "ctrl k")
    with pytest.raises(HotkeyEditError):
        apply_hotkey(mod, "mod.ini", "KeyHair", "key", 5, "ctrl k")
    assert (mod / "mod.ini").read_bytes() == original


def test_apply_targets_correct_instance_for_duplicate_sections(tmp_path):
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyHair]\nKey = X\n\n[KEYHAIR]\nKey = Y")
    hotkeys = parse_mod_hotkeys(mod)
    assert [(h.section, h.raw, h.field, h.occurrence) for h in hotkeys] == [
        ("KeyHair", "X", "key", 0),
        ("KEYHAIR", "Y", "key", 1),
    ]

    apply_hotkey(
        mod, "mod.ini", hotkeys[1].section, hotkeys[1].field, hotkeys[1].occurrence, "ctrl k"
    )
    lines = (mod / "mod.ini").read_text(encoding="utf-8-sig").splitlines()
    assert lines == ["[KeyHair]", "Key = X", "", "[KEYHAIR]", "Key = ctrl k"]

    apply_hotkey(
        mod, "mod.ini", hotkeys[0].section, hotkeys[0].field, hotkeys[0].occurrence, "alt j"
    )
    lines = (mod / "mod.ini").read_text(encoding="utf-8-sig").splitlines()
    assert lines == ["[KeyHair]", "Key = alt j", "", "[KEYHAIR]", "Key = ctrl k"]


def test_apply_preserves_inline_comment_and_trailing_space_on_target_line(tmp_path):
    mod = tmp_path / "Mod"
    _write(
        mod / "mod.ini",
        "[KeyHair]\nkey = ctrl 1 ; 说明\nBack = Q # 备注\n\n[KeyTail]\nKey = X   \nBack = W",
    )
    apply_hotkey(mod, "mod.ini", "KeyHair", "key", 0, "ctrl 2")
    apply_hotkey(mod, "mod.ini", "KeyHair", "back", 0, "alt b")
    apply_hotkey(mod, "mod.ini", "KeyTail", "key", 0, "alt n")
    lines = (mod / "mod.ini").read_text(encoding="utf-8-sig").splitlines()
    assert lines == [
        "[KeyHair]",
        "key = ctrl 2 ; 说明",
        "Back = alt b # 备注",
        "",
        "[KeyTail]",
        "Key = alt n   ",
        "Back = W",
    ]


def test_validate_rejects_bare_hex_and_signed_numbers():
    for bad in ("abc", "face", "-5", "0xzz"):
        with pytest.raises(HotkeyEditError):
            validate_key_expr(bad)
    assert validate_key_expr("0") == "0"
    assert validate_key_expr("5") == "5"
    assert validate_key_expr("0X7B") == "0X7B"


def test_apply_keeps_bomless_file_bomless(tmp_path):
    mod = tmp_path / "Mod"
    mod.mkdir()
    ini = mod / "mod.ini"
    original = b"[KeyHair]\n; comment\nkey = ctrl 1\nBack = Q\n"
    ini.write_bytes(original)
    apply_hotkey(mod, "mod.ini", "KeyHair", "key", 0, "ctrl 2")
    assert ini.read_bytes() == original.replace(b"key = ctrl 1\n", b"key = ctrl 2\n")
