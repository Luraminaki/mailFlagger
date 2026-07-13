"""mailflagger: analyze spam sender lists and suggest a domain-level blacklist."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('mailflagger')
except PackageNotFoundError:  # pragma: no cover - only hit when running from an uninstalled checkout
    __version__ = '0.0.0+unknown'
