import pytest

from wwmm.errors import LayoutError
from wwmm.roster import ensure_character_dirs


def test_creates_missing_dirs_and_others(tmp_path, roster):
    root = tmp_path / "Mods"
    (root / "character" / "denia").mkdir(parents=True)
    result = ensure_character_dirs(roster, root)
    assert {p.name for p in result.created} == {"aemeath", "hsin", "lynae", "rover", "others"}
    assert (root / "character" / "denia").is_dir()
    assert not result.errors


def test_case_insensitive_existing_dir_is_not_duplicated(tmp_path, roster):
    root = tmp_path / "Mods"
    (root / "character" / "DENIA").mkdir(parents=True)
    ensure_character_dirs(roster, root)
    assert not (root / "character" / "denia").exists()
    assert (root / "character" / "DENIA").is_dir()


def test_existing_unknown_dirs_are_never_deleted(tmp_path, roster):
    root = tmp_path / "Mods"
    (root / "character" / "keep-me").mkdir(parents=True)
    ensure_character_dirs(roster, root)
    assert (root / "character" / "keep-me").is_dir()


def test_file_with_character_name_is_reported_not_overwritten(tmp_path, roster):
    root = tmp_path / "Mods"
    (root / "character").mkdir(parents=True)
    (root / "character" / "aemeath").write_text("x", encoding="utf-8")
    result = ensure_character_dirs(roster, root)
    assert any("aemeath" in str(p) for p, _ in result.errors)
    assert (root / "character" / "aemeath").is_file()


def test_missing_mods_root_is_rejected(tmp_path, roster):
    with pytest.raises(LayoutError):
        ensure_character_dirs(roster, tmp_path / "missing")
