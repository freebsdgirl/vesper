"""Vesper package."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

__all__ = ["__version__"]

# Single source of truth is pyproject.toml. Read the installed distribution
# metadata so the version can't drift from the packaging metadata. Fall back to
# the literal for editable/source runs where the distribution is not installed
# (issue #88).
try:
    __version__ = _pkg_version("vesper")
except PackageNotFoundError:  # pragma: no cover - editable/source tree runs
    __version__ = "0.1.0"
