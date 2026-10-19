import json
from pathlib import Path

import pytest

from wwmm.errors import RosterBuildError
from wwmm.roster_build import (
    ELEMENT_BY_ID,
    build_roster,
    load_textmap,
    slugify,
    validate_roster_dict,
)

FIXTURES = Path(__file__).parent / "fixtures" / "arikatsu"
OVERRIDES = {
    "slugs": {"Rover": "rover"},
    "aliases": {"Hsin": ["心月狐", "xinyuehu"]},
}


def _build():
    roles = json.loads((FIXTURES / "roleinfo.json").read_text(encoding="utf-8"))
    zh = load_textmap(FIXTURES / "zh.json")
    en = load_textmap(FIXTURES / "en.json")
    return build_roster(
        roles,
        zh,
        en,
        branch="test",
        commit="abc",
        committed_at="2026-10-19T00:00:00Z",
        overrides=OVERRIDES,
    )


def test_element_id_map():
    assert ELEMENT_BY_ID[1] == "冷凝"
    assert ELEMENT_BY_ID[2] == "热熔"
    assert ELEMENT_BY_ID[6] == "湮灭"


def test_slugify():
    assert slugify("Yangyang: Xuanling") == "yangyangxuanling"
    assert slugify("Luuk Herssen") == "luukherssen"


def test_rover_forms_merge():
    roster = _build()
    rover = next(c for c in roster["characters"] if c["slug"] == "rover")
    assert rover["elements"] == ["衍射", "湮灭"]
    assert rover["name_zh"] == "漂泊者"


def test_build_fixture_matches_expected():
    built = _build()
    expected = json.loads((FIXTURES / "expected_roster.json").read_text(encoding="utf-8"))
    assert built["game_version"] == "test"
    assert built["characters"] == expected["characters"]


def _valid_built():
    data = _build()
    data["characters"].insert(
        0,
        {
            "slug": "sanhua",
            "name_zh": "散华",
            "name_en": "Sanhua",
            "elements": ["冷凝"],
            "pinyin": "sanhua",
            "initials": "sh",
            "aliases": ["散华", "sanhua"],
            "folder": "sanhua",
            "special": False,
        },
    )
    data["characters"].insert(
        1,
        {
            "slug": "yangyang",
            "name_zh": "秧秧",
            "name_en": "Yangyang",
            "elements": ["气动"],
            "pinyin": "yangyang",
            "initials": "yy",
            "aliases": ["秧秧", "yangyang"],
            "folder": "yangyang",
            "special": False,
        },
    )
    return data


def test_validation_accepts_complete_roster():
    validate_roster_dict(_valid_built(), min_characters=1)


def test_validation_rejects_missing_element():
    data = _valid_built()
    data["characters"] = [c for c in data["characters"] if "冷凝" not in c["elements"]]
    with pytest.raises(RosterBuildError):
        validate_roster_dict(data, min_characters=1)


def test_validation_rejects_missing_rover():
    data = _valid_built()
    data["characters"] = [c for c in data["characters"] if c["slug"] != "rover"]
    with pytest.raises(RosterBuildError):
        validate_roster_dict(data, min_characters=1)


def test_validation_rejects_missing_others():
    data = _valid_built()
    data["characters"] = [c for c in data["characters"] if c["slug"] != "others"]
    with pytest.raises(RosterBuildError):
        validate_roster_dict(data, min_characters=1)


def test_validation_rejects_duplicate_slug():
    data = _valid_built()
    data["characters"].append({**data["characters"][0], "folder": "copy"})
    with pytest.raises(RosterBuildError):
        validate_roster_dict(data, min_characters=1)


def test_validation_rejects_empty_roster():
    with pytest.raises(RosterBuildError):
        validate_roster_dict({"schema_version": 1, "characters": []})
