"""Shared exception types for WWMM.

All modules import their exceptions from here to avoid circular imports.
"""


class WWMMError(Exception):
    """Base class for all WWMM errors."""


class LayoutError(WWMMError):
    """The Mods directory layout is missing or invalid."""


class RosterError(WWMMError):
    """The character roster is missing, corrupt or invalid."""


class ToggleError(WWMMError):
    """A mod folder could not be enabled or disabled."""


class RosterUpdateError(WWMMError):
    """The character roster could not be updated."""


class RosterDowngradeError(RosterUpdateError):
    """The remote roster is older than the local one."""


class RosterBuildError(WWMMError):
    """The roster could not be built from upstream data."""


class HotkeyEditError(WWMMError):
    """A hotkey expression was rejected or could not be written back to an ini."""
