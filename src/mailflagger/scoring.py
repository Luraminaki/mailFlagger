#!/usr/bin/env python3
"""Weighted 'spaminess' scoring for parsed addresses, aggregated per domain."""

import re
from collections import Counter
from dataclasses import dataclass, field

from mailflagger.analyzer import AnalysisResult, root_domain, tld

# TLDs repeatedly flagged in spam/abuse reports as disproportionately used for
# throwaway or spam registrations. Override with --suspicious-tlds.
DEFAULT_SUSPICIOUS_TLDS = frozenset({
    'xyz', 'top', 'click', 'link', 'work', 'rest', 'gq', 'tk', 'ml', 'cf', 'loan',
    'win', 'review', 'party', 'date', 'faith', 'accountant', 'science', 'stream',
    'bid', 'download', 'men', 'kim', 'icu', 'club', 'online', 'site', 'ru',
})

GENERIC_LOCAL_PART_RE = re.compile(
    r'\b(test|admin|info|support|no[.\-_]?reply|do[.\-_]?not[.\-_]?reply|promo|sales?|'
    + r'newsletter|marketing|notification|alerts?|accounts?|member)\b'
)
MANY_DIGITS_RE = re.compile(r'\d{4,}')
LONG_LOCAL_THRESHOLD = 20


@dataclass(frozen=True)
class ScoringWeights:
    """Points added per matched suspicious pattern when scoring one address.

    Attributes:
        suspicious_tld (int): Points added when the domain's TLD is in the suspicious set.
        many_digits (int): Points added when the local part has 4+ consecutive digits.
        long_local (int): Points added when the local part exceeds `LONG_LOCAL_THRESHOLD` characters.
        generic_name (int): Points added when the local part matches a generic/marketing pattern.
    """
    suspicious_tld: int = 3
    many_digits: int = 2
    long_local: int = 2
    generic_name: int = 1


_DEFAULT_WEIGHTS = ScoringWeights()


@dataclass
class DomainScore:
    """Aggregated spaminess score for a domain, across every address seen for it.

    Attributes:
        domain (str): The domain (or root domain) this score is for.
        count (int): Number of addresses seen for this domain.
        total_score (int): Sum of every address's individual score.
        matched_patterns (Counter): Occurrences per matched suspicious pattern name.
    """
    domain: str
    count: int = 0
    total_score: int = 0
    matched_patterns: Counter = field(default_factory=Counter)

    @property
    def avg_score(self) -> float:
        """float: Mean score per address, or `0.0` if `count` is zero."""
        return self.total_score / self.count if self.count else 0.0


def score_email(local: str, domain: str, weights: ScoringWeights,
                 suspicious_tlds: frozenset) -> tuple[int, list[str]]:
    """Scores one address against the suspicious-pattern heuristics.

    Args:
        local (str): The address's local part, before the `@`.
        domain (str): The address's domain, after the `@`.
        weights (ScoringWeights): Points awarded per matched pattern.
        suspicious_tlds (frozenset): TLDs treated as suspicious.

    Returns:
        tuple[int, list[str]]: The total score, and the list of matched pattern names.
    """
    matched = []
    score = 0

    if tld(domain) in suspicious_tlds:
        matched.append('suspicious_tld')
        score += weights.suspicious_tld

    if MANY_DIGITS_RE.search(local):
        matched.append('many_digits')
        score += weights.many_digits

    if len(local) > LONG_LOCAL_THRESHOLD:
        matched.append('long_local')
        score += weights.long_local

    if GENERIC_LOCAL_PART_RE.search(local):
        matched.append('generic_name')
        score += weights.generic_name

    return score, matched


def score_domains(result: AnalysisResult, weights: ScoringWeights = _DEFAULT_WEIGHTS,
                   suspicious_tlds: frozenset = DEFAULT_SUSPICIOUS_TLDS, by_root_domain: bool = True
                   ) -> dict[str, DomainScore]:
    """Scores every parsed address and aggregates the results per domain.

    Args:
        result (AnalysisResult): Parsed addresses to score (see `mailflagger.analyzer.analyze`).
        weights (ScoringWeights): Points awarded per matched pattern.
        suspicious_tlds (frozenset): TLDs treated as suspicious.
        by_root_domain (bool): If `True`, aggregate by root domain (e.g. `mail.spam.com` and
            `spam.com` both count toward `spam.com`). If `False`, aggregate by full domain.

    Returns:
        dict[str, DomainScore]: One `DomainScore` per domain key, keyed by that same domain.
    """
    scores: dict[str, DomainScore] = {}

    for parsed in result.parsed:
        key = root_domain(parsed.domain) if by_root_domain else parsed.domain
        domain_score = scores.get(key)
        if domain_score is None:
            domain_score = DomainScore(domain=key)
            scores[key] = domain_score

        email_score, matched = score_email(parsed.local, parsed.domain, weights, suspicious_tlds)

        domain_score.count += 1
        domain_score.total_score += email_score
        for pattern in matched:
            domain_score.matched_patterns[pattern] += 1

    return scores
