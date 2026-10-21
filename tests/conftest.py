import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wwmm.app import WWMMApp
from wwmm.config import Config, ConfigStore
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


def _offline_release_checker(**kwargs):
    """Fake release check so tests never reach the network."""
    return


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


@pytest.fixture
def app(tmp_path, roster, mods_tree):
    config_store = ConfigStore(tmp_path / "config")
    config = Config(mods_dir=mods_tree, auto_create_folders=True)
    config_store.save(config)
    return WWMMApp(
        config_store=config_store,
        config=config,
        roster=roster,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        home_dir=tmp_path / "home",
        release_checker=_offline_release_checker,
    )


@pytest.fixture
def app_without_mods(tmp_path, roster):
    config_store = ConfigStore(tmp_path / "config")
    return WWMMApp(
        config_store=config_store,
        config=Config(),
        roster=roster,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        home_dir=tmp_path / "home",
        release_checker=_offline_release_checker,
    )


@pytest.fixture
def sparse_app(tmp_path, roster):
    mods = tmp_path / "Mods"
    (mods / "character" / "denia").mkdir(parents=True)
    config_store = ConfigStore(tmp_path / "config")
    config = Config(mods_dir=mods, auto_create_folders=True)
    config_store.save(config)
    return WWMMApp(
        config_store=config_store,
        config=config,
        roster=roster,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        home_dir=tmp_path / "home",
        release_checker=_offline_release_checker,
    )
