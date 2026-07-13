#!/usr/bin/env python3
"""Tracks which root domains have been seen across previous runs, to report only new ones."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_seen_domains(path: Path) -> set[str]:
    """Loads the set of root domains recorded by a previous run.

    Args:
        path (Path): State file, one domain per line. A missing file is treated as empty.

    Returns:
        set[str]: Previously-seen root domains, or an empty set if `path` doesn't exist.
    """
    if not path.is_file():
        return set()
    with open(path, encoding='utf-8') as handle:
        return {line.strip().lower() for line in handle if line.strip()}


def save_seen_domains(path: Path, domains: set[str]) -> None:
    """Writes the full set of root domains seen so far, one per line, sorted.

    Creates `path`'s parent directory if it doesn't already exist.

    Args:
        path (Path): Destination state file (overwritten if it already exists).
        domains (set[str]): Domains to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(''.join(f'{domain}\n' for domain in sorted(domains)), encoding='utf-8')
    logger.info('Saved %d known domain(s) to state file %s', len(domains), path)
