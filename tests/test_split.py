from mailflagger.analyzer import analyze
from mailflagger.blacklist import DEFAULT_EXCLUDED_DOMAINS, suggest_blacklist
from mailflagger.scoring import score_domains
from mailflagger.split import split_for_caps


def test_split_for_caps_puts_top_domains_on_the_tight_provider():
    emails = [f'promo{i}@spam-a.xyz' for i in range(10)] + [f'promo{i}@spam-b.xyz' for i in range(8)]
    result = analyze(emails)
    scores = score_domains(result, by_root_domain=True)
    candidates = suggest_blacklist(scores, min_count=5)

    split = split_for_caps(result, candidates, DEFAULT_EXCLUDED_DOMAINS,
                            tight_domain_cap=1, tight_address_cap=1000)

    assert [d.domain for d in split.tight_domains] == ['spam-a.xyz']
    assert [d.domain for d in split.generous_domains] == ['spam-a.xyz', 'spam-b.xyz']
    # spam-b.xyz didn't make the tight domain cap, but still repeats -> its addresses go tight.
    assert all(address.endswith('@spam-b.xyz') for address in split.tight_addresses)
    assert len(split.tight_addresses) == 8


def test_split_for_caps_routes_freemail_and_oneoff_addresses_correctly():
    emails = ['a@gmail.com', 'b@gmail.com', 'c@gmail.com', 'onceoff@random-domain.example']
    result = analyze(emails)
    scores = score_domains(result, by_root_domain=True)
    candidates = suggest_blacklist(scores, min_count=100)  # nothing qualifies as a domain

    split = split_for_caps(result, candidates, DEFAULT_EXCLUDED_DOMAINS,
                            tight_domain_cap=3, tight_address_cap=1000)

    assert split.tight_domains == []
    assert set(split.tight_addresses) == {'a@gmail.com', 'b@gmail.com', 'c@gmail.com'}
    assert split.generous_addresses == ['onceoff@random-domain.example']


def test_split_for_caps_overflows_beyond_tight_address_cap_to_generous():
    emails = [f'a{i}@gmail.com' for i in range(5)]
    result = analyze(emails)
    scores = score_domains(result, by_root_domain=True)
    candidates = suggest_blacklist(scores, min_count=100)

    split = split_for_caps(result, candidates, DEFAULT_EXCLUDED_DOMAINS,
                            tight_domain_cap=3, tight_address_cap=2)

    assert len(split.tight_addresses) == 2
    assert len(split.generous_addresses) == 3
