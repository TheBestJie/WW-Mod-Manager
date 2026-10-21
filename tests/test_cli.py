import pytest

from wwmm.cli import main


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "1.3.1" in capsys.readouterr().out


def test_update_from_file_creates_dirs(tmp_path, roster_file, capsys, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    mods = tmp_path / "Mods"
    (mods / "character" / "denia").mkdir(parents=True)
    rc = main(["update", "--from", str(roster_file), "--mods-dir", str(mods)])
    assert rc == 0
    assert (mods / "character" / "aemeath").is_dir()
    assert "已补全" in capsys.readouterr().out


def test_update_without_mods_dir_returns_2(tmp_path, roster_file, capsys, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    rc = main(["update", "--from", str(roster_file)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "Mods" in captured.err or "目录" in captured.err


def test_update_rejects_invalid_mods_dir(tmp_path, roster_file, capsys, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    plain = tmp_path / "plain"
    plain.mkdir()
    rc = main(["update", "--from", str(roster_file), "--mods-dir", str(plain)])
    assert rc == 2
    assert not (plain / "character").exists()
    assert "有效的" in capsys.readouterr().err


def test_update_dry_run_does_not_touch_fs(tmp_path, roster_file, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    mods = tmp_path / "Mods"
    (mods / "character").mkdir(parents=True)
    rc = main(["update", "--from", str(roster_file), "--dry-run", "--mods-dir", str(mods)])
    assert rc == 0
    assert not (mods / "character" / "aemeath").exists()
    assert not (tmp_path / "data" / "roster.json").exists()
    assert not (tmp_path / "config" / "wwmm" / "config.toml").exists()
