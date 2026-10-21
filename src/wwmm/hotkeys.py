"""Parse 3Dmigoto/WWMI ``[Key...]`` hotkeys from a mod's ini files."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)

_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_FIELD_RE = re.compile(r"^\s*(key|back|type)\s*=\s*(.*?)\s*$", re.IGNORECASE)
_XBOX_RE = re.compile(r"^XB([1-4])?_(.+)$", re.IGNORECASE)


class HotkeyKind(str, Enum):
    SWITCH = "切换"
    HOLD = "长按"
    OTHER = "其他"


@dataclass(frozen=True)
class Hotkey:
    display_key: str
    section: str
    source: str
    kind: HotkeyKind
    back: bool = False
    raw: str = ""
    field: str = "key"
    occurrence: int = 0


# Readable labels for 3Dmigoto's single-token virtual key names (vkeys.h).
# Names are matched case-insensitively, with or without a VK_ prefix.
_VK_LABELS: dict[str, str] = {
    "LBUTTON": "左键",
    "RBUTTON": "右键",
    "CANCEL": "Cancel",
    "MBUTTON": "中键",
    "XBUTTON1": "侧键1",
    "XBUTTON2": "侧键2",
    "BACK": "Backspace",
    "BACKSPACE": "Backspace",
    "BACK_SPACE": "Backspace",
    "TAB": "Tab",
    "CLEAR": "Clear",
    "RETURN": "Enter",
    "ENTER": "Enter",
    "SHIFT": "Shift",
    "CONTROL": "Ctrl",
    "CTRL": "Ctrl",
    "MENU": "Alt",
    "ALT": "Alt",
    "PAUSE": "Pause",
    "CAPITAL": "CapsLock",
    "CAPS": "CapsLock",
    "CAPSLOCK": "CapsLock",
    "CAPS_LOCK": "CapsLock",
    "KANA": "Kana",
    "HANGUEL": "Hangul",
    "HANGUL": "Hangul",
    "JUNJA": "Junja",
    "FINAL": "Final",
    "HANJA": "Hanja",
    "KANJI": "Kanji",
    "ESCAPE": "Esc",
    "CONVERT": "Convert",
    "NONCONVERT": "NonConvert",
    "ACCEPT": "Accept",
    "MODECHANGE": "ModeChange",
    "SPACE": "Space",
    "PRIOR": "PgUp",
    "PGUP": "PgUp",
    "PAGEUP": "PgUp",
    "PAGE_UP": "PgUp",
    "NEXT": "PgDn",
    "PGDN": "PgDn",
    "PAGEDOWN": "PgDn",
    "PAGE_DOWN": "PgDn",
    "END": "End",
    "HOME": "Home",
    "LEFT": "←",
    "UP": "↑",
    "RIGHT": "→",
    "DOWN": "↓",
    "SELECT": "Select",
    "PRINT": "Print",
    "EXECUTE": "Execute",
    "SNAPSHOT": "PrintScreen",
    "PRSCR": "PrintScreen",
    "PRINTSCREEN": "PrintScreen",
    "PRINT_SCREEN": "PrintScreen",
    "INSERT": "Insert",
    "DELETE": "Delete",
    "DEL": "Delete",
    "HELP": "Help",
    "WIN": "Win",
    "LWIN": "Win",
    "LEFT_WIN": "Win",
    "LEFT_WINDOWS": "Win",
    "RWIN": "Win",
    "RIGHT_WIN": "Win",
    "RIGHT_WINDOWS": "Win",
    "APPS": "Menu",
    "SLEEP": "Sleep",
    "NUMLOCK": "NumLock",
    "SCROLL": "ScrollLock",
    "LSHIFT": "Shift",
    "LEFT_SHIFT": "Shift",
    "RSHIFT": "Shift",
    "RIGHT_SHIFT": "Shift",
    "LCONTROL": "Ctrl",
    "LEFT_CONTROL": "Ctrl",
    "LCTRL": "Ctrl",
    "LEFT_CTRL": "Ctrl",
    "RCONTROL": "Ctrl",
    "RIGHT_CONTROL": "Ctrl",
    "RCTRL": "Ctrl",
    "RIGHT_CTRL": "Ctrl",
    "LMENU": "Alt",
    "LEFT_MENU": "Alt",
    "LALT": "Alt",
    "LEFT_ALT": "Alt",
    "RMENU": "Alt",
    "RIGHT_MENU": "Alt",
    "RALT": "Alt",
    "RIGHT_ALT": "Alt",
    "OEM_1": ";",
    "SEMICOLON": ";",
    "SEMI_COLON": ";",
    "OEM_PLUS": "=",
    "PLUS": "=",
    "EQUALS": "=",
    "OEM_COMMA": ",",
    "COMMA": ",",
    "OEM_MINUS": "-",
    "MINUS": "-",
    "UNDERSCORE": "-",
    "OEM_PERIOD": ".",
    "PERIOD": ".",
    "OEM_2": "/",
    "SLASH": "/",
    "FORWARD_SLASH": "/",
    "QUESTION": "/",
    "QUESTION_MARK": "/",
    "OEM_3": "`",
    "TILDE": "`",
    "GRAVE": "`",
    "OEM_4": "[",
    "OEM_5": "\\",
    "BACKSLASH": "\\",
    "BACK_SLASH": "\\",
    "PIPE": "\\",
    "VERTICAL_BAR": "\\",
    "OEM_6": "]",
    "OEM_7": "'",
    "QUOTE": "'",
    "DOUBLE_QUOTE": "'",
    "OEM_8": "OEM_8",
    "OEM_102": "OEM_102",
    "PROCESSKEY": "ProcessKey",
    "ATTN": "Attn",
    "CRSEL": "CrSel",
    "EXSEL": "ExSel",
    "EREOF": "ErEof",
    "PLAY": "Play",
    "ZOOM": "Zoom",
    "NONAME": "NoName",
    "PA1": "PA1",
    "OEM_CLEAR": "OEM_CLEAR",
    "MULTIPLY": "小键盘 *",
    "ADD": "小键盘 +",
    "SEPARATOR": "小键盘 ,",
    "SUBTRACT": "小键盘 -",
    "DECIMAL": "小键盘 .",
    "DIVIDE": "小键盘 /",
}

for _index in range(1, 25):
    _VK_LABELS[f"F{_index}"] = f"F{_index}"

for _index in range(10):
    _VK_LABELS[f"NUMPAD{_index}"] = f"小键盘 {_index}"

# Readable labels for numeric virtual-key codes (hex key bindings).
_VK_CODE_LABELS: dict[int, str] = {
    0x01: "左键",
    0x02: "右键",
    0x03: "Cancel",
    0x04: "中键",
    0x05: "侧键1",
    0x06: "侧键2",
    0x08: "Backspace",
    0x09: "Tab",
    0x0C: "Clear",
    0x0D: "Enter",
    0x10: "Shift",
    0x11: "Ctrl",
    0x12: "Alt",
    0x13: "Pause",
    0x14: "CapsLock",
    0x1B: "Esc",
    0x20: "Space",
    0x21: "PgUp",
    0x22: "PgDn",
    0x23: "End",
    0x24: "Home",
    0x25: "←",
    0x26: "↑",
    0x27: "→",
    0x28: "↓",
    0x2C: "PrintScreen",
    0x2D: "Insert",
    0x2E: "Delete",
    0x5B: "Win",
    0x5C: "Win",
    0x5D: "Menu",
    0x5F: "Sleep",
    0x90: "NumLock",
    0x91: "ScrollLock",
    0xA0: "Shift",
    0xA1: "Shift",
    0xA2: "Ctrl",
    0xA3: "Ctrl",
    0xA4: "Alt",
    0xA5: "Alt",
    0xBA: ";",
    0xBB: "=",
    0xBC: ",",
    0xBD: "-",
    0xBE: ".",
    0xBF: "/",
    0xC0: "`",
    0xDB: "[",
    0xDC: "\\",
    0xDD: "]",
    0xDE: "'",
    0xDF: "OEM_8",
    0xE2: "OEM_102",
}

for _index in range(10):
    _VK_CODE_LABELS[0x30 + _index] = str(_index)
    _VK_CODE_LABELS[0x60 + _index] = f"小键盘 {_index}"

for _code in range(0x41, 0x5B):
    _VK_CODE_LABELS[_code] = chr(_code)

_VK_CODE_LABELS.update(
    {
        0x6A: "小键盘 *",
        0x6B: "小键盘 +",
        0x6C: "小键盘 ,",
        0x6D: "小键盘 -",
        0x6E: "小键盘 .",
        0x6F: "小键盘 /",
    }
)

for _index in range(1, 25):
    _VK_CODE_LABELS[0x6F + _index] = f"F{_index}"

_XBOX_BUTTONS: dict[str, str] = {
    "A": "A",
    "B": "B",
    "X": "X",
    "Y": "Y",
    "START": "Start",
    "BACK": "Back",
    "GUIDE": "Guide",
    "DPAD_UP": "↑",
    "DPAD_DOWN": "↓",
    "DPAD_LEFT": "←",
    "DPAD_RIGHT": "→",
    "LEFT_TRIGGER": "LT",
    "RIGHT_TRIGGER": "RT",
    "LEFT_SHOULDER": "LB",
    "RIGHT_SHOULDER": "RB",
    "LEFT_THUMB": "LS",
    "RIGHT_THUMB": "RS",
}


def _xbox_label(token: str) -> str | None:
    match = _XBOX_RE.match(token)
    if match is None:
        return None
    controller, button = match.groups()
    label = _XBOX_BUTTONS.get(button.upper(), button.upper().replace("_", " ").title())
    prefix = f"手柄{controller} " if controller else "手柄 "
    return f"{prefix}{label}"


def _token_label(token: str) -> str:
    if len(token) == 1:
        return token.upper() if token.isalpha() else token

    xbox = _xbox_label(token)
    if xbox is not None:
        return xbox

    if token.casefold().startswith("0x"):
        try:
            code = int(token, 16)
        except ValueError:
            return token.upper()
        return _VK_CODE_LABELS.get(code, f"0x{code:02X}")

    name = token[3:] if token.casefold().startswith("vk_") else token
    return _VK_LABELS.get(name.upper(), name.upper())


def format_key(raw: str) -> str:
    """Turn one ini ``key``/``back`` value into a human-readable shortcut."""
    labels = [
        label
        for token in raw.split()
        if not token.casefold().startswith("no_")
        for label in [_token_label(token)]
        if label
    ]
    return "+".join(labels)


def _kind(type_value: str) -> HotkeyKind:
    match type_value.strip().casefold():
        case "cycle" | "toggle":
            return HotkeyKind.SWITCH
        case "hold":
            return HotkeyKind.HOLD
        case _:
            return HotkeyKind.OTHER


def _parse_ini(text: str, source: str) -> list[Hotkey]:
    entries: list[Hotkey] = []
    section: str | None = None
    raw_keys: list[str] = []
    raw_backs: list[str] = []
    type_value = ""
    # Running counts per (section name, field) across the whole file, so a
    # duplicated section name keeps counting instead of restarting at 0. This
    # mirrors how apply_hotkey scans the file and lets each Hotkey round-trip
    # back to its exact line even when two sections share a name.
    counts: dict[tuple[str, str], int] = {}

    def flush() -> None:
        if section is None or not section.casefold().startswith("key"):
            return
        kind = _kind(type_value)
        for raw in raw_keys:
            index = counts.get((section.casefold(), "key"), 0)
            counts[(section.casefold(), "key")] = index + 1
            display = format_key(raw)
            if display:
                entries.append(Hotkey(display, section, source, kind, False, raw, "key", index))
        for raw in raw_backs:
            index = counts.get((section.casefold(), "back"), 0)
            counts[(section.casefold(), "back")] = index + 1
            display = format_key(raw)
            if display:
                entries.append(Hotkey(display, section, source, kind, True, raw, "back", index))

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in ";#":
            continue

        section_match = _SECTION_RE.match(line)
        if section_match is not None:
            flush()
            section = section_match.group(1).strip()
            raw_keys = []
            raw_backs = []
            type_value = ""
            continue

        if section is None:
            continue

        field_match = _FIELD_RE.match(line)
        if field_match is None:
            continue
        field, value = field_match.group(1).casefold(), field_match.group(2).strip()
        if field == "key":
            raw_keys.append(value)
        elif field == "back":
            raw_backs.append(value)
        else:
            type_value = value

    flush()
    return entries


def _iter_ini_files(mod_path: Path) -> list[Path]:
    if not mod_path.is_dir():
        return []

    files: list[Path] = []
    for root, dirnames, filenames in os.walk(mod_path, followlinks=False):
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".") and not name.casefold().startswith("disabled")
        ]
        for name in filenames:
            if name.startswith(".") or name.casefold().startswith("disabled"):
                continue
            if not name.casefold().endswith(".ini"):
                continue
            files.append(Path(root) / name)

    files.sort(key=lambda path: path.relative_to(mod_path).as_posix().casefold())
    return files


def parse_mod_hotkeys(mod_path: Path) -> list[Hotkey]:
    """Read every active ini under *mod_path* and return its key bindings."""
    root = Path(mod_path)
    entries: list[Hotkey] = []
    for ini in _iter_ini_files(root):
        try:
            text = ini.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError as exc:
            log.warning("无法读取 ini %s：%s", ini, exc)
            continue
        entries.extend(_parse_ini(text, ini.relative_to(root).as_posix()))
    return entries
