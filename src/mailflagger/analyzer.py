#!/usr/bin/env python3
"""Parsing and frequency analysis for a raw list of sender email addresses."""

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import tldextract
    # cache_dir=None: never touch disk. suffix_list_urls=(): never fetch over the network,
    # use only the frozen snapshot bundled with the package. include_psl_private_domains=True:
    # also recognize domain-hack suffixes like `uk.com` (sold by registrars as if it were a
    # ccTLD), not just ICANN-delegated TLDs.
    _PSL = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=(), include_psl_private_domains=True)
except ImportError:
    _PSL = None

# Second-level suffixes under which a domain's *third*-from-last label is the actual
# registrable name (e.g. `mail.example.co.uk` -> `example.co.uk`, not `co.uk`).
# Used as a fallback when the optional `publicsuffix2` dependency (`pip install
# mailflagger[psl]`) isn't installed. This is a curated subset of the real Public Suffix
# List (publicsuffix.org) covering the multi-part suffixes most commonly seen in practice.
MULTI_PART_SUFFIXES = frozenset({
    'co.uk', 'org.uk', 'ac.uk', 'gov.uk', 'net.uk', 'me.uk', 'ltd.uk', 'plc.uk', 'sch.uk',
    'com.au', 'net.au', 'org.au', 'edu.au', 'gov.au', 'id.au',
    'com.br', 'net.br', 'org.br', 'gov.br',
    'com.tr', 'org.tr', 'net.tr', 'gov.tr',
    'co.jp', 'ne.jp', 'or.jp', 'ad.jp', 'go.jp', 'ac.jp',
    'co.nz', 'org.nz', 'net.nz', 'govt.nz',
    'co.za', 'org.za', 'net.za', 'gov.za',
    'co.in', 'net.in', 'org.in', 'firm.in', 'gen.in', 'ind.in',
    'co.id', 'or.id', 'web.id',
    'co.kr', 'or.kr', 'ne.kr',
    'com.mx', 'org.mx', 'net.mx',
    'com.ar', 'org.ar', 'net.ar',
    'com.sg', 'org.sg', 'net.sg', 'edu.sg',
    'com.tw', 'org.tw', 'net.tw',
    'co.il', 'org.il', 'net.il',
    'com.pl', 'org.pl', 'net.pl',
    'com.cn', 'org.cn', 'net.cn', 'gov.cn',
    'com.hk', 'org.hk', 'net.hk',
    'uk.com', 'us.com', 'eu.com', 'de.com', 'gb.com', 'gb.net',
})


def normalize_email(raw: str) -> str:
    """Strips whitespace and lowercases a raw line from an input file.

    Args:
        raw (str): Raw line as read from the input file.

    Returns:
        str: The normalized address.
    """
    return raw.strip().lower()


def parse_email(email: str) -> tuple[str, str] | tuple[None, None]:
    """Splits an email into its local part and domain.

    Args:
        email (str): Normalized email address (see `normalize_email`).

    Returns:
        tuple[str, str] | tuple[None, None]: `(local_part, domain)`, or `(None, None)` if `email`
        is malformed (missing/multiple `@`, or an empty local part or domain).
    """
    if not email:
        return None, None
    parts = email.split('@')
    if len(parts) != 2:
        return None, None
    local, domain = parts
    if not local or not domain:
        return None, None
    return local, domain


def tld(domain: str) -> str:
    """Returns a domain's top-level label.

    Args:
        domain (str): Domain to inspect (e.g. `mail.spam.com` or a trailing-dot FQDN
            like `spam.com.`).

    Returns:
        str: The top-level label (e.g. `com`), or `domain` unchanged if it has no dot.
    """
    return domain.rstrip('.').rsplit('.', 1)[-1]


def root_domain(domain: str) -> str:
    """Collapses a domain to its registrable name, dropping any subdomains.

    If the optional `tldextract` dependency is installed (`pip install mailflagger[psl]`), the
    real Public Suffix List is used. Otherwise, this falls back to `MULTI_PART_SUFFIXES`:
    usually the last two labels (e.g. `mail.spam.com` -> `spam.com`), but for domains registered
    under a multi-part suffix (e.g. `mail.example.co.uk`), the last three labels are kept instead
    (`example.co.uk`) so unrelated senders sharing a country-code suffix like `co.uk` aren't
    merged together. A trailing dot (a technically valid absolute FQDN, e.g. `spam.com.`) is
    stripped first so it doesn't get misread as an extra, empty label.

    Args:
        domain (str): Domain to collapse (e.g. `mail.spam.com`).

    Returns:
        str: The registrable domain, or `domain` unchanged if it has fewer labels than needed.
    """
    domain = domain.rstrip('.')

    if _PSL is not None:
        via_psl = _PSL(domain).top_domain_under_public_suffix
        if via_psl:
            return via_psl

    parts = domain.split('.')
    if len(parts) < 2:
        return domain
    last_two = '.'.join(parts[-2:])
    if len(parts) >= 3 and last_two in MULTI_PART_SUFFIXES:
        return '.'.join(parts[-3:])
    return last_two


@dataclass
class ParsedEmail:
    """A successfully-parsed sender address.

    Attributes:
        local (str): The local part, before the `@`.
        domain (str): The domain, after the `@`.
    """
    local: str
    domain: str


@dataclass
class AnalysisResult:
    """Frequency tables produced by `analyze`.

    `invalid` and the four `Counter` properties are all derived on demand from `parsed`, so
    they can never drift out of sync with it.

    Attributes:
        total (int): Total number of addresses read, valid or not.
        parsed (list[ParsedEmail]): Every successfully-parsed address.
    """
    total: int = 0
    parsed: list[ParsedEmail] = field(default_factory=list)

    @property
    def invalid(self) -> int:
        """int: Number of addresses that failed to parse."""
        return self.total - len(self.parsed)

    @property
    def domain_counts(self) -> Counter:
        """Counter: Occurrences per full domain."""
        return Counter(p.domain for p in self.parsed)

    @property
    def root_domain_counts(self) -> Counter:
        """Counter: Occurrences per root domain (see `root_domain`)."""
        return Counter(root_domain(p.domain) for p in self.parsed)

    @property
    def local_counts(self) -> Counter:
        """Counter: Occurrences per local part."""
        return Counter(p.local for p in self.parsed)

    @property
    def tld_counts(self) -> Counter:
        """Counter: Occurrences per top-level domain (see `tld`)."""
        return Counter(tld(p.domain) for p in self.parsed)


def load_emails(filepath: Path) -> list[str]:
    """Reads a text file of one address per line, normalizing and dropping blanks/comments.

    Reads in binary and decodes with `utf-8-sig` (transparently dropping a leading BOM if
    present) so a stray non-UTF-8 byte anywhere in the file degrades that one line instead of
    aborting the whole run.

    Args:
        filepath (Path): Path to the input file.

    Returns:
        list[str]: Normalized, non-empty, non-comment lines, in file order.
    """
    emails = []
    decode_errors = 0
    with open(filepath, 'rb') as handle:
        for raw_line in handle:
            try:
                line = raw_line.decode('utf-8-sig')
            except UnicodeDecodeError:
                line = raw_line.decode('utf-8-sig', errors='replace')
                decode_errors += 1
            email = normalize_email(line)
            if email and not email.startswith('#'):
                emails.append(email)

    if decode_errors:
        logger.warning('%d line(s) in %s contained invalid UTF-8 bytes; decoded with replacement '
                       + 'characters', decode_errors, filepath)
    logger.info('Loaded %d candidate address(es) from %s', len(emails), filepath)
    return emails


def analyze(emails: list[str]) -> AnalysisResult:
    """Parses and tallies a list of raw addresses.

    Each address is re-normalized via `normalize_email` before parsing, so callers that pass
    already-normalized input (e.g. via `load_emails`) or raw/mixed-case input get the same result.

    Args:
        emails (list[str]): Addresses to analyze.

    Returns:
        AnalysisResult: Frequency tables and the list of successfully-parsed addresses.
    """
    result = AnalysisResult(total=len(emails))

    for email in emails:
        local, domain = parse_email(normalize_email(email))
        if not local or not domain:
            continue
        result.parsed.append(ParsedEmail(local=local, domain=domain))

    if result.invalid:
        logger.warning('Skipped %d malformed address(es)', result.invalid)

    return result
