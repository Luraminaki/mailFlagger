import csv
from pathlib import Path

from mailflagger.export import write_domain_scores_csv
from mailflagger.scoring import DomainScore


def test_write_domain_scores_csv_writes_expected_rows(tmp_path: Path):
    out_path = tmp_path / 'scores.csv'
    score = DomainScore(domain='spam.xyz', count=10, total_score=25)
    score.matched_patterns['suspicious_tld'] = 10

    write_domain_scores_csv(out_path, [score])

    with open(out_path, encoding='utf-8', newline='') as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == ['domain', 'count', 'total_score', 'avg_score', 'matched_patterns']
    assert rows[1] == ['spam.xyz', '10', '25', '2.50', 'suspicious_tld=10']


def test_write_domain_scores_csv_creates_missing_parent_directory(tmp_path: Path):
    out_path = tmp_path / 'nested' / 'scores.csv'

    write_domain_scores_csv(out_path, [])

    assert out_path.exists()
