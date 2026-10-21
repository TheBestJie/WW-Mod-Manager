from pathlib import Path

import pytest

from wwmm.hotkey_edit import HotkeyEditError, apply_hotkey, validate_key_expr
from wwmm.hotkeys import parse_mod_hotkeys


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_validate_accepts_supported_syntax():
    assert validate_key_expr("ctrl alt f7") == "ctrl alt VK_F7"
    assert validate_key_expr("Ctrl+Alt+K") == "ctrl alt K"
    assert validate_key_expr("VK_INSERT") == "VK_INSERT"
    assert validate_key_expr("0x70") == "0x70"
    assert validate_key_expr("XB_LEFT_TRIGGER") == "XB_LEFT_TRIGGER"
    assert validate_key_expr("no_modifiers VK_OEM_2") == "no_modifiers VK_OEM_2"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Display labels from hotkeys._VK_LABELS are not 3Dmigoto syntax; they
        # must be normalised to the vkeys.h constant instead of rejected or
        # written through verbatim.
        ("ctrl Backspace", "ctrl VK_BACK"),
        ("BACK_SPACE", "VK_BACK"),
        ("esc", "VK_ESCAPE"),
        ("enter", "VK_RETURN"),
        ("pgup pgdn del ins", "VK_PRIOR VK_NEXT VK_DELETE VK_INSERT"),
        ("caps", "VK_CAPITAL"),
        ("ctrl semicolon", "ctrl VK_OEM_1"),
        ("ctrl plus", "ctrl VK_OEM_PLUS"),
        ("ctrl equals", "ctrl VK_OEM_PLUS"),
        ("printscreen", "VK_SNAPSHOT"),
        ("vk_f7", "VK_F7"),
        ("f7", "VK_F7"),
        ("backspace", "VK_BACK"),
        ("a", "A"),
        ("0", "0"),
        ("xb2_left_shoulder", "XB2_LEFT_SHOULDER"),
        ("XB_A", "XB_A"),
        ("Ctrl+Shift+Q", "ctrl shift Q"),
        # 未经游戏侧验证：若不成立需改断言（分侧修饰键是否可单独成键）。
        ("VK_LSHIFT", "VK_LSHIFT"),
        # 未经游戏侧验证：若不成立需改断言（3Dmigoto 是否接受大写 0X 前缀）。
        ("0X7B", "0X7B"),
        ("f7 no_backspace", "VK_F7 no_vk_back"),
        ("f7 no_control", "VK_F7 no_ctrl"),
        ("f7 no_menu", "VK_F7 no_alt"),
        ("f7 no_win", "VK_F7 no_win"),
        ("f7 NO_MODIFIERS", "VK_F7 no_modifiers"),
    ],
)
def test_validate_normalises_to_3dmigoto_key_names(raw, expected):
    assert validate_key_expr(raw) == expected


@pytest.mark.parametrize(
    ("bad", "hint"),
    [
        ("XB_garbage", "XB_LEFT_TRIGGER"),
        ("ctrl XB_garbage", "XB_RIGHT_THUMB"),
        (";", "VK_OEM_1"),
        ("ctrl ;", "VK_OEM_1"),
        ("ctrl /", "VK_OEM_2"),
        ("ctrl =", "VK_OEM_PLUS"),
        ("INLINE", "不支持的按键"),
        ("NOTE", "不支持的按键"),
        ("VK_SOME_UNKNOWN", "不支持的按键"),
        ("ctrl 中文", "不支持的按键"),
    ],
)
def test_validate_rejects_non_3dmigoto_tokens(bad, hint):
    with pytest.raises(HotkeyEditError) as excinfo:
        validate_key_expr(bad)
    assert hint in str(excinfo.value)


def test_validation_does_not_use_the_display_label_table():
    import wwmm.hotkey_edit as module

    assert not hasattr(module, "_VK_LABELS")
    assert "BACKSPACE" not in module._VK_NAMES
    assert "BACK" in module._VK_NAMES
    assert all(len(name) > 1 for name in module._VK_NAMES)


def test_validate_rejects_expressions_without_real_keys():
    for bad in ("no_ctrl", "no_modifiers", "ctrl no_ctrl", "win no_win", "f7 no_vk_f7"):
        with pytest.raises(HotkeyEditError, match="排除项"):
            validate_key_expr(bad)
    assert validate_key_expr("ctrl no_modifiers VK_OEM_2") == "ctrl no_modifiers VK_OEM_2"
    assert validate_key_expr("ctrl alt VK_F7") == "ctrl alt VK_F7"
    assert validate_key_expr("0x70") == "0x70"
    assert validate_key_expr("XB_X") == "XB_X"


@pytest.mark.parametrize(
    "bad",
    ["ctrl", "alt", "shift", "win", "VK_LWIN", "VK_RWIN", "shift alt", "ctrl win", "Ctrl+Alt"],
)
def test_validate_rejects_modifier_only_expressions(bad):
    """``key = ctrl`` never fires in game, so it must not report success."""
    with pytest.raises(HotkeyEditError, match="修饰键") as excinfo:
        validate_key_expr(bad)
    assert "0x5B" in str(excinfo.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ctrl alt shift win K", "ctrl alt shift win K"),
        ("no_alt F1", "no_alt VK_F1"),
        ("f7 no_ctrl", "VK_F7 no_ctrl"),
        ("ctrl no_modifiers VK_OEM_2", "ctrl no_modifiers VK_OEM_2"),
        ("no_modifiers XB_A", "no_modifiers XB_A"),
        ("ctrl 0x70", "ctrl 0x70"),
    ],
)
def test_validate_accepts_modifiers_with_a_real_key(raw, expected):
    assert validate_key_expr(raw) == expected


def test_validate_accepts_hex_for_the_windows_keys(tmp_path):
    """The modifier-only error points at 0x5B/0x5C, so those must really work."""
    assert validate_key_expr("0x5B") == "0x5B"
    assert validate_key_expr("0x5C") == "0x5C"
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyHair]\nkey = CTRL 0\ntype = cycle")
    apply_hotkey(mod, "mod.ini", "KeyHair", "key", 0, validate_key_expr("0x5B"))
    assert (mod / "mod.ini").read_text(encoding="utf-8").splitlines()[1] == "key = 0x5B"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("f7 f7", "VK_F7"),
        ("f7 VK_F7", "VK_F7"),
        ("F7 vk_f7 VK_F7", "VK_F7"),
        ("ctrl ctrl K", "ctrl K"),
        ("ctrl K k", "ctrl K"),
        ("XB_A XB_A", "XB_A"),
        ("0x70 0X70", "0x70"),
        ("f7 no_ctrl no_control", "VK_F7 no_ctrl"),
        ("f7 no_alt no_menu", "VK_F7 no_alt"),
    ],
)
def test_validate_dedupes_repeated_tokens(raw, expected):
    assert validate_key_expr(raw) == expected


def test_every_alias_normalises_to_a_canonical_name():
    """Behavioural anti-regression for the display-label bug.

    Re-coupling validation to a label table would let e.g. ``BACKSPACE`` through
    verbatim; this iterates every alias and demands a real canonical name.
    """
    import wwmm.hotkey_edit as module

    allowed = module._VK_NAMES | {"ctrl", "alt", "shift", "win"}
    for alias in module._VK_ALIASES:
        # Paired with a real key so modifier aliases (CTRL/ALT/WIN) are not
        # rejected as modifier-only expressions.
        tokens = validate_key_expr(f"{alias} K").split(" ")
        assert tokens[1] == "K"
        real = tokens[0]
        assert real != alias
        assert real in allowed or real.removeprefix("VK_") in allowed
        excluded = validate_key_expr(f"f7 no_{alias}").split(" ")[1]
        assert excluded != f"no_{alias}"
        word = excluded.removeprefix("no_")
        assert word in {"ctrl", "alt", "shift", "win"} or (
            word.removeprefix("vk_").upper() in module._VK_NAMES
        )


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


def test_edit_round_trip_drops_inline_comment_from_the_expression(tmp_path):
    """A line comment must not leak into the prefilled expression or its edit."""
    mod = tmp_path / "Mod"
    _write(mod / "mod.ini", "[KeyHair]\nkey = CTRL 0 ; 说明\ntype = cycle")

    hotkey = parse_mod_hotkeys(mod)[0]
    assert hotkey.raw == "CTRL 0"
    assert hotkey.display_key == "Ctrl+0"

    normalized = validate_key_expr(hotkey.raw)
    assert normalized == "ctrl 0"
    apply_hotkey(mod, "mod.ini", hotkey.section, hotkey.field, hotkey.occurrence, normalized)
    assert (mod / "mod.ini").read_text(encoding="utf-8").splitlines() == [
        "[KeyHair]",
        "key = ctrl 0 ; 说明",
        "type = cycle",
    ]


def test_apply_keeps_bomless_file_bomless(tmp_path):
    mod = tmp_path / "Mod"
    mod.mkdir()
    ini = mod / "mod.ini"
    original = b"[KeyHair]\n; comment\nkey = ctrl 1\nBack = Q\n"
    ini.write_bytes(original)
    apply_hotkey(mod, "mod.ini", "KeyHair", "key", 0, "ctrl 2")
    assert ini.read_bytes() == original.replace(b"key = ctrl 1\n", b"key = ctrl 2\n")
