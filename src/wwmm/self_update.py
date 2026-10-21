"""Check the latest GitHub release and update an editable (git clone) install."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from wwmm import __version__
from wwmm.errors import SelfUpdateError

log = logging.getLogger(__name__)

RELEASES_API_URL = "https://api.github.com/repos/TheBestJie/WW-Mod-Manager/releases/latest"
RELEASES_PAGE_URL = "https://github.com/TheBestJie/WW-Mod-Manager/releases/latest"
PROJECT_NAME = "ww-mod-manager"
USER_AGENT = f"wwmm/{__version__}"
COMMAND_TIMEOUT = 60
MAX_ERROR_DETAIL = 200


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
    current = Path(start) if start is not None else Path(__file__).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        if _read_project(pyproject).get("name") != PROJECT_NAME:
            continue
        if not (candidate / ".git").exists():
            continue
        return candidate
    raise SelfUpdateError(
        "未找到可自动更新的 git 仓库（需要 git clone + install.sh 安装），"
        f"请手动更新：{RELEASES_PAGE_URL}"
    )


def _read_version(repo_root: Path) -> str:
    pyproject = repo_root / "pyproject.toml"
    version = _read_project(pyproject).get("version")
    if not isinstance(version, str) or not version:
        raise SelfUpdateError(f"无法从 {pyproject} 读取 project.version")
    return version


def _summarize(stdout: str | None, stderr: str | None) -> str:
    parts = [part.strip() for part in (stdout, stderr) if part and part.strip()]
    detail = "\n".join(parts) or "未知错误"
    if len(detail) > MAX_ERROR_DETAIL:
        return f"{detail[:MAX_ERROR_DETAIL]}…"
    return detail


def _run_command(runner, command: list[str]) -> subprocess.CompletedProcess:
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
        raise SelfUpdateError(
            f"更新超时（{COMMAND_TIMEOUT} 秒），请检查网络或改用 git pull"
        ) from exc


def perform_self_update(repo_root: Path, runner=subprocess.run) -> SelfUpdateResult:
    repo_root = Path(repo_root)
    pull_command = ["git", "-C", str(repo_root), "pull", "--ff-only"]
    pulled = _run_command(runner, pull_command)
    if pulled.returncode != 0:
        raise SelfUpdateError(f"git pull 失败：{_summarize(pulled.stdout, pulled.stderr)}")

    reinstalled = False
    if shutil.which("uv"):
        install_command = ["uv", "tool", "install", "--editable", "--force", str(repo_root)]
        installed = _run_command(runner, install_command)
        if installed.returncode == 0:
            reinstalled = True
        else:
            log.warning(
                "uv tool install 失败，保留现有安装：%s",
                _summarize(installed.stdout, installed.stderr),
            )
    else:
        log.info("未找到 uv，跳过重新安装，使用已安装的入口")

    return SelfUpdateResult(new_version=_read_version(repo_root), reinstalled=reinstalled)
