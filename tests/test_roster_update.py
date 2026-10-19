import json

import pytest

from wwmm.errors import RosterDowngradeError, RosterUpdateError
from wwmm.roster_update import fetch_roster, update_roster


def _write_local(data_dir, source, roster_file):
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(roster_file.read_text(encoding="utf-8"))
    payload["source"]["committed_at"] = source
    (data_dir / "roster.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return (data_dir / "roster.json").read_bytes()


def test_update_from_file_writes_and_backs_up(tmp_path, roster_file):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "roster.json").write_text("{}", encoding="utf-8")
    result = update_roster(url="", data_dir=data_dir, from_file=roster_file)
    assert (data_dir / "roster.json").exists()
    assert (data_dir / "roster.json.bak").exists()
    assert result.game_version == "test"


def test_dry_run_does_not_write(tmp_path, roster_file):
    result = update_roster(url="", data_dir=tmp_path, from_file=roster_file, dry_run=True)
    assert result.dry_run is True
    assert not (tmp_path / "roster.json").exists()


def test_downgrade_is_rejected(tmp_path, roster_file):
    data_dir = tmp_path / "data"
    _write_local(data_dir, "2026-10-20T00:00:00Z", roster_file)
    with pytest.raises(RosterDowngradeError):
        update_roster(url="", data_dir=data_dir, from_file=roster_file)


def test_fetch_roster_parses_json(monkeypatch, roster_file):
    class FakeResponse:
        def read(self):
            return roster_file.read_bytes()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("wwmm.roster_update.urlopen", lambda *a, **k: FakeResponse())
    assert fetch_roster("https://example.com/roster.json").game_version == "test"


def test_invalid_roster_does_not_overwrite(tmp_path, roster_file):
    data_dir = tmp_path / "data"
    before = _write_local(data_dir, "2026-10-18T00:00:00Z", roster_file)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RosterUpdateError):
        update_roster(url="", data_dir=data_dir, from_file=bad)
    assert (data_dir / "roster.json").read_bytes() == before
