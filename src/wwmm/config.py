"""Persistent configuration stored as TOML."""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from wwmm.constants import DEFAULT_ROSTER_URL

log = logging.getLogger(__name__)


@dataclass
class Config:
    mods_dir: Path | None = None
    roster_url: str = DEFAULT_ROSTER_URL
    auto_create_folders: bool = True
    show_empty_characters: bool = True
    last_character: str | None = None


class ConfigStore:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = Path(config_dir)
        self.path = self.config_dir / "config.toml"

    def load(self) -> Config:
        if not self.path.exists():
            return Config()
        try:
            data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            log.warning("配置文件损坏，已移动到 %s: %s", self.path.with_name("config.toml.bad"), exc)
            try:
                os.replace(self.path, self.path.with_name("config.toml.bad"))
            except OSError:
                log.exception("无法移动损坏的配置文件")
            return Config()

        mods_dir = data.get("mods_dir")
        return Config(
            mods_dir=Path(mods_dir) if mods_dir else None,
            roster_url=str(data.get("roster_url", DEFAULT_ROSTER_URL)),
            auto_create_folders=bool(data.get("auto_create_folders", True)),
            show_empty_characters=bool(data.get("show_empty_characters", True)),
            last_character=data.get("last_character"),
        )

    def save(self, config: Config) -> None:
        data: dict[str, object] = {
            "roster_url": config.roster_url,
            "auto_create_folders": config.auto_create_folders,
            "show_empty_characters": config.show_empty_characters,
        }
        if config.mods_dir is not None:
            data["mods_dir"] = str(config.mods_dir)
        if config.last_character is not None:
            data["last_character"] = config.last_character

        self.config_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.config_dir / "config.toml.tmp"
        tmp_path.write_text(tomli_w.dumps(data), encoding="utf-8")
        os.replace(tmp_path, self.path)
