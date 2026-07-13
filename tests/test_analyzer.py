from pathlib import Path

import pytest

from mailflagger.analyzer import analyze, load_emails, normalize_email, parse_email, root_domain, tld


def test_normalize_email_strips_and_lowercases():
    assert normalize_email('  Promo2024@Spam-Domain.XYZ  \n') == 'promo2024@spam-domain.xyz'


def test_parse_email_valid():
    assert parse_email('user@example.com') == ('user', 'example.com')


def test_parse_email_missing_at():
    assert parse_email('not-an-email') == (None, None)


def test_parse_email_multiple_at():
    assert parse_email('a@b@c.com') == (None, None)


def test_parse_email_empty_parts():
    assert parse_email('@example.com') == (None, None)
    assert parse_email('user@') == (None, None)


def test_root_domain_collapses_subdomains():
    assert root_domain('mail.spam.com') == 'spam.com'
    assert root_domain('spam.com') == 'spam.com'
    assert root_domain('localhost') == 'localhost'


def test_root_domain_keeps_registrable_name_under_multi_part_suffix():
    assert root_domain('mail.example.co.uk') == 'example.co.uk'
    assert root_domain('a.b.spam.com.br') == 'spam.com.br'
    assert root_domain('random123.uk.com') == 'random123.uk.com'


def test_root_domain_bare_multi_part_suffix_is_unchanged():
    assert root_domain('co.uk') == 'co.uk'


def test_root_domain_distinguishes_unrelated_senders_under_same_suffix():
    assert root_domain('spammer.co.uk') != root_domain('legit-company.co.uk')


def test_root_domain_strips_trailing_dot_and_does_not_merge_unrelated_domains():
    assert root_domain('example.com.') == 'example.com'
    assert root_domain('another-example.com.') == 'another-example.com'
    assert root_domain('example.com.') != root_domain('another-example.com.')


def test_tld_returns_last_label():
    assert tld('mail.spam.com') == 'com'
    assert tld('spam.xyz') == 'xyz'


def test_tld_strips_trailing_dot():
    assert tld('spam.com.') == 'com'


def test_load_emails_skips_blanks_and_comments(tmp_path: Path):
    input_file = tmp_path / 'emails.txt'
    input_file.write_text('user@example.com\n\n# a comment\nOTHER@Example.COM\n', encoding='utf-8')

    emails = load_emails(input_file)

    assert emails == ['user@example.com', 'other@example.com']


def test_load_emails_strips_utf8_bom(tmp_path: Path):
    input_file = tmp_path / 'emails.txt'
    input_file.write_bytes('﻿user@example.com\n'.encode())

    emails = load_emails(input_file)

    assert emails == ['user@example.com']


def test_load_emails_tolerates_invalid_utf8_bytes(tmp_path: Path):
    input_file = tmp_path / 'emails.txt'
    input_file.write_bytes(b'good@example.com\n# comment with a bad byte \xe9 here\nother@example.com\n')

    emails = load_emails(input_file)

    assert emails == ['good@example.com', 'other@example.com']


def test_analyze_tallies_domains_locals_and_tlds():
    emails = ['a@spam.xyz', 'b@spam.xyz', 'c@mail.spam.xyz', 'not-an-email']

    result = analyze(emails)

    assert result.total == 4
    assert result.invalid == 1
    assert result.domain_counts['spam.xyz'] == 2
    assert result.domain_counts['mail.spam.xyz'] == 1
    assert result.root_domain_counts['spam.xyz'] == 3
    assert result.tld_counts['xyz'] == 3
    assert result.local_counts['a'] == 1


def test_analyze_does_not_merge_unrelated_domains_under_a_multi_part_suffix():
    emails = ['a@one-company.co.uk', 'b@another-company.co.uk']

    result = analyze(emails)

    assert result.root_domain_counts['one-company.co.uk'] == 1
    assert result.root_domain_counts['another-company.co.uk'] == 1
    assert 'co.uk' not in result.root_domain_counts


def test_analyze_normalizes_input_regardless_of_caller():
    result = analyze(['  A@Spam.COM  '])

    assert result.parsed[0].local == 'a'
    assert result.parsed[0].domain == 'spam.com'


def test_root_domain_uses_real_public_suffix_list_when_installed():
    pytest.importorskip('tldextract')
    # kobe.jp is a PSL *wildcard* rule (`*.kobe.jp` is itself a suffix, needing one more label
    # for a registrable domain) - not in our curated MULTI_PART_SUFFIXES fallback list, so this
    # is only correct if the real PSL (via the optional `tldextract` dependency) is consulted.
    assert root_domain('mail.example.kobe.jp') == 'mail.example.kobe.jp'
