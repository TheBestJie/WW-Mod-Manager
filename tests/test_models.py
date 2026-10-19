from pathlib import Path

from wwmm.models import Character, Mod


def test_character_group_single_element():
    c = Character(
        slug="denia", name_zh="达妮娅", name_en="Denia", elements=("热熔",), folder="denia"
    )
    assert c.group == "热熔"


def test_character_group_multi_element():
    c = Character(
        slug="rover",
        name_zh="漂泊者",
        name_en="Rover",
        elements=("衍射", "湮灭", "气动", "导电"),
        folder="rover",
    )
    assert c.group == "多属性"


def test_character_group_others():
    c = Character(
        slug="others", name_zh="其他", name_en="Others", elements=(), folder="others", special=True
    )
    assert c.group == "其他"


def test_disabled_prefix_is_only_stripped_once():
    mod = Mod(
        path=Path("/tmp/DISABLED_DISABLED_Foo"),
        folder_name="DISABLED_DISABLED_Foo",
        enabled=False,
        ini_count=1,
    )
    assert mod.base_name == "DISABLED_Foo"
    assert mod.display_name == "DISABLED_Foo"
