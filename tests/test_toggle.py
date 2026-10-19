import errno

import pytest

from wwmm.errors import ToggleError
from wwmm.models import Mod
from wwmm.toggle import toggle_mod


def test_disable_and_enable_roundtrip(tmp_path):
    folder = tmp_path / "达妮娅-巫女"
    folder.mkdir()
    mod = Mod(path=folder, folder_name=folder.name, enabled=True, ini_count=1)
    disabled = toggle_mod(mod)
    assert disabled.folder_name == "DISABLED_达妮娅-巫女"
    assert disabled.path.is_dir()
    enabled = toggle_mod(disabled)
    assert enabled.folder_name == "达妮娅-巫女"
    assert enabled.path.is_dir()


def test_collision_aborts_without_changes(tmp_path):
    (tmp_path / "Foo").mkdir()
    (tmp_path / "DISABLED_Foo").mkdir()
    mod = Mod(path=tmp_path / "Foo", folder_name="Foo", enabled=True, ini_count=1)
    with pytest.raises(ToggleError):
        toggle_mod(mod, enable=False)
    assert (tmp_path / "Foo").is_dir()
    assert (tmp_path / "DISABLED_Foo").is_dir()


def test_permission_error_becomes_toggle_error(tmp_path, monkeypatch):
    folder = tmp_path / "Foo"
    folder.mkdir()
    mod = Mod(path=folder, folder_name="Foo", enabled=True, ini_count=1)

    def deny(*args, **kwargs):
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr("wwmm.toggle.os.rename", deny)
    with pytest.raises(ToggleError, match="没有权限"):
        toggle_mod(mod, enable=False)
    assert folder.is_dir()


def test_name_too_long_becomes_toggle_error(tmp_path, monkeypatch):
    folder = tmp_path / "Foo"
    folder.mkdir()
    mod = Mod(path=folder, folder_name="Foo", enabled=True, ini_count=1)

    def too_long(*args, **kwargs):
        raise OSError(errno.ENAMETOOLONG, "too long")

    monkeypatch.setattr("wwmm.toggle.os.rename", too_long)
    with pytest.raises(ToggleError, match="过长"):
        toggle_mod(mod, enable=False)
    assert folder.is_dir()


def test_internal_disabled_folder_is_untouched(tmp_path):
    mod_dir = tmp_path / "Foo"
    (mod_dir / "DISABLED").mkdir(parents=True)
    mod = Mod(path=mod_dir, folder_name="Foo", enabled=True, ini_count=0)
    toggle_mod(mod)
    assert (tmp_path / "DISABLED_Foo" / "DISABLED").is_dir()


def test_double_prefix_strips_only_one_level(tmp_path):
    folder = tmp_path / "DISABLED_DISABLED_Foo"
    folder.mkdir()
    mod = Mod(path=folder, folder_name=folder.name, enabled=False, ini_count=1)
    enabled = toggle_mod(mod, enable=True)
    assert enabled.folder_name == "DISABLED_Foo"
    assert enabled.base_name == "Foo"
    assert not (tmp_path / "Foo").exists()
