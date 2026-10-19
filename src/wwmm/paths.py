"""XDG paths and Wine/Proton Mods directory detection."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir, user_data_dir, user_state_dir

APP_NAME = "wwmm"

WWMI_RELATIVE = Path("drive_c/Program Files/XXMI Launcher/WWMI/Mods")


def config_dir() -> Path:
    return Path(user_config_dir(APP_NAME, appauthor=False))


def data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, appauthor=False))


def state_dir() -> Path:
    return Path(user_state_dir(APP_NAME, appauthor=False))


def detect_mods_dirs(home: Path) -> list[Path]:
    """Return existing WWMI Mods directories in Wine/Proton prefixes."""
    home = Path(home)
    candidates = [
        home / ".proton" / "pfx" / WWMI_RELATIVE,
        home / ".wine" / WWMI_RELATIVE,
    ]
    for compatdata in (
        home / ".local" / "share" / "Steam" / "steamapps" / "compatdata",
        home / ".steam" / "steam" / "steamapps" / "compatdata",
    ):
        candidates.extend(sorted(compatdata.glob(f"*/pfx/{WWMI_RELATIVE}")))

    found: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        found.append(candidate)
    return found
