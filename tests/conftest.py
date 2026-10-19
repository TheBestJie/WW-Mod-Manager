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
