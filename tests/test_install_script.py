import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "install.sh"
MARK_START = "# >>> wwmm installer >>>"

FAKE_UV = """#!/usr/bin/env python3
import pathlib
import sys

bin_dir = pathlib.Path(sys.argv[0]).resolve().parent.parent / "toolbin"
args = sys.argv[1:]

if args == ["tool", "dir", "--bin"]:
    print(bin_dir)
    raise SystemExit(0)

if args[:2] == ["tool", "install"]:
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / "wwmm"
    exe.write_text("#!/usr/bin/env bash\\necho 'wwmm 0.1.0'\\n", encoding="utf-8")
    exe.chmod(0o755)
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
    return env, home, config, tmp_path / "toolbin"


def _run(env, *args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
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


def test_install_configures_bash_zsh_and_fish(tmp_path):
    env, home, config, toolbin = _setup(tmp_path)
    result = _run(env)
    assert result.returncode == 0, result.stderr
    assert "wwmm 0.1.0" in result.stdout

    executable = toolbin / "wwmm"
    assert executable.is_file()
    assert os.access(executable, os.X_OK)

    for path in _configs(home, config):
        text = path.read_text(encoding="utf-8")
        assert MARK_START in text
        assert str(toolbin) in text

    if shutil.which("bash"):
        subprocess.run(["bash", "-n", str(home / ".bashrc")], check=True)
    if shutil.which("fish"):
        subprocess.run(["fish", "-n", str(config / "fish" / "config.fish")], check=True)


def test_install_is_idempotent_and_preserves_existing_content(tmp_path):
    env, home, config, _toolbin = _setup(tmp_path)
    (home / ".bashrc").write_text("export FOO=bar\n", encoding="utf-8")

    assert _run(env).returncode == 0
    assert _run(env).returncode == 0

    for path in _configs(home, config):
        text = path.read_text(encoding="utf-8")
        assert text.count(MARK_START) == 1, path
    assert "export FOO=bar" in (home / ".bashrc").read_text(encoding="utf-8")


def test_install_replaces_old_path_block(tmp_path):
    env, home, _config, _toolbin = _setup(tmp_path)
    (home / ".bashrc").write_text(
        f'{MARK_START}\nexport PATH="/old/wwmm/bin:$PATH"\n# <<< wwmm installer <<<\n',
        encoding="utf-8",
    )

    assert _run(env).returncode == 0
    text = (home / ".bashrc").read_text(encoding="utf-8")
    assert "/old/wwmm/bin" not in text
    assert text.count(MARK_START) == 1


def test_no_path_skips_shell_configuration(tmp_path):
    env, home, config, _toolbin = _setup(tmp_path)
    result = _run(env, "--no-path")
    assert result.returncode == 0, result.stderr
    assert not (home / ".bashrc").exists()
    assert not (home / ".zshrc").exists()
    assert not (config / "fish" / "config.fish").exists()


def test_help_does_not_install(tmp_path):
    env, _home, _config, toolbin = _setup(tmp_path)
    result = _run(env, "--help")
    assert result.returncode == 0
    assert "用法" in result.stdout
    assert not toolbin.exists()


def test_unknown_option_fails(tmp_path):
    env, _home, _config, _toolbin = _setup(tmp_path)
    result = _run(env, "--definitely-not-an-option")
    assert result.returncode != 0
