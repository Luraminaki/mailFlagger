#!/usr/bin/env python3
"""CSV export of per-domain spaminess scores, for opening in a spreadsheet."""

import csv
import logging
from pathlib import Path

from mailflagger.scoring import DomainScore

logger = logging.getLogger(__name__)


def write_domain_scores_csv(path: Path, domain_scores: list[DomainScore]) -> None:
    """Writes per-domain spaminess scores to a CSV file, one row per domain.

    Creates `path`'s parent directory if it doesn't already exist.

    Args:
        path (Path): Destination file, written as UTF-8 (overwritten if it already exists).
        domain_scores (list[DomainScore]): Domains to write, in the given order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['domain', 'count', 'total_score', 'avg_score', 'matched_patterns'])
        for score in domain_scores:
            patterns = '; '.join(f'{name}={count}' for name, count in score.matched_patterns.most_common())
            writer.writerow([score.domain, score.count, score.total_score, f'{score.avg_score:.2f}', patterns])
    logger.info('Wrote %d domain(s) to CSV file %s', len(domain_scores), path)
