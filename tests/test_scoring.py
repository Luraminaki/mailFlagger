from mailflagger.analyzer import analyze
from mailflagger.scoring import DEFAULT_SUSPICIOUS_TLDS, ScoringWeights, score_domains, score_email

WEIGHTS = ScoringWeights()


def test_score_email_flags_suspicious_tld():
    score, matched = score_email('alice', 'spam.xyz', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
    assert 'suspicious_tld' in matched
    assert score == WEIGHTS.suspicious_tld


def test_score_email_flags_many_digits():
    score, matched = score_email('user12345', 'example.com', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
    assert 'many_digits' in matched
    assert score == WEIGHTS.many_digits


def test_score_email_flags_long_local():
    long_local = 'a' * 25
    score, matched = score_email(long_local, 'example.com', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
    assert 'long_local' in matched
    assert score == WEIGHTS.long_local


def test_score_email_flags_generic_name():
    score, matched = score_email('noreply', 'example.com', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
    assert 'generic_name' in matched
    assert score == WEIGHTS.generic_name


def test_score_email_flags_generic_name_variants():
    for local in ('donotreply', 'do-not-reply', 'do_not_reply', 'no.reply', 'no_reply',
                  'alerts', 'accounts', 'member'):
        _, matched = score_email(local, 'example.com', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
        assert 'generic_name' in matched, f'{local!r} should have matched generic_name'


def test_score_email_clean_address_has_no_matches():
    score, matched = score_email('jane.doe', 'example.com', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
    assert matched == []
    assert score == 0


def test_score_email_generic_name_requires_word_boundary():
    # "test"/"info" embedded in ordinary words should not match.
    for local in ('latest', 'information', 'remember'):
        _, matched = score_email(local, 'example.com', WEIGHTS, DEFAULT_SUSPICIOUS_TLDS)
        assert 'generic_name' not in matched, f'{local!r} should not have matched generic_name'


def test_score_domains_aggregates_by_root_domain():
    result = analyze(['promo1234@mail.spam.xyz', 'promo5678@spam.xyz'])

    scores = score_domains(result, by_root_domain=True)

    assert set(scores.keys()) == {'spam.xyz'}
    domain_score = scores['spam.xyz']
    assert domain_score.count == 2
    assert domain_score.matched_patterns['suspicious_tld'] == 2
    assert domain_score.matched_patterns['many_digits'] == 2


def test_score_domains_can_split_by_full_domain():
    result = analyze(['a@mail.spam.xyz', 'b@spam.xyz'])

    scores = score_domains(result, by_root_domain=False)

    assert set(scores.keys()) == {'mail.spam.xyz', 'spam.xyz'}
