"""Tests for the GitHub release check and the self update core.

Everything here is hermetic: ``urlopen`` and ``subprocess`` are replaced by fakes,
nothing touches the network or the real repository.
"""

from __future__ import annotations

import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from wwmm import __version__
from wwmm.errors import SelfUpdateError
from wwmm.self_update import (
    ARCHIVE_URL_TEMPLATE,
    MODE_ARCHIVE,
    MODE_GIT,
    RELEASES_PAGE_URL,
    ReleaseInfo,
    SelfUpdateResult,
    UpdateCheck,
    check_for_update,
    download_release_archive,
    extract_release_archive,
    fetch_latest_release,
    find_repo_root,
    is_git_checkout,
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
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._payload[self._offset :]
            self._offset = len(self._payload)
            return chunk
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

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


def _git_install(tmp_path: Path, version: str = "1.4.0") -> Path:
    """A checkout that ``install.sh`` installed in editable mode."""
    root = tmp_path / "repo"
    _write_pyproject(root, version=version)
    (root / ".git").mkdir()
    return root


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


def test_find_repo_root_accepts_a_release_install(tmp_path):
    """A release archive extracted without .git is still a valid source install."""
    plain = tmp_path / "plain"
    _write_pyproject(plain, version="1.2.0")

    assert find_repo_root(plain) == plain
    assert is_git_checkout(plain) is False

    clone = tmp_path / "clone"
    _write_pyproject(clone, version="1.2.0")
    (clone / ".git").mkdir()

    assert find_repo_root(clone) == clone
    assert is_git_checkout(clone) is True


def test_find_repo_root_rejects_a_foreign_project(tmp_path):
    other = tmp_path / "other"
    _write_pyproject(other, version="1.2.0", name="not-wwmm")

    with pytest.raises(SelfUpdateError) as excinfo:
        find_repo_root(other)

    message = str(excinfo.value)
    assert "wwmm" in message
    assert RELEASES_PAGE_URL in message


def test_perform_self_update(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    calls = []
    _uv_present(monkeypatch)

    result = perform_self_update(root, runner=_recording_runner(calls))

    assert result == SelfUpdateResult(new_version="1.4.0", reinstalled=True, mode=MODE_GIT)
    assert [command for command, _ in calls] == [
        ["git", "-C", str(root), "pull", "--ff-only"],
        ["uv", "tool", "install", "--editable", "--force", str(root)],
    ]
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True
    assert calls[0][1]["check"] is False


def test_perform_self_update_raises_on_git_failure(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    calls = []
    _uv_present(monkeypatch)
    runner = _recording_runner(calls, returncode=1, stderr="错误：本地改动会被覆盖（冲突）")

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    assert "git pull 失败" in str(excinfo.value)
    assert "冲突" in str(excinfo.value)


def test_perform_self_update_reports_install_failure(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
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


def test_perform_self_update_reports_pull_timeout(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    _uv_present(monkeypatch)

    def runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 60, output="fatal: unable to access")

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    message = str(excinfo.value)
    assert "更新超时" in message
    assert "改用 git pull" in message
    assert "fatal: unable to access" in message
    assert "代码已更新" not in message


def test_perform_self_update_reports_install_timeout(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    _uv_present(monkeypatch)
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return _FakeCompleted()
        raise subprocess.TimeoutExpired(
            command, 60, output=b"error: failed to build \xe4\xbe\x9d\xe8\xb5\x96"
        )

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    message = str(excinfo.value)
    assert len(calls) == 2
    assert calls[0][:3] == ["git", "-C", str(root)]
    assert "代码已更新" in message
    assert "重装超时" in message
    assert "60" in message
    assert f"uv tool install -e {root}" in message
    assert "error: failed to build 依赖" in message  # TimeoutExpired.output is bytes
    assert "改用 git pull" not in message
    assert "更新失败" not in message


def test_perform_self_update_without_uv(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    calls = []
    monkeypatch.setattr("wwmm.self_update.shutil.which", lambda name: None)

    result = perform_self_update(root, runner=_recording_runner(calls))

    assert result == SelfUpdateResult(new_version="1.4.0", reinstalled=False)
    assert [command for command, _ in calls] == [["git", "-C", str(root), "pull", "--ff-only"]]


def test_perform_refuses_when_dirty_pull_fails(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    calls = []
    _uv_present(monkeypatch)
    runner = _recording_runner(calls, returncode=1, stderr="error: Your local changes")

    with pytest.raises(SelfUpdateError):
        perform_self_update(root, runner=runner)

    assert [command for command, _ in calls] == [["git", "-C", str(root), "pull", "--ff-only"]]


def test_perform_self_update_bounds_subprocess_calls(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    calls = []
    _uv_present(monkeypatch)

    perform_self_update(root, runner=_recording_runner(calls))

    assert len(calls) == 2
    for _, kwargs in calls:
        assert kwargs["timeout"] == 60
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["text"] is True


def test_perform_self_update_reports_timeout(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
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
    root = _git_install(tmp_path)
    _uv_present(monkeypatch)
    runner = _recording_runner([], returncode=1, stdout="out", stderr="err")

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    assert "out\nerr" in str(excinfo.value)


def test_perform_self_update_truncates_long_error(tmp_path, monkeypatch):
    root = _git_install(tmp_path)
    _uv_present(monkeypatch)
    runner = _recording_runner([], returncode=1, stdout="x" * 500, stderr="y" * 500)

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(root, runner=runner)

    detail = str(excinfo.value).removeprefix("git pull 失败：")
    assert len(detail) <= 201
    assert detail.endswith("…")


# ---------------------------------------------------------------------------
# release archive mode: installs unpacked from a downloaded release tarball
# ---------------------------------------------------------------------------

ARCHIVE_FILES = {
    "pyproject.toml": '[project]\nname = "ww-mod-manager"\nversion = "1.4.0"\n',
    "src/wwmm/__init__.py": '__version__ = "1.4.0"\n',
}


def _make_archive(path: Path, files: dict[str, str], *, top: str = "WW-Mod-Manager-1.4.0") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def _make_raw_tar(path: Path, members: list[tarfile.TarInfo]) -> Path:
    """A tarball with hand-built members, for the unsafe shapes GitHub never ships."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        for info in members:
            if info.isreg():
                tar.addfile(info, io.BytesIO(b"x" * info.size))
            else:
                tar.addfile(info)
    return path


def _release_install(tmp_path: Path, version: str = "1.3.0") -> Path:
    """A tree that looks like "downloaded the release and ran install.sh"."""
    root = tmp_path / f"WW-Mod-Manager-{version}"
    _write_pyproject(root, version=version)
    (root / "src" / "wwmm").mkdir(parents=True)
    (root / "src" / "wwmm" / "__init__.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    (root / ".venv").mkdir()
    (root / ".venv" / "marker").write_text("local venv", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "roster.json").write_text("local roster", encoding="utf-8")
    return root


def _latest_release(version: str = "1.4.0") -> ReleaseInfo:
    return ReleaseInfo(tag=f"v{version}", version=version, url=RELEASES_PAGE_URL)


def _run_archive_update(tmp_path, monkeypatch, extra_files: dict[str, str] | None = None):
    root = _release_install(tmp_path)
    calls: list = []
    _uv_present(monkeypatch)
    files = dict(ARCHIVE_FILES)
    files.update(extra_files or {})

    def fake_download(tag: str, dest_dir: Path) -> Path:
        assert tag == "v1.4.0"
        return _make_archive(Path(dest_dir) / "release.tar.gz", files)

    result = perform_self_update(
        root,
        runner=_recording_runner(calls),
        fetch_release=_latest_release,
        download=fake_download,
    )
    return root, calls, result


def test_archive_update_overwrites_sources_and_reinstalls(tmp_path, monkeypatch):
    root, calls, result = _run_archive_update(
        tmp_path, monkeypatch, {"src/wwmm/new_module.py": "NEW = 1\n"}
    )

    assert result.new_version == "1.4.0"
    assert result.mode == MODE_ARCHIVE
    assert result.reinstalled is True
    assert result.backup is not None
    assert "1.4.0" in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "1.4.0" in (root / "src" / "wwmm" / "__init__.py").read_text(encoding="utf-8")
    assert (root / "src" / "wwmm" / "new_module.py").is_file()
    assert [command for command, _ in calls] == [
        ["uv", "tool", "install", "--editable", "--force", str(root)]
    ]


def test_archive_update_keeps_local_venv_and_data(tmp_path, monkeypatch):
    root, _, _ = _run_archive_update(
        tmp_path,
        monkeypatch,
        {".venv/marker": "archive venv", "data/roster.json": "archive roster"},
    )

    assert (root / ".venv" / "marker").read_text(encoding="utf-8") == "local venv"
    assert (root / "data" / "roster.json").read_text(encoding="utf-8") == "local roster"


def test_archive_update_backs_up_the_previous_tree(tmp_path, monkeypatch):
    root, _, result = _run_archive_update(tmp_path, monkeypatch)

    backup = Path(result.backup)
    assert backup.is_dir()
    assert backup.parent == root.parent
    assert "1.3.0" in (backup / "pyproject.toml").read_text(encoding="utf-8")
    assert not (backup / ".venv").exists()


def test_archive_update_refuses_to_downgrade(tmp_path, monkeypatch):
    root = _release_install(tmp_path)
    _uv_present(monkeypatch)
    downloaded: list[str] = []

    def fake_download(tag: str, dest_dir: Path) -> Path:
        downloaded.append(tag)
        return _make_archive(Path(dest_dir) / "release.tar.gz", ARCHIVE_FILES)

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(
            root,
            runner=_recording_runner([]),
            fetch_release=lambda: _latest_release("1.3.0"),
            download=fake_download,
        )

    assert "已取消覆盖" in str(excinfo.value)
    assert downloaded == []
    assert "1.3.0" in (root / "pyproject.toml").read_text(encoding="utf-8")


def test_archive_update_reports_release_fetch_failure(tmp_path):
    root = _release_install(tmp_path)

    def boom() -> ReleaseInfo:
        raise SelfUpdateError("获取 GitHub release 失败：超时")

    with pytest.raises(SelfUpdateError, match="超时"):
        perform_self_update(root, runner=_recording_runner([]), fetch_release=boom)


def test_archive_update_reports_download_failure(tmp_path):
    root = _release_install(tmp_path)
    calls: list = []

    def boom(tag: str, dest_dir: Path) -> Path:
        raise SelfUpdateError("下载源码包失败：HTTP Error 404: Not Found")

    with pytest.raises(SelfUpdateError, match="下载源码包失败"):
        perform_self_update(
            root,
            runner=_recording_runner(calls),
            fetch_release=_latest_release,
            download=boom,
        )

    assert calls == []


def test_archive_update_reports_copy_failure_with_backup(tmp_path, monkeypatch):
    root = _release_install(tmp_path)
    calls: list = []
    _uv_present(monkeypatch)

    def exploding_sync(source, target) -> int:
        raise OSError("磁盘只读")

    monkeypatch.setattr("wwmm.self_update.sync_source_tree", exploding_sync)

    with pytest.raises(SelfUpdateError) as excinfo:
        perform_self_update(
            root,
            runner=_recording_runner(calls),
            fetch_release=_latest_release,
            download=lambda tag, dest: _make_archive(Path(dest) / "release.tar.gz", ARCHIVE_FILES),
        )

    message = str(excinfo.value)
    assert "覆盖安装目录失败" in message
    assert "磁盘只读" in message
    assert "备份" in message
    assert calls == []


def test_extract_rejects_parent_traversal(tmp_path):
    archive = _make_archive(tmp_path / "evil.tar.gz", {"../evil.txt": "pwned"})

    with pytest.raises(SelfUpdateError, match="非法路径"):
        extract_release_archive(archive, tmp_path / "out")

    assert not (tmp_path / "evil.txt").exists()


def test_extract_rejects_absolute_member(tmp_path):
    info = tarfile.TarInfo("/etc/wwmm-evil")
    info.size = 1
    archive = _make_raw_tar(tmp_path / "abs.tar.gz", [info])

    with pytest.raises(SelfUpdateError, match="非法路径"):
        extract_release_archive(archive, tmp_path / "out")


def test_extract_rejects_symlink_member(tmp_path):
    link = tarfile.TarInfo("WW-Mod-Manager-1.4.0/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    archive = _make_raw_tar(tmp_path / "link.tar.gz", [link])

    with pytest.raises(SelfUpdateError, match="不支持的条目"):
        extract_release_archive(archive, tmp_path / "out")


def test_extract_rejects_ambiguous_top_level(tmp_path):
    one = tarfile.TarInfo("WW-Mod-Manager-1.4.0/pyproject.toml")
    one.size = 1
    two = tarfile.TarInfo("other/pyproject.toml")
    two.size = 1
    archive = _make_raw_tar(tmp_path / "two-roots.tar.gz", [one, two])

    with pytest.raises(SelfUpdateError, match="顶层目录不唯一"):
        extract_release_archive(archive, tmp_path / "out")


def test_extract_returns_the_single_top_level_directory(tmp_path):
    archive = _make_archive(tmp_path / "ok.tar.gz", {"pyproject.toml": "x"})

    source = extract_release_archive(archive, tmp_path / "out")

    assert source.name == "WW-Mod-Manager-1.4.0"
    assert (source / "pyproject.toml").is_file()


def test_download_writes_the_archive(tmp_path, monkeypatch):
    payload = b"tarball-bytes" * 10
    seen: dict = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        return _FakeResponse(payload)

    monkeypatch.setattr("wwmm.self_update.urlopen", fake_urlopen)

    target = download_release_archive("v1.4.0", tmp_path / "dl")

    assert target.read_bytes() == payload
    assert seen["url"] == ARCHIVE_URL_TEMPLATE.format(tag="v1.4.0")


def test_download_rejects_a_crafted_tag(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("tag 没校验就发请求了")

    monkeypatch.setattr("wwmm.self_update.urlopen", no_network)

    with pytest.raises(SelfUpdateError, match="无效的 release tag"):
        download_release_archive("../../evil", tmp_path / "dl")


def test_download_reports_network_error(tmp_path, monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise OSError("HTTP Error 404: Not Found")

    monkeypatch.setattr("wwmm.self_update.urlopen", fake_urlopen)

    with pytest.raises(SelfUpdateError, match="下载源码包失败") as excinfo:
        download_release_archive("v1.4.0", tmp_path / "dl")

    assert "404" in str(excinfo.value)


def test_download_rejects_an_empty_body(tmp_path, monkeypatch):
    monkeypatch.setattr("wwmm.self_update.urlopen", lambda *a, **k: _FakeResponse(b""))

    with pytest.raises(SelfUpdateError, match="内容为空"):
        download_release_archive("v1.4.0", tmp_path / "dl")
