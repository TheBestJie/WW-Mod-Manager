"""Check the latest GitHub release and update this install.

Two install shapes are supported:

* a git checkout (``git clone`` + ``install.sh``) is fast-forwarded in place;
* a release archive unpacked from the Releases page has no ``.git`` to pull
  from, so the new tag's source archive is downloaded and merged over the
  install directory after backing the previous tree up.

Both paths finish with ``uv tool install --editable --force`` so the entry point
picks up the new sources on the next start.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from wwmm import __version__
from wwmm.errors import SelfUpdateError

log = logging.getLogger(__name__)

REPO_SLUG = "TheBestJie/WW-Mod-Manager"
RELEASES_API_URL = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{REPO_SLUG}/releases/latest"
ARCHIVE_URL_TEMPLATE = f"https://github.com/{REPO_SLUG}/archive/refs/tags/{{tag}}.tar.gz"
PROJECT_NAME = "ww-mod-manager"
USER_AGENT = f"wwmm/{__version__}"
COMMAND_TIMEOUT = 60
ARCHIVE_TIMEOUT = 60
MAX_ERROR_DETAIL = 200
COPY_CHUNK = 256 * 1024

MODE_GIT = "git"
MODE_ARCHIVE = "archive"
TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Entries a release archive must never overwrite: local git metadata, the
# project venv, and anything the user generated (root level `data/`).
SKIP_TOP_LEVEL = frozenset(
    {
        ".git",
        ".venv",
        ".worktrees",
        ".superpowers",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "data",
    }
)
BACKUP_SKIP = (
    ".git",
    ".venv",
    ".worktrees",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".ruff_cache",
)


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: str
    url: str


@dataclass(frozen=True)
class UpdateCheck:
    current: str
    latest: ReleaseInfo


@dataclass(frozen=True)
class SelfUpdateResult:
    new_version: str
    reinstalled: bool
    mode: str = MODE_GIT
    backup: str | None = None


def parse_version(text: str) -> tuple[int, ...]:
    cleaned = text.strip().lstrip("vV")
    try:
        return tuple(int(part) for part in cleaned.split("."))
    except ValueError as exc:
        raise SelfUpdateError(f"无效版本号：{text}") from exc


def _is_newer(remote: tuple[int, ...], current: tuple[int, ...]) -> bool:
    width = max(len(remote), len(current))
    remote_padded = remote + (0,) * (width - len(remote))
    current_padded = current + (0,) * (width - len(current))
    return remote_padded > current_padded


def fetch_latest_release(url: str = RELEASES_API_URL, timeout: float = 15) -> ReleaseInfo:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except OSError as exc:
        raise SelfUpdateError(f"获取 GitHub release 失败：{exc}") from exc

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SelfUpdateError("GitHub release 响应格式无效") from exc

    if not isinstance(data, dict):
        raise SelfUpdateError("GitHub release 响应格式无效")
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not tag.lstrip("vV"):
        raise SelfUpdateError("GitHub release 响应格式无效")
    html_url = data.get("html_url")
    return ReleaseInfo(
        tag=tag,
        version=tag.lstrip("vV"),
        url=html_url if isinstance(html_url, str) and html_url else RELEASES_PAGE_URL,
    )


def check_for_update(
    current: str = __version__,
    url: str = RELEASES_API_URL,
    timeout: float = 15,
) -> UpdateCheck | None:
    latest = fetch_latest_release(url=url, timeout=timeout)
    if not _is_newer(parse_version(latest.version), parse_version(current)):
        return None
    return UpdateCheck(current=current, latest=latest)


def _read_project(pyproject: Path) -> dict:
    try:
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    project = data.get("project")
    return project if isinstance(project, dict) else {}


def find_repo_root(start: Path | None = None) -> Path:
    """Locate the source tree this install runs from, git checkout or not."""
    current = Path(start) if start is not None else Path(__file__).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        if _read_project(pyproject).get("name") != PROJECT_NAME:
            continue
        return candidate
    raise SelfUpdateError(
        "未找到 wwmm 的源码安装目录（需要 git clone + install.sh，"
        "或从 Releases 下载源码包解压后运行 install.sh），"
        f"请手动更新：{RELEASES_PAGE_URL}"
    )


def is_git_checkout(repo_root: Path) -> bool:
    """A release archive has no ``.git``; a cloned install does."""
    return (Path(repo_root) / ".git").exists()


def _read_version(repo_root: Path) -> str:
    pyproject = repo_root / "pyproject.toml"
    version = _read_project(pyproject).get("version")
    if not isinstance(version, str) or not version:
        raise SelfUpdateError(f"无法从 {pyproject} 读取 project.version")
    return version


def _detail(stdout: bytes | str | None, stderr: bytes | str | None) -> str:
    """Join whatever the subprocess left behind; TimeoutExpired hands back bytes."""
    parts = []
    for part in (stdout, stderr):
        if isinstance(part, bytes):
            part = part.decode("utf-8", errors="replace")
        if part and part.strip():
            parts.append(part.strip())
    detail = "\n".join(parts)
    if len(detail) > MAX_ERROR_DETAIL:
        return f"{detail[:MAX_ERROR_DETAIL]}…"
    return detail


def _summarize(stdout: bytes | str | None, stderr: bytes | str | None) -> str:
    return _detail(stdout, stderr) or "未知错误"


def _run_command(
    runner, command: list[str], *, timeout_message: str
) -> subprocess.CompletedProcess:
    try:
        return runner(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # Keep whatever the command printed before it was killed.
        detail = _detail(exc.output, exc.stderr)
        suffix = f"：{detail}" if detail else ""
        raise SelfUpdateError(f"{timeout_message}{suffix}") from exc


def _validate_tag(tag: str) -> str:
    if not isinstance(tag, str) or not TAG_PATTERN.fullmatch(tag):
        raise SelfUpdateError(f"无效的 release tag：{tag}")
    return tag


def download_release_archive(tag: str, dest_dir: Path, timeout: float = ARCHIVE_TIMEOUT) -> Path:
    """Download the source archive GitHub builds for ``tag`` into ``dest_dir``."""
    _validate_tag(tag)
    url = ARCHIVE_URL_TEMPLATE.format(tag=tag)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{PROJECT_NAME}-{tag.lstrip('vV')}.tar.gz"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response, target.open("wb") as handle:
            shutil.copyfileobj(response, handle, COPY_CHUNK)
    except OSError as exc:
        raise SelfUpdateError(f"下载源码包失败：{exc}") from exc
    if target.stat().st_size == 0:
        raise SelfUpdateError("下载源码包失败：内容为空")
    return target


def _validate_member(member: tarfile.TarInfo) -> None:
    name = member.name.replace("\\", "/")
    parts = [part for part in name.split("/") if part not in ("", ".")]
    if name.startswith("/") or ".." in parts:
        raise SelfUpdateError(f"源码包包含非法路径：{member.name}")
    if not (member.isfile() or member.isdir()):
        raise SelfUpdateError(f"源码包包含不支持的条目：{member.name}")


def extract_release_archive(archive: Path, dest_dir: Path) -> Path:
    """Safely unpack ``archive`` and return its single top-level directory."""
    dest_dir = Path(dest_dir)
    if dest_dir.exists() and any(dest_dir.iterdir()):
        raise SelfUpdateError(f"解压目标目录不是空目录：{dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                _validate_member(member)
            # filter="data" rejects links and device nodes on top of the
            # checks above; older 3.11 patch releases have no filter argument.
            try:
                tar.extractall(dest_dir, filter="data")
            except TypeError:  # pragma: no cover - Python < 3.11.4 only
                tar.extractall(dest_dir)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise SelfUpdateError(f"解压源码包失败：{exc}") from exc

    entries = [entry for entry in dest_dir.iterdir()]
    if len(entries) != 1:
        raise SelfUpdateError("解压源码包失败：顶层目录不唯一")
    source = entries[0]
    if not source.is_dir():
        raise SelfUpdateError("解压源码包失败：顶层条目不是目录")
    return source


def sync_source_tree(source: Path, target: Path) -> int:
    """Copy new files over ``target`` without ever deleting anything."""
    source, target = Path(source), Path(target)
    copied = 0
    for entry in sorted(source.iterdir()):
        if entry.name in SKIP_TOP_LEVEL:
            log.info("跳过本地条目：%s", entry.name)
            continue
        destination = target / entry.name
        if entry.is_dir():
            shutil.copytree(
                entry,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        elif entry.is_file():
            shutil.copy2(entry, destination)
        else:
            log.warning("跳过非常规文件：%s", entry)
            continue
        copied += 1
    return copied


def backup_install(repo_root: Path, version: str) -> Path | None:
    """Copy the current tree next to itself so a bad update can be rolled back."""
    repo_root = Path(repo_root)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = repo_root.parent / f"{repo_root.name}.bak-v{version}-{stamp}"
    suffix = 1
    while backup.exists():
        suffix += 1
        backup = repo_root.parent / f"{repo_root.name}.bak-v{version}-{stamp}-{suffix}"
    try:
        shutil.copytree(repo_root, backup, ignore=shutil.ignore_patterns(*BACKUP_SKIP))
    except OSError as exc:
        log.warning("备份旧安装失败：%s", exc)
        return None
    return backup


def _archive_failure(exc: OSError, backup: Path | None) -> str:
    message = f"覆盖安装目录失败：{exc}"
    if backup is not None:
        message += f"；旧文件备份在 {backup}"
    return message


def _archive_update(
    repo_root: Path,
    previous: str,
    *,
    fetch_release,
    download,
    extract,
) -> Path | None:
    release = fetch_release()
    if not _is_newer(parse_version(release.version), parse_version(previous)):
        raise SelfUpdateError(
            f"当前 v{previous} 不早于最新 release v{release.version}，已取消覆盖"
            f"（如需重装请手动运行 uv tool install -e {repo_root}）"
        )
    with tempfile.TemporaryDirectory(prefix="wwmm-update-") as workspace:
        archive = download(release.tag, Path(workspace))
        source = extract(archive, Path(workspace) / "extracted")
        backup = backup_install(repo_root, previous)
        try:
            sync_source_tree(source, repo_root)
        except OSError as exc:
            raise SelfUpdateError(_archive_failure(exc, backup)) from exc
    return backup


def _reinstall(repo_root: Path, runner) -> bool:
    if not shutil.which("uv"):
        log.info("未找到 uv，跳过重新安装，使用已安装的入口")
        return False
    install_command = ["uv", "tool", "install", "--editable", "--force", str(repo_root)]
    installed = _run_command(
        runner,
        install_command,
        timeout_message=(
            "代码已更新，但重装超时"
            f"（{COMMAND_TIMEOUT} 秒），请手动运行 uv tool install -e {repo_root}"
        ),
    )
    if installed.returncode != 0:
        # The source update already succeeded, so the wording must not claim the
        # update failed as a whole: only the reinstall did.
        raise SelfUpdateError(
            "代码已更新，但重装失败，请手动运行 "
            f"uv tool install -e {repo_root}："
            f"{_summarize(installed.stdout, installed.stderr)}"
        )
    return True


def perform_self_update(
    repo_root: Path,
    runner=subprocess.run,
    *,
    fetch_release=None,
    download=None,
    extract=None,
) -> SelfUpdateResult:
    repo_root = Path(repo_root)
    previous = _read_version(repo_root)
    backup: Path | None = None
    if is_git_checkout(repo_root):
        mode = MODE_GIT
        pulled = _run_command(
            runner,
            ["git", "-C", str(repo_root), "pull", "--ff-only"],
            timeout_message=f"更新超时（{COMMAND_TIMEOUT} 秒），请检查网络或改用 git pull",
        )
        if pulled.returncode != 0:
            raise SelfUpdateError(f"git pull 失败：{_summarize(pulled.stdout, pulled.stderr)}")
    else:
        mode = MODE_ARCHIVE
        backup = _archive_update(
            repo_root,
            previous,
            fetch_release=fetch_release or fetch_latest_release,
            download=download or download_release_archive,
            extract=extract or extract_release_archive,
        )

    reinstalled = _reinstall(repo_root, runner)
    return SelfUpdateResult(
        new_version=_read_version(repo_root),
        reinstalled=reinstalled,
        mode=mode,
        backup=str(backup) if backup is not None else None,
    )
