import json

import pytest

from wwmm.errors import RosterError
from wwmm.roster import load_bundled_roster, load_effective_roster, parse_roster


def test_by_folder_is_case_insensitive(roster):
    assert roster.by_folder("DENIA").name_zh == "达妮娅"


def test_groups_are_complete_and_ordered(roster):
    groups = roster.groups()
    assert list(groups) == [
        "冷凝",
        "热熔",
        "导电",
        "气动",
        "衍射",
        "湮灭",
        "多属性",
        "其他",
        "未分类",
    ]
    assert [c.slug for c in groups["热熔"]] == ["aemeath", "denia"]
    assert [c.slug for c in groups["多属性"]] == ["rover"]


def test_duplicate_folder_is_rejected(roster_data):
    roster_data["characters"][1]["folder"] = "aemeath"
    with pytest.raises(RosterError):
        parse_roster(roster_data)


def test_invalid_element_is_rejected(roster_data):
    roster_data["characters"][0]["elements"] = ["雷"]
    with pytest.raises(RosterError):
        parse_roster(roster_data)


def test_others_is_appended_when_missing(roster_data):
    roster_data["characters"] = [c for c in roster_data["characters"] if c["slug"] != "others"]
    parsed = parse_roster(roster_data)
    assert parsed.by_slug("others") is not None


@pytest.mark.parametrize("folder", ["/tmp/evil", "../evil", "a/b", "..", "."])
def test_unsafe_folder_is_rejected(roster_data, folder):
    roster_data["characters"][0]["folder"] = folder
    with pytest.raises(RosterError):
        parse_roster(roster_data)


def test_non_utf8_local_roster_falls_back_to_bundled(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "roster.json").write_bytes(b"\xff\xfe\x00broken")
    parsed = load_effective_roster(data_dir)
    assert parsed.game_version == load_bundled_roster().game_version


def test_local_roster_overrides_bundled(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    local_data = {
        "schema_version": 1,
        "game_version": "local",
        "source": {
            "repo": "local",
            "branch": "local",
            "commit": "local",
            "committed_at": "2026-10-19T00:00:00Z",
        },
        "characters": [
            {
                "slug": "denia",
                "name_zh": "达妮娅",
                "name_en": "Denia",
                "elements": ["热熔"],
            }
        ],
    }
    (data_dir / "roster.json").write_text(
        json.dumps(local_data, ensure_ascii=False), encoding="utf-8"
    )
    parsed = load_effective_roster(data_dir)
    assert parsed.game_version == "local"
    assert parsed.characters[0].slug == "denia"
