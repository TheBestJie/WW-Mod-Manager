from pathlib import Path

from wwmm.models import Mod
from wwmm.search import character_matches, element_for_query, mod_matches


def test_pinyin_initials_match(roster):
    deny = roster.by_slug("denia")
    assert character_matches(deny, "dn")
    assert character_matches(deny, "dny")
    assert character_matches(deny, "daniya")
    assert character_matches(deny, "达妮娅")


def test_element_alias_matches(roster):
    hsin = roster.by_slug("hsin")
    assert element_for_query("雷") == "导电"
    assert character_matches(hsin, "雷")
    assert character_matches(hsin, "电磁")


def test_unrelated_query_does_not_match(roster):
    assert not character_matches(roster.by_slug("denia"), "zzzz")


def test_mod_filter_matches_chinese_and_ascii():
    mod = Mod(path=Path("/tmp/达妮娅-巫女"), folder_name="达妮娅-巫女", enabled=True, ini_count=1)
    assert mod_matches(mod, "巫女")
    assert mod_matches(mod, "dny") is False
    assert mod_matches(mod, "denia") is False
