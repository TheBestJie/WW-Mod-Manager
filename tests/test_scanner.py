import pytest

from wwmm.errors import LayoutError
from wwmm.scanner import scan


def test_nested_ini_files_count_as_one_mod(mods_tree, roster):
    snapshot = scan(mods_tree, roster)
    aemeath = snapshot.find("aemeath")
    assert aemeath.total_count == 2
    assert aemeath.enabled_count == 1
    enabled = aemeath.mods[0]
    assert enabled.base_name == "Aemeath - Sky Pixie"
    assert enabled.ini_count == 2


def test_disabled_prefix_is_detected(mods_tree, roster):
    aemeath = scan(mods_tree, roster).find("aemeath")
    assert [m.enabled for m in aemeath.mods] == [True, False]


def test_empty_roster_character_has_zero_mods(mods_tree, roster):
    lynae = scan(mods_tree, roster).find("lynae")
    assert lynae.total_count == 0
    assert lynae.has_mods is False


def test_unknown_dir_goes_to_unclassified(mods_tree, roster):
    snapshot = scan(mods_tree, roster)
    assert [e.character.slug for e in snapshot.groups["未分类"]] == ["unknown"]


def test_rover_and_others_groups(mods_tree, roster):
    snapshot = scan(mods_tree, roster)
    assert snapshot.groups["多属性"][0].character.slug == "rover"
    assert snapshot.groups["其他"][0].character.slug == "others"


def test_missing_character_root_raises(tmp_path, roster):
    with pytest.raises(LayoutError):
        scan(tmp_path, roster)
