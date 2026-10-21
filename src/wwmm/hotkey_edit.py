"""Validate 3Dmigoto key expressions and write them back into mod ini files."""

from __future__ import annotations

import os
import re
from pathlib import Path

from wwmm.errors import HotkeyEditError
from wwmm.hotkeys import _FIELD_RE, _SECTION_RE, _XBOX_RE

_TOKEN_SPLIT_RE = re.compile(r"[\s+]+")

# Canonical ``vkeys.h`` constants, i.e. the names 3Dmigoto actually accepts.
# Deliberately separate from ``wwmm.hotkeys._VK_LABELS``: that one is a display
# table and also carries friendly spellings (BACKSPACE, CAPS, SEMICOLON, …) that
# the game silently ignores, so using it as a syntax whitelist wrote broken
# bindings into the ini while the UI reported success.
_VK_NAMES: frozenset[str] = frozenset(
    {
        "LBUTTON",
        "RBUTTON",
        "CANCEL",
        "MBUTTON",
        "XBUTTON1",
        "XBUTTON2",
        "BACK",
        "TAB",
        "CLEAR",
        "RETURN",
        "SHIFT",
        "CONTROL",
        "MENU",
        "PAUSE",
        "CAPITAL",
        "KANA",
        "HANGUL",
        "JUNJA",
        "FINAL",
        "HANJA",
        "KANJI",
        "ESCAPE",
        "CONVERT",
        "NONCONVERT",
        "ACCEPT",
        "MODECHANGE",
        "SPACE",
        "PRIOR",
        "NEXT",
        "END",
        "HOME",
        "LEFT",
        "UP",
        "RIGHT",
        "DOWN",
        "SELECT",
        "PRINT",
        "EXECUTE",
        "SNAPSHOT",
        "INSERT",
        "DELETE",
        "HELP",
        "LWIN",
        "RWIN",
        "APPS",
        "SLEEP",
        "MULTIPLY",
        "ADD",
        "SEPARATOR",
        "SUBTRACT",
        "DECIMAL",
        "DIVIDE",
        "NUMLOCK",
        "SCROLL",
        "LSHIFT",
        "RSHIFT",
        "LCONTROL",
        "RCONTROL",
        "LMENU",
        "RMENU",
        "OEM_1",
        "OEM_PLUS",
        "OEM_COMMA",
        "OEM_MINUS",
        "OEM_PERIOD",
        "OEM_2",
        "OEM_3",
        "OEM_4",
        "OEM_5",
        "OEM_6",
        "OEM_7",
        "OEM_8",
        "OEM_102",
        "OEM_CLEAR",
        "PROCESSKEY",
        "ATTN",
        "CRSEL",
        "EXSEL",
        "EREOF",
        "PLAY",
        "ZOOM",
        "NONAME",
        "PA1",
    }
    | {f"F{index}" for index in range(1, 25)}
    | {f"NUMPAD{index}" for index in range(10)}
)

# Friendly spellings worth accepting: anything a user may plausibly type that
# maps onto exactly one canonical name above.
_VK_ALIASES: dict[str, str] = {
    "BACKSPACE": "BACK",
    "BACK_SPACE": "BACK",
    "ESC": "ESCAPE",
    "ENTER": "RETURN",
    "PGUP": "PRIOR",
    "PAGEUP": "PRIOR",
    "PAGE_UP": "PRIOR",
    "PGDN": "NEXT",
    "PAGEDOWN": "NEXT",
    "PAGE_DOWN": "NEXT",
    "DEL": "DELETE",
    "INS": "INSERT",
    "CAPS": "CAPITAL",
    "CAPSLOCK": "CAPITAL",
    "CAPS_LOCK": "CAPITAL",
    "SEMICOLON": "OEM_1",
    "SEMI_COLON": "OEM_1",
    "PLUS": "OEM_PLUS",
    "EQUALS": "OEM_PLUS",
    "COMMA": "OEM_COMMA",
    "MINUS": "OEM_MINUS",
    "UNDERSCORE": "OEM_MINUS",
    "PERIOD": "OEM_PERIOD",
    "SLASH": "OEM_2",
    "FORWARD_SLASH": "OEM_2",
    "QUESTION": "OEM_2",
    "QUESTION_MARK": "OEM_2",
    "TILDE": "OEM_3",
    "GRAVE": "OEM_3",
    "BACKSLASH": "OEM_5",
    "BACK_SLASH": "OEM_5",
    "PIPE": "OEM_5",
    "VERTICAL_BAR": "OEM_5",
    "QUOTE": "OEM_7",
    "DOUBLE_QUOTE": "OEM_7",
    "PRSCR": "SNAPSHOT",
    "PRINTSCREEN": "SNAPSHOT",
    "PRINT_SCREEN": "SNAPSHOT",
    "HANGUEL": "HANGUL",
    "CTRL": "CONTROL",
    "ALT": "MENU",
    "WIN": "LWIN",
    "LEFT_WIN": "LWIN",
    "LEFT_WINDOWS": "LWIN",
    "RIGHT_WIN": "RWIN",
    "RIGHT_WINDOWS": "RWIN",
    "LCTRL": "LCONTROL",
    "LEFT_CTRL": "LCONTROL",
    "LEFT_CONTROL": "LCONTROL",
    "RCTRL": "RCONTROL",
    "RIGHT_CTRL": "RCONTROL",
    "RIGHT_CONTROL": "RCONTROL",
    "LALT": "LMENU",
    "LEFT_ALT": "LMENU",
    "LEFT_MENU": "LMENU",
    "RALT": "RMENU",
    "RIGHT_ALT": "RMENU",
    "RIGHT_MENU": "RMENU",
    "LEFT_SHIFT": "LSHIFT",
    "RIGHT_SHIFT": "RSHIFT",
}

# 3Dmigoto spells the four modifier buttons as words instead of VK_ names.
_MODIFIER_WORDS: dict[str, str] = {
    "CONTROL": "ctrl",
    "MENU": "alt",
    "SHIFT": "shift",
    "LWIN": "win",
    "RWIN": "win",
}

# Canonical key identities behind each modifier word, used to detect an
# expression whose every real key is also excluded.
_MODIFIER_KEYS: dict[str, frozenset[str]] = {
    "ctrl": frozenset({"CONTROL"}),
    "alt": frozenset({"MENU"}),
    "shift": frozenset({"SHIFT"}),
    "win": frozenset({"LWIN", "RWIN"}),
}
_ALL_MODIFIER_KEYS: frozenset[str] = frozenset().union(*_MODIFIER_KEYS.values())

# 3Dmigoto understands exactly these Xbox button names (plus a 1-4 pad index).
_XBOX_BUTTONS: frozenset[str] = frozenset(
    {
        "LEFT_TRIGGER",
        "RIGHT_TRIGGER",
        "LEFT_SHOULDER",
        "RIGHT_SHOULDER",
        "LEFT_THUMB",
        "RIGHT_THUMB",
        "DPAD_UP",
        "DPAD_DOWN",
        "DPAD_LEFT",
        "DPAD_RIGHT",
        "A",
        "B",
        "X",
        "Y",
        "START",
        "BACK",
        "GUIDE",
    }
)

_USAGE_HINT = (
    "不支持的按键：{}；可用写法：字母 A–Z / 数字 0–9、VK 名称（如 VK_BACK、VK_OEM_1）、"
    "0x 十六进制码、XB_ 手柄键、修饰键 ctrl/alt/shift/win、no_ 排除前缀"
)
_PUNCTUATION_HINT = (
    "不支持的按键：{}；单字符只支持字母 A–Z 和数字 0–9，"
    "符号请写 VK 名称（如 ; → VK_OEM_1、/ → VK_OEM_2、= → VK_OEM_PLUS、' → VK_OEM_7）"
)
_XBOX_HINT = "不支持的按键：{}；可用写法：{}（可带手柄编号 1–4，如 XB2_LEFT_SHOULDER）"
_MODIFIER_ONLY_HINT = (
    "至少需要一个按键，不能只写修饰键；ctrl/alt/shift 键本身请写 VK_LCONTROL 这类分侧名，"
    "Windows 键请写 0x5B / 0x5C"
)
_XBOX_BUTTON_LIST = "、".join(f"XB_{name}" for name in sorted(_XBOX_BUTTONS))


def _canonical_name(name: str) -> str | None:
    """Resolve one (already upper-cased) name to its canonical vkeys.h constant."""
    if name in _VK_NAMES:
        return name
    return _VK_ALIASES.get(name)


def _normalize_token(token: str) -> str:
    """Return the 3Dmigoto spelling of one token or raise :class:`HotkeyEditError`."""
    if len(token) == 1:
        if token.isascii() and token.isalpha():
            return token.upper()
        if token.isascii() and token.isdigit():
            return token
        raise HotkeyEditError(_PUNCTUATION_HINT.format(token))

    xbox_match = _XBOX_RE.match(token)
    if xbox_match is not None:
        controller, button = xbox_match.groups()
        if button.upper() not in _XBOX_BUTTONS:
            raise HotkeyEditError(_XBOX_HINT.format(token, _XBOX_BUTTON_LIST))
        return f"XB{controller or ''}_{button.upper()}"

    upper = token.upper()
    if upper.startswith("NO_"):
        rest = upper[3:]
        if rest == "MODIFIERS":
            return "no_modifiers"
        name = _canonical_name(rest.removeprefix("VK_"))
        if name is None:
            raise HotkeyEditError(_USAGE_HINT.format(token))
        word = _MODIFIER_WORDS.get(name)
        return f"no_{word}" if word is not None else f"no_vk_{name.lower()}"

    if upper.startswith("0X"):
        try:
            int(token, 16)
        except ValueError:
            raise HotkeyEditError(_USAGE_HINT.format(token)) from None
        return token

    name = _canonical_name(upper.removeprefix("VK_"))
    if name is None:
        raise HotkeyEditError(_USAGE_HINT.format(token))
    return _MODIFIER_WORDS.get(name, f"VK_{name}")


def _identities(normalized: str) -> frozenset[str]:
    """Canonical keys one normalised token binds (or excludes, for ``no_*``)."""
    if normalized.startswith("no_vk_"):
        return frozenset({normalized[len("no_vk_") :].upper()})
    if normalized.startswith("no_"):
        word = normalized[len("no_") :]
        return _ALL_MODIFIER_KEYS if word == "modifiers" else _MODIFIER_KEYS[word]
    if normalized.startswith("VK_"):
        return frozenset({normalized[len("VK_") :]})
    modifier = _MODIFIER_KEYS.get(normalized)
    if modifier is not None:
        return modifier
    return frozenset({normalized.upper()})


def validate_key_expr(text: str) -> str:
    """Return *text* normalised to 3Dmigoto syntax or raise :class:`HotkeyEditError`."""
    tokens = _TOKEN_SPLIT_RE.split(text.strip())
    if any(token == "" for token in tokens):
        raise HotkeyEditError("按键组合不能为空")
    # Repeated spellings of one key (``f7 VK_F7``, ``no_ctrl no_control``) collapse
    # onto their canonical identity, keeping the first spelling seen.
    unique: list[str] = []
    seen: set[tuple[bool, frozenset[str]]] = set()
    for token in (_normalize_token(token) for token in tokens):
        identity = (token.startswith("no_"), _identities(token))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(token)
    real_tokens = [token for token in unique if not token.startswith("no_")]
    # A ``no_*`` token only excludes a key; if every real key is excluded (or
    # none is left) the expression parses to an empty binding and the ini would
    # end up with a line that the hotkey list silently drops.
    excluded = frozenset().union(
        *(_identities(token) for token in unique if token.startswith("no_"))
    )
    real = frozenset().union(*(_identities(token) for token in real_tokens))
    if not real - excluded:
        raise HotkeyEditError("至少需要一个按键，不能只写排除项")
    # A bare modifier never fires in 3Dmigoto either: ``key = ctrl`` reports
    # success in the UI and does nothing in game.
    if all(token in _MODIFIER_KEYS for token in real_tokens):
        raise HotkeyEditError(_MODIFIER_ONLY_HINT)
    return " ".join(unique)


def apply_hotkey(
    mod_path: Path,
    source: str,
    section: str,
    field: str,
    occurrence: int,
    new_raw: str,
) -> None:
    """Replace one ``key``/``back`` line in *mod_path*/*source* with *new_raw*.

    Only the targeted line changes; BOM, comments, blank lines and every other
    section stay byte-identical. The write is atomic (temp file + ``os.replace``)
    and the original file is left untouched when the target is missing.
    """
    ini = Path(mod_path) / source
    data = ini.read_bytes()
    had_bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig", errors="surrogateescape")

    want_section = section.casefold()
    want_field = field.casefold()
    current: str | None = None
    counter = 0
    out: list[str] = []
    replaced = False

    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        section_match = _SECTION_RE.match(body)
        if section_match is not None:
            current = section_match.group(1).strip()
            out.append(line)
            continue
        field_match = _FIELD_RE.match(body)
        if (
            field_match is not None
            and current is not None
            and current.casefold() == want_section
            and field_match.group(1).casefold() == want_field
        ):
            # Counted continuously across duplicated section instances on
            # purpose: _parse_ini numbers occurrences the same way, so each
            # parsed Hotkey round-trips back to its exact line.
            counter += 1
            if counter == occurrence + 1:
                name = field_match.group(1)
                new_body = re.sub(
                    rf"^(\s*{re.escape(name)}\s*=\s*)(.*?)(\s+[;#].*|\s*)$",
                    lambda match: match.group(1) + new_raw + (match.group(3) or ""),
                    body,
                    count=1,
                    flags=re.IGNORECASE,
                )
                out.append(new_body + ending)
                replaced = True
                continue
        out.append(line)

    if not replaced:
        raise HotkeyEditError(
            f"未找到快捷键：[{section}] {field} 第 {occurrence + 1} 处（{source}）"
        )

    encoding = "utf-8-sig" if had_bom else "utf-8"
    payload = "".join(out).encode(encoding, errors="surrogateescape")
    tmp = ini.with_name(ini.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, ini)
