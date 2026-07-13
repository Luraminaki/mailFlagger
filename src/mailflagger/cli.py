#!/usr/bin/env python3
"""Command-line entry point: analyze a sender list, report, and suggest a blacklist."""

import argparse
import heapq
import logging
from collections import Counter
from pathlib import Path

from mailflagger import __version__
from mailflagger.analyzer import analyze, load_emails
from mailflagger.blacklist import DEFAULT_EXCLUDED_DOMAINS, suggest_blacklist, write_addresses, write_blacklist
from mailflagger.export import write_domain_scores_csv
from mailflagger.logging_utils import configure_logging
from mailflagger.scoring import DEFAULT_SUSPICIOUS_TLDS, ScoringWeights, score_domains
from mailflagger.split import split_for_caps
from mailflagger.state import load_seen_domains, save_seen_domains

logger = logging.getLogger(__name__)

TOP_N_DEFAULT = 20


def non_negative_int(value: str) -> int:
    """Parses a CLI argument as a non-negative integer.

    Args:
        value (str): Raw argument string from argparse.

    Returns:
        int: The parsed value.

    Raises:
        argparse.ArgumentTypeError: If `value` is a valid integer but negative.
    """
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError(f'must be a non-negative integer, got {value!r}')
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for the mailflagger CLI.

    Args:
        argv (list[str] | None): Argument vector to parse, or `None` to use `sys.argv[1:]`.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog='mailflagger',
        description='Analyze a list of spammy sender addresses and suggest a domain-level blacklist.',
    )
    _ = parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    _ = parser.add_argument('input_file', type=Path, help='Text file with one sender address per line.')
    _ = parser.add_argument('--top', type=non_negative_int, default=TOP_N_DEFAULT,
                            help='Rows to show per report table (default: %(default)s).')
    _ = parser.add_argument('--min-count', type=int, default=5,
                            help='Minimum distinct senders on a domain to suggest blocking it (default: %(default)s).')
    _ = parser.add_argument('--min-score', type=int, default=None,
                            help='Also suggest domains whose total spam score reaches this value.')
    _ = parser.add_argument('--by-domain', action='store_true',
                            help='Score/blacklist by full domain instead of root domain '
                                 + '(e.g. mail.spam.com, not spam.com).')
    _ = parser.add_argument('--suspicious-tlds', nargs='*', default=None,
                            help='Override the default list of TLDs treated as suspicious. Pass with '
                                 + 'no values to disable the check entirely.')
    _ = parser.add_argument('--blacklist-out', type=Path, default=None,
                            help='Where to write the suggested blacklist '
                                 + '(default: <input_file stem>_blacklist.txt).')
    _ = parser.add_argument('--no-blacklist', action='store_true', help='Skip writing a blacklist file.')
    _ = parser.add_argument('--allow-major-providers', action='store_true',
                            help='Allow major freemail providers (gmail.com, hotmail.com, ...) to be '
                                 + 'suggested for blocking. Off by default: too many unrelated senders '
                                 + 'share those domains for a domain-wide block to be safe.')
    _ = parser.add_argument('--csv-out', type=Path, default=None,
                            help='Also write the full per-domain spaminess scores to this CSV file.')
    _ = parser.add_argument('--state-file', type=Path, default=None,
                            help='Track root domains seen across runs in this file, and report only '
                                 + 'those new since the last run.')
    _ = parser.add_argument('--split-caps', action='store_true',
                            help='Split the suggested blacklist between a tight-cap provider (few '
                                 + 'domain slots, e.g. Yahoo) and a generous-cap one (e.g. Outlook) '
                                 + 'instead of writing a single blacklist file. See --primary-* flags '
                                 + 'and --split-out-dir.')
    _ = parser.add_argument('--primary-name', default='primary',
                            help='Name of the tight-cap provider, used in output filenames '
                                 + '(default: %(default)s).')
    _ = parser.add_argument('--primary-domain-cap', type=non_negative_int, default=3,
                            help='Max domains the tight-cap provider allows (default: %(default)s).')
    _ = parser.add_argument('--primary-address-cap', type=non_negative_int, default=1000,
                            help='Max addresses the tight-cap provider allows (default: %(default)s).')
    _ = parser.add_argument('--secondary-name', default='secondary',
                            help='Name of the generous-cap provider, used in output filenames '
                                 + '(default: %(default)s).')
    _ = parser.add_argument('--split-out-dir', type=Path, default=None,
                            help='Directory to write the split ban lists into '
                                 + '(default: <input_file stem>_banlists).')
    _ = parser.add_argument('--log-file-stem', default='mailflagger',
                            help='Stem for the rotating log file (default: %(default)s).')
    _ = parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                            help='Root logging level (default: %(default)s).')

    args = parser.parse_args(argv)
    if args.no_blacklist and args.blacklist_out is not None:
        parser.error('--blacklist-out cannot be used together with --no-blacklist')
    if args.split_caps and (args.no_blacklist or args.blacklist_out is not None):
        parser.error('--split-caps cannot be used together with --no-blacklist or --blacklist-out')
    return args


def log_counter_table(title: str, counter: Counter, top: int, width: int = 30) -> None:
    """Logs a frequency table's top entries at INFO level.

    Args:
        title (str): Heading logged above the table.
        counter (Counter): Frequency table to render.
        top (int): Maximum number of rows to log.
        width (int): Column width used to left-align each key.
    """
    logger.info('=== %s ===', title)
    for key, count in counter.most_common(top):
        logger.info('%-*s %d', width, key, count)


def main(argv: list[str] | None = None) -> int:
    """Runs the mailflagger CLI: parse args, analyze, report, and optionally write a blacklist.

    Args:
        argv (list[str] | None): Argument vector to parse, or `None` to use `sys.argv[1:]`.

    Returns:
        int: Process exit code (`0` on success, `1` if the input file is missing).
    """
    args = parse_args(argv)
    configure_logging(log_file_stem=args.log_file_stem, level=args.log_level)

    if not args.input_file.is_file():
        logger.error('Input file not found: %s', args.input_file)
        return 1

    emails = load_emails(args.input_file)
    if not emails:
        logger.warning('No addresses found in %s', args.input_file)
        return 0

    result = analyze(emails)
    if not result.parsed:
        logger.warning('No valid addresses parsed from %s (all %d line(s) were malformed) - '
                       + 'skipping report and blacklist', args.input_file, result.total)
        return 0

    suspicious_tlds = (frozenset(t.lower() for t in args.suspicious_tlds)
                       if args.suspicious_tlds is not None else DEFAULT_SUSPICIOUS_TLDS)
    weights = ScoringWeights()
    domain_scores = score_domains(result, weights=weights, suspicious_tlds=suspicious_tlds,
                                   by_root_domain=not args.by_domain)

    logger.info('Total addresses: %d', result.total)
    logger.info('Invalid addresses skipped: %d', result.invalid)
    log_counter_table('Top domains', result.domain_counts, args.top)
    log_counter_table('Top root domains', result.root_domain_counts, args.top)
    log_counter_table('Top local parts (before @)', result.local_counts, args.top)
    log_counter_table('Top TLDs', result.tld_counts, args.top)

    if args.state_file is not None:
        previously_seen = load_seen_domains(args.state_file)
        current_domains = set(result.root_domain_counts)
        new_domains = sorted(current_domains - previously_seen)
        logger.info('=== New root domains since last run (%d) ===', len(new_domains))
        for domain in new_domains:
            logger.info('%s', domain)
        save_seen_domains(args.state_file, previously_seen | current_domains)

    ranked = heapq.nlargest(args.top, domain_scores.values(), key=lambda score: score.total_score)
    logger.info('=== Top domains by spaminess score ===')
    for score in ranked:
        patterns = ', '.join(f'{name}={count}' for name, count in score.matched_patterns.most_common())
        logger.info('%-30s count=%-4d total_score=%-5d avg=%.1f  %s',
                    score.domain, score.count, score.total_score, score.avg_score, patterns)

    exclude_domains = frozenset() if args.allow_major_providers else DEFAULT_EXCLUDED_DOMAINS

    if args.csv_out is not None:
        all_scores = sorted(domain_scores.values(), key=lambda score: score.total_score, reverse=True)
        write_domain_scores_csv(args.csv_out, all_scores)

    if args.split_caps:
        # The split's own bucketing logic collapses to registrable domains itself, so it needs
        # root-domain-keyed scores regardless of --by-domain.
        root_scores = domain_scores if not args.by_domain else score_domains(
            result, weights=weights, suspicious_tlds=suspicious_tlds, by_root_domain=True)
        all_candidates = suggest_blacklist(root_scores, min_count=args.min_count, min_score=args.min_score,
                                            exclude_domains=exclude_domains)
        split = split_for_caps(result, all_candidates, exclude_domains,
                                args.primary_domain_cap, args.primary_address_cap)
        out_dir = args.split_out_dir or args.input_file.with_name(f'{args.input_file.stem}_banlists')
        write_blacklist(out_dir / f'{args.primary_name}_domains.txt', split.tight_domains)
        write_addresses(out_dir / f'{args.primary_name}_addresses.txt', split.tight_addresses)
        write_blacklist(out_dir / f'{args.secondary_name}_domains.txt', split.generous_domains)
        write_addresses(out_dir / f'{args.secondary_name}_addresses.txt', split.generous_addresses)
        logger.info('Split ban lists written to %s (%s: %d domain(s)/%d address(es), '
                    + '%s: %d domain(s)/%d address(es))', out_dir,
                    args.primary_name, len(split.tight_domains), len(split.tight_addresses),
                    args.secondary_name, len(split.generous_domains), len(split.generous_addresses))
    elif not args.no_blacklist:
        blacklist = suggest_blacklist(domain_scores, min_count=args.min_count, min_score=args.min_score,
                                       exclude_domains=exclude_domains)
        out_path = args.blacklist_out or args.input_file.with_name(f'{args.input_file.stem}_blacklist.txt')
        write_blacklist(out_path, blacklist)
        logger.info('Suggested blacklist (%d domain(s)) written to %s', len(blacklist), out_path)

    return 0
