import json
from pathlib import Path

import pytest

from wwmm.roster import parse_roster

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def roster_data():
    return json.loads((FIXTURES / "roster.json").read_text(encoding="utf-8"))


@pytest.fixture
def roster(roster_data):
    return parse_roster(roster_data)


@pytest.fixture
def roster_file():
    return FIXTURES / "roster.json"


MODS_TREE_FILES = (
    "aemeath/Aemeath - Sky Pixie/mod.ini",
    "aemeath/Aemeath - Sky Pixie/Weapon/Sword/mod.ini",
    "aemeath/DISABLED_Aemeath - Old/mod.ini",
    "denia/达妮娅-红绳捆绑/mod.ini",
    "denia/达妮娅-红绳捆绑/Textures/Tex.ini",
    "hsin/心-黑桃爱丽丝/Master.ini",
    "rover/漂泊者-默认/mod.ini",
    "others/UI/mod.ini",
    "unknown/Unknown Mod/mod.ini",
)


@pytest.fixture
def mods_tree(tmp_path):
    root = tmp_path / "Mods"
    for relative in MODS_TREE_FILES:
        path = root / "character" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    (root / "character" / "lynae").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def tmp_mods_root(tmp_path):
    root = tmp_path / "Mods"
    (root / "character").mkdir(parents=True)
    return root
