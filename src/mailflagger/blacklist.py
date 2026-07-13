#!/usr/bin/env python3
"""Turn per-domain spam scores into a ready-to-use blacklist of domains."""

import logging
from pathlib import Path

from mailflagger.analyzer import root_domain
from mailflagger.scoring import DomainScore

logger = logging.getLogger(__name__)

# Major freemail/webmail providers (including common regional variants), excluded from
# suggestions by default: they're shared by far too many unrelated senders for a domain-wide
# block to be safe, no matter how many spammy addresses on them get reported. Individually
# blocking/reporting-as-junk the offending address is the only sound option here. This list is
# intentionally all-or-nothing (via `exclude_domains`/--allow-major-providers) rather than
# partially customizable - it's a safety net, not a tuning knob.
DEFAULT_EXCLUDED_DOMAINS = frozenset({
    'gmail.com', 'googlemail.com',
    'outlook.com', 'outlook.fr', 'outlook.de', 'outlook.it', 'outlook.es', 'outlook.co.uk',
    'hotmail.com', 'hotmail.fr', 'hotmail.de', 'hotmail.it', 'hotmail.es', 'hotmail.co.uk',
    'live.com', 'live.fr', 'live.de', 'live.it', 'live.co.uk', 'msn.com',
    'yahoo.com', 'yahoo.co.uk', 'yahoo.fr', 'yahoo.de', 'yahoo.it', 'yahoo.es', 'yahoo.ca',
    'yahoo.com.br', 'ymail.com', 'rocketmail.com',
    'icloud.com', 'me.com', 'mac.com',
    'aol.com', 'protonmail.com', 'proton.me', 'gmx.com', 'gmx.net', 'gmx.de', 'mail.com',
    'zoho.com', 'fastmail.com', 'yandex.com', 'yandex.ru', 'mail.ru', 'qq.com', '163.com', '126.com',
})


def suggest_blacklist(domain_scores: dict[str, DomainScore], min_count: int = 5,
                       min_score: int | None = None,
                       exclude_domains: frozenset = DEFAULT_EXCLUDED_DOMAINS) -> list[DomainScore]:
    """Ranks domains worth blocking: enough distinct senders and/or a high spam score.

    A domain qualifies if it was seen at least `min_count` times, OR (when `min_score` is set)
    its total score reaches that threshold. This mirrors the "block domains, not individual
    addresses" approach that avoids a mail provider's per-address blacklist cap. A domain is
    excluded if its *registrable* domain (see `root_domain`) is in `exclude_domains`, regardless
    of count or score and regardless of whether `domain_scores` itself is keyed by root or full
    domain - so a subdomain of an excluded provider (e.g. `mail.yahoo.com`) is caught too.

    Args:
        domain_scores (dict[str, DomainScore]): Per-domain scores from `mailflagger.scoring.score_domains`.
        min_count (int): Minimum distinct senders on a domain to suggest blocking it.
        min_score (int | None): Also suggest domains whose total score reaches this value, or
            `None` to disable the score-based criterion.
        exclude_domains (frozenset): Domains never suggested, e.g. major freemail providers
            (see `DEFAULT_EXCLUDED_DOMAINS`). Pass `frozenset()` to disable this safeguard.

    Returns:
        list[DomainScore]: Qualifying domains, sorted by `(count, total_score)` descending.
    """
    candidates = [
        score for score in domain_scores.values()
        if root_domain(score.domain) not in exclude_domains
        and (score.count >= min_count or (min_score is not None and score.total_score >= min_score))
    ]
    candidates.sort(key=lambda score: (score.count, score.total_score), reverse=True)
    return candidates


def write_blacklist(path: Path, domains: list[DomainScore]) -> None:
    """Writes one '@domain' per line, ready to paste into a mail client's block list.

    Creates `path`'s parent directory if it doesn't already exist.

    Args:
        path (Path): Destination file, written as UTF-8 (overwritten if it already exists).
        domains (list[DomainScore]): Domains to write, in the given order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(''.join(f'@{score.domain}\n' for score in domains), encoding='utf-8')
    logger.info('Wrote %d domain(s) to blacklist file %s', len(domains), path)


def write_addresses(path: Path, addresses: list[str]) -> None:
    """Writes one address per line (no '@' prefix), ready for a mail client's address block list.

    Creates `path`'s parent directory if it doesn't already exist.

    Args:
        path (Path): Destination file, written as UTF-8 (overwritten if it already exists).
        addresses (list[str]): Addresses to write, in the given order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(''.join(f'{address}\n' for address in addresses), encoding='utf-8')
    logger.info('Wrote %d address(es) to %s', len(addresses), path)
