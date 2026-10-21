"""Tests for the GitHub release check and the self update core.

Everything here is hermetic: ``urlopen`` and ``subprocess`` are replaced by fakes,
nothing touches the network or the real repository.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from wwmm import __version__
from wwmm.errors import SelfUpdateError
from wwmm.self_update import (
    RELEASES_PAGE_URL,
    ReleaseInfo,
    SelfUpdateResult,
    UpdateCheck,
    check_for_update,
    fetch_latest_release,
    find_repo_root,
    parse_version,
    perform_self_update,
)

PYPROJECT_TEMPLATE = """[project]
name = "{name}"
version = "{version}"
"""


def _write_pyproject(root: Path, version: str = "1.3.0", name: str = "ww-mod-manager") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "pyproject.toml"
    path.write_text(PYPROJECT_TEMPLATE.format(name=name, version=version), encoding="utf-8")
    return path


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _recording_runner(calls: list, returncode: int = 0, stdout: str = "", stderr: str = ""):
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return _FakeCompleted(returncode=returncode, stdout=stdout, stderr=stderr)

    return run


def _uv_present(monkeypatch, path: str = "/usr/bin/uv") -> None:
    monkeypatch.setattr("wwmm.self_update.shutil.which", lambda name: path)


def test_parse_version():
    assert parse_version("1.3.0") == (1, 3, 0)
    assert parse_version("v1.3.0") == (1, 3, 0)
    assert parse_version("1.3") == (1, 3)
    with pytest.raises(SelfUpdateError):
        parse_version("abc")


def test_fetch_latest_release(monkeypatch):
    payload = {
        "tag_name": "v1.4.0",
        "html_url": "https://github.com/TheBestJie/WW-Mod-Manager/releases/tag/v1.4.0",
    }
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["request"] = request
        seen["timeout"] = timeout
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("wwmm.self_update.urlopen", fake_urlopen)

    info = fetch_latest_release(timeout=5)

    assert info == ReleaseInfo(tag="v1.4.0", version="1.4.0", url=payload["html_url"])
    assert seen["request"].get_header("User-agent") == f"wwmm/{__version__}"
    assert seen["timeout"] == 5


def test_fetch_raises_on_missing_release(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise OSError("HTTP Error 404: Not Found")

    monkeypatch.setattr("wwmm.self_update.urlopen", fake_urlopen)

    with pytest.raises(SelfUpdateError) as excinfo:
        fetch_latest_release()

    message = str(excinfo.value)
    assert "GitHub" in message
    assert "404" in message


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"not json", id="invalid-json"),
        pytest.param(json.dumps({"html_url": RELEASES_PAGE_URL}).encode("utf-8"), id="no-tag"),
    ],
)
def test_fetch_rejects_invalid_payload(monkeypatch, payload):
    monkeypatch.setattr("wwmm.self_update.urlopen", lambda *a, **k: _FakeResponse(payload))

    with pytest.raises(SelfUpdateError) as excinfo:
        fetch_latest_release()

    assert "GitHub" in str(excinfo.value)


@pytest.mark.parametrize(
    ("remote_tag", "expected_latest"),
    [
        pytest.param("v1.4.0", "1.4.0", id="newer"),
        pytest.param("v1.3.0", None, id="same"),
        pytest.param("v1.2.9", None, id="older"),
    ],
)
def test_check_for_update(monkeypatch, remote_tag, expected_latest):
    url = "https://example.invalid/releases/latest"
    calls = []

    def fake_fetch(url: str = "", timeout: float = 15) -> ReleaseInfo:
        calls.append((url, timeout))
        return ReleaseInfo(tag=remote_tag, version=remote_tag.lstrip("v"), url=RELEASES_PAGE_URL)

    monkeypatch.setattr("wwmm.self_update.fetch_latest_release", fake_fetch)

    result = check_for_update("1.3.0", url=url, timeout=5)

    assert calls == [(url, 5)]
    if expected_latest is None:
        assert result is None
    else:
        assert result == UpdateCheck(
            current="1.3.0",
            latest=ReleaseInfo(tag="v1.4.0", version=expected_latest, url=RELEASES_PAGE_URL),
        )


def test_find_repo_root_requires_git_clone(tmp_path):
    plain = tmp_path / "plain"
    _write_pyproject(plain, version="1.2.0")

    with pytest.raises(SelfUpdateError) as excinfo:
        find_repo_root(plain)

    message = str(excinfo.value)
    assert "git clone" in message
    assert RELEASES_PAGE_URL in message

    clone = tmp_path / "clone"
    _write_pyproject(clone, version="1.2.0")
    (clone / ".git").mkdir()

    assert find_repo_root(clone) == clone


def test_perform_self_update(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    calls = []
    _uv_present(monkeypatch)

    result = perform_self_update(root, runner=_recording_runner(calls))

    assert result == SelfUpdateResult(new_version="1.4.0", reinstalled=True)
    assert [command for command, _ in calls] == [
        ["git", "-C", str(root), "pull", "--ff-only"],
        ["uv", "tool", "install", "--editable", "--force", str(root)],
    ]
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True
    assert calls[0][1]["check"] is False


def test_perform_self_update_raises_on_git_failure(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    calls = []
    _uv_present(monkeypatch)
    runner = _recording_runner(calls, returncode=1, stderr="错误：本地改动会被覆盖（冲突）")

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    assert "git pull 失败" in str(excinfo.value)
    assert "冲突" in str(excinfo.value)


def test_perform_self_update_reports_install_failure(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    _uv_present(monkeypatch)
    returncodes = iter([0, 1])
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return _FakeCompleted(returncode=next(returncodes), stderr="error: 安装失败（依赖冲突）")

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    message = str(excinfo.value)
    assert calls[0][:3] == ["git", "-C", str(root)]
    assert len(calls) == 2
    assert "代码已更新" in message
    assert f"uv tool install -e {root}" in message
    assert "依赖冲突" in message
    assert "更新失败" not in message


def test_perform_self_update_without_uv(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    calls = []
    monkeypatch.setattr("wwmm.self_update.shutil.which", lambda name: None)

    result = perform_self_update(root, runner=_recording_runner(calls))

    assert result == SelfUpdateResult(new_version="1.4.0", reinstalled=False)
    assert [command for command, _ in calls] == [["git", "-C", str(root), "pull", "--ff-only"]]


def test_perform_refuses_when_dirty_pull_fails(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    calls = []
    _uv_present(monkeypatch)
    runner = _recording_runner(calls, returncode=1, stderr="error: Your local changes")

    with pytest.raises(SelfUpdateError):
        perform_self_update(root, runner=runner)

    assert [command for command, _ in calls] == [["git", "-C", str(root), "pull", "--ff-only"]]


def test_perform_self_update_bounds_subprocess_calls(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    calls = []
    _uv_present(monkeypatch)

    perform_self_update(root, runner=_recording_runner(calls))

    assert len(calls) == 2
    for _, kwargs in calls:
        assert kwargs["timeout"] == 60
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["text"] is True


def test_perform_self_update_reports_timeout(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    _uv_present(monkeypatch)

    def timeout_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 0))

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=timeout_runner)

    message = str(excinfo.value)
    assert "超时" in message
    assert "60" in message
    assert "git pull" in message


def test_perform_self_update_joins_both_streams(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    _uv_present(monkeypatch)
    runner = _recording_runner([], returncode=1, stdout="out", stderr="err")

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    assert "out\nerr" in str(excinfo.value)


def test_perform_self_update_truncates_long_error(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write_pyproject(root, version="1.4.0")
    _uv_present(monkeypatch)
    runner = _recording_runner([], returncode=1, stdout="x" * 500, stderr="y" * 500)

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    detail = str(excinfo.value).removeprefix("git pull 失败：")
    assert len(detail) <= 201
    assert detail.endswith("…")
