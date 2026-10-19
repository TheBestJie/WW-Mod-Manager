import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
UNINSTALL = ROOT / "uninstall.sh"
MARK_START = "# >>> wwmm installer >>>"
BASH = shutil.which("bash") or "/bin/bash"

FAKE_UV = """#!/usr/bin/env python3
import pathlib
import sys

root = pathlib.Path(sys.argv[0]).resolve().parent.parent
bin_dir = root / "toolbin"
state = root / "installed"
args = sys.argv[1:]

if args == ["tool", "dir", "--bin"]:
    print(bin_dir)
    raise SystemExit(0)

if args[:2] == ["tool", "install"]:
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / "wwmm"
    exe.write_text("#!/usr/bin/env bash\\necho 'wwmm 0.1.0'\\n", encoding="utf-8")
    exe.chmod(0o755)
    state.write_text("installed", encoding="utf-8")
    raise SystemExit(0)

if args == ["tool", "list"]:
    if state.exists():
        print("ww-mod-manager v0.1.0")
        print("- wwmm")
    else:
        print("No tools installed")
    raise SystemExit(0)

if args == ["tool", "uninstall", "ww-mod-manager"]:
    if not state.exists():
        print("error: `ww-mod-manager` is not installed", file=sys.stderr)
        raise SystemExit(2)
    state.unlink()
    exe = bin_dir / "wwmm"
    if exe.exists():
        exe.unlink()
    raise SystemExit(0)

print(f"unexpected uv args: {args}", file=sys.stderr)
raise SystemExit(1)
"""


def _setup(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    config = tmp_path / "config"
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    uv = fake_bin / "uv"
    uv.write_text(FAKE_UV, encoding="utf-8")
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config),
            "ZDOTDIR": str(home),
            "SHELL": "/bin/bash",
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    return env, home, config, tmp_path / "toolbin", tmp_path / "installed"


def _run(script, env, *args):
    return subprocess.run(
        [BASH, str(script), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _configs(home, config):
    return (
        home / ".bashrc",
        home / ".zshrc",
        config / "fish" / "config.fish",
    )


def test_uninstall_removes_tool_and_shell_blocks(tmp_path):
    env, home, config, toolbin, state = _setup(tmp_path)
    (home / ".bashrc").write_text("export FOO=bar\n", encoding="utf-8")
    assert _run(INSTALL, env).returncode == 0
    assert state.exists()
    assert (toolbin / "wwmm").exists()

    result = _run(UNINSTALL, env)
    assert result.returncode == 0, result.stderr
    assert not state.exists()
    assert not (toolbin / "wwmm").exists()

    for path in _configs(home, config):
        text = path.read_text(encoding="utf-8")
        assert MARK_START not in text
    assert "export FOO=bar" in (home / ".bashrc").read_text(encoding="utf-8")


def test_uninstall_is_idempotent(tmp_path):
    env, home, config, _toolbin, _state = _setup(tmp_path)
    assert _run(INSTALL, env).returncode == 0

    first = _run(UNINSTALL, env)
    second = _run(UNINSTALL, env)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    for path in _configs(home, config):
        assert MARK_START not in path.read_text(encoding="utf-8")


def test_keep_shell_config_only_removes_tool(tmp_path):
    env, home, config, toolbin, state = _setup(tmp_path)
    assert _run(INSTALL, env).returncode == 0

    result = _run(UNINSTALL, env, "--keep-shell-config")
    assert result.returncode == 0, result.stderr
    assert not state.exists()
    assert not (toolbin / "wwmm").exists()
    for path in _configs(home, config):
        assert MARK_START in path.read_text(encoding="utf-8")


def test_uninstall_help_does_not_change_anything(tmp_path):
    env, home, config, _toolbin, state = _setup(tmp_path)
    assert _run(INSTALL, env).returncode == 0
    before = {path: path.read_bytes() for path in _configs(home, config)}

    result = _run(UNINSTALL, env, "--help")
    assert result.returncode == 0
    assert "用法" in result.stdout
    assert state.exists()
    for path, content in before.items():
        assert path.read_bytes() == content


def test_uninstall_without_uv_still_cleans_shell_config(tmp_path):
    env, home, config, _toolbin, _state = _setup(tmp_path)
    assert _run(INSTALL, env).returncode == 0

    coreutils = tmp_path / "coreutils"
    coreutils.mkdir()
    for name in ("awk", "cat", "grep", "mktemp", "rm"):
        source = shutil.which(name)
        assert source is not None
        (coreutils / name).symlink_to(source)
    env["PATH"] = str(coreutils)

    result = _run(UNINSTALL, env)
    assert result.returncode == 1
    assert "uv" in result.stderr
    for path in _configs(home, config):
        assert MARK_START not in path.read_text(encoding="utf-8")


def test_unknown_option_fails(tmp_path):
    env, _home, _config, _toolbin, _state = _setup(tmp_path)
    result = _run(UNINSTALL, env, "--definitely-not-an-option")
    assert result.returncode != 0
