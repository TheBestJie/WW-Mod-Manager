from wwmm.roster import load_bundled_roster


def test_bundled_roster_is_valid():
    roster = load_bundled_roster()
    assert roster.schema_version == 1
    assert len(roster.characters) == 58
    assert roster.by_folder("lucilla").name_zh == "洛瑟菈"
    assert roster.by_folder("rover").group == "多属性"
    assert roster.by_folder("others").group == "其他"
    assert {c.group for c in roster.characters} == {
        "冷凝",
        "热熔",
        "导电",
        "气动",
        "衍射",
        "湮灭",
        "多属性",
        "其他",
    }
