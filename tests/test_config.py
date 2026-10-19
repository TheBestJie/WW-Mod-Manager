from wwmm.config import Config, ConfigStore
from wwmm.paths import config_dir


def test_roundtrip_with_unicode_path(tmp_path):
    store = ConfigStore(tmp_path)
    cfg = Config(
        mods_dir=tmp_path / "Mods 目录 with spaces",
        roster_url="https://example.com/roster.json",
        auto_create_folders=False,
    )
    store.save(cfg)
    assert store.load() == cfg


def test_missing_file_returns_defaults(tmp_path):
    cfg = ConfigStore(tmp_path).load()
    assert cfg.mods_dir is None
    assert cfg.roster_url.endswith("/data/roster.json")


def test_corrupt_file_is_moved_aside(tmp_path):
    (tmp_path / "config.toml").write_text("not = [valid toml", encoding="utf-8")
    cfg = ConfigStore(tmp_path).load()
    assert cfg.mods_dir is None
    assert (tmp_path / "config.toml.bad").exists()


def test_paths_follow_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert config_dir() == tmp_path / "cfg" / "wwmm"
