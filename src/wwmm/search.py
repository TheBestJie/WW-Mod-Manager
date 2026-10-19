"""Search characters and mods by name, pinyin, initials and element aliases."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from wwmm.constants import ELEMENT_ALIASES, ELEMENTS
from wwmm.models import Character, CharacterEntry, Mod


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in normalized if char.isalnum())


def _is_subsequence(needle: str, haystack: str) -> bool:
    iterator = iter(haystack)
    return all(char in iterator for char in needle)


def _matches(haystack: str, query: str) -> bool:
    candidate = normalize(haystack)
    if not candidate:
        return False
    if query in candidate:
        return True
    if not query.isascii():
        return False
    return _is_subsequence(query, candidate)


def element_for_query(query: str) -> str | None:
    normalized = normalize(query)
    if not normalized:
        return None
    if normalized in ELEMENT_ALIASES:
        return ELEMENT_ALIASES[normalized]
    if normalized in ELEMENTS:
        return normalized
    return None


def character_matches(character: Character, query: str) -> bool:
    normalized = normalize(query)
    if not normalized:
        return True

    element = element_for_query(normalized)
    if element is not None:
        return element in character.elements

    terms = [
        character.name_zh,
        character.name_en,
        character.slug,
        character.pinyin,
        character.initials,
        character.folder,
        *character.aliases,
    ]
    return any(_matches(term, normalized) for term in terms)


def filter_characters(entries: Iterable[CharacterEntry], query: str) -> list[CharacterEntry]:
    if not normalize(query):
        return list(entries)
    return [entry for entry in entries if character_matches(entry.character, query)]


def mod_matches(mod: Mod, query: str) -> bool:
    normalized = normalize(query)
    if not normalized:
        return True
    return _matches(mod.display_name, normalized) or _matches(mod.folder_name, normalized)


def filter_mods(mods: Iterable[Mod], query: str) -> list[Mod]:
    if not normalize(query):
        return list(mods)
    return [mod for mod in mods if mod_matches(mod, query)]
