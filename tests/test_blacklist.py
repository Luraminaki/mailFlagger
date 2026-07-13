from pathlib import Path

from mailflagger.blacklist import suggest_blacklist, write_blacklist
from mailflagger.scoring import DomainScore


def make_score(domain: str, count: int, total_score: int) -> DomainScore:
    return DomainScore(domain=domain, count=count, total_score=total_score)


def test_suggest_blacklist_filters_by_min_count():
    scores = {
        'spam.xyz': make_score('spam.xyz', count=10, total_score=5),
        'legit.com': make_score('legit.com', count=1, total_score=0),
    }

    blacklist = suggest_blacklist(scores, min_count=5)

    assert [entry.domain for entry in blacklist] == ['spam.xyz']


def test_suggest_blacklist_also_includes_high_score_domains():
    scores = {
        'sneaky.xyz': make_score('sneaky.xyz', count=1, total_score=50),
        'legit.com': make_score('legit.com', count=1, total_score=0),
    }

    blacklist = suggest_blacklist(scores, min_count=5, min_score=10)

    assert [entry.domain for entry in blacklist] == ['sneaky.xyz']


def test_suggest_blacklist_sorts_by_count_then_score():
    scores = {
        'a.xyz': make_score('a.xyz', count=10, total_score=5),
        'b.xyz': make_score('b.xyz', count=10, total_score=20),
    }

    blacklist = suggest_blacklist(scores, min_count=5)

    assert [entry.domain for entry in blacklist] == ['b.xyz', 'a.xyz']


def test_suggest_blacklist_excludes_major_providers_by_default():
    scores = {
        'gmail.com': make_score('gmail.com', count=50, total_score=100),
        'spam.xyz': make_score('spam.xyz', count=10, total_score=5),
    }

    blacklist = suggest_blacklist(scores, min_count=5)

    assert [entry.domain for entry in blacklist] == ['spam.xyz']


def test_suggest_blacklist_can_include_major_providers_via_empty_exclude_set():
    scores = {'gmail.com': make_score('gmail.com', count=50, total_score=100)}

    blacklist = suggest_blacklist(scores, min_count=5, exclude_domains=frozenset())

    assert [entry.domain for entry in blacklist] == ['gmail.com']


def test_suggest_blacklist_excludes_major_providers_even_when_keyed_by_full_subdomain():
    # Simulates --by-domain, where domain_scores keys are uncollapsed subdomains.
    scores = {
        'mail.yahoo.com': make_score('mail.yahoo.com', count=10, total_score=5),
        'spam.xyz': make_score('spam.xyz', count=10, total_score=5),
    }

    blacklist = suggest_blacklist(scores, min_count=5)

    assert [entry.domain for entry in blacklist] == ['spam.xyz']


def test_write_blacklist_writes_at_prefixed_domains(tmp_path: Path):
    out_path = tmp_path / 'blacklist.txt'
    domains = [make_score('spam.xyz', count=10, total_score=5)]

    write_blacklist(out_path, domains)

    assert out_path.read_text(encoding='utf-8') == '@spam.xyz\n'


def test_write_blacklist_creates_missing_parent_directory(tmp_path: Path):
    out_path = tmp_path / 'nested' / 'dir' / 'blacklist.txt'
    domains = [make_score('spam.xyz', count=10, total_score=5)]

    write_blacklist(out_path, domains)

    assert out_path.read_text(encoding='utf-8') == '@spam.xyz\n'
