"""Validate 3Dmigoto key expressions and write them back into mod ini files."""

from __future__ import annotations

import os
import re
from pathlib import Path

from wwmm.errors import HotkeyEditError
from wwmm.hotkeys import _FIELD_RE, _SECTION_RE, _VK_LABELS, _XBOX_RE

_TOKEN_SPLIT_RE = re.compile(r"[\s+]+")

_USAGE_HINT = (
    "不支持的按键：{}；可用写法：字母/数字、VK_ 名称、0x 十六进制、"
    "XB_ 手柄键，修饰键 ctrl/shift/alt/win"
)


def _valid_token(token: str) -> bool:
    if len(token) == 1:
        return token.isascii() and token.isprintable()
    if _XBOX_RE.match(token) is not None:
        return True
    if token.casefold().startswith("0x"):
        try:
            int(token, 16)
        except ValueError:
            return False
        return True
    name = token[3:] if token.casefold().startswith(("vk_", "no_")) else token
    return name.upper() in _VK_LABELS or token.upper() == "NO_MODIFIERS"


def _key_label(token: str) -> str:
    """Map a token to the label used for the ``no_`` exclusion collision check."""
    name = token[3:] if token.casefold().startswith("no_") else token
    return _VK_LABELS.get(name.upper(), name.upper())


def validate_key_expr(text: str) -> str:
    """Return *text* as a normalized key expression or raise :class:`HotkeyEditError`."""
    tokens = _TOKEN_SPLIT_RE.split(text.strip())
    if any(token == "" for token in tokens):
        raise HotkeyEditError("按键组合不能为空")
    bad = [token for token in tokens if not _valid_token(token)]
    if bad:
        raise HotkeyEditError(_USAGE_HINT.format("、".join(bad)))
    # A ``no_*`` token only excludes a key; if every real key is excluded (or none
    # is left) the expression parses to an empty binding and the ini would end up
    # with a line that the hotkey list silently drops.
    excluded = {_key_label(token) for token in tokens if token.casefold().startswith("no_")}
    real = {_key_label(token) for token in tokens if not token.casefold().startswith("no_")}
    if not real - excluded:
        raise HotkeyEditError("至少需要一个按键，不能只写排除项")
    return " ".join(tokens)


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
        raise HotkeyEditError(f"未找到快捷键：[{section}] {field} 第 {occurrence + 1} 处（{source}）")

    encoding = "utf-8-sig" if had_bom else "utf-8"
    payload = "".join(out).encode(encoding, errors="surrogateescape")
    tmp = ini.with_name(ini.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, ini)
