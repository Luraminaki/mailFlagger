import argparse
from pathlib import Path

import pytest

from mailflagger.cli import main, non_negative_int, parse_args
from mailflagger.state import load_seen_domains


def test_non_negative_int_accepts_zero_and_positive():
    assert non_negative_int('0') == 0
    assert non_negative_int('20') == 20


def test_non_negative_int_rejects_negative():
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int('-1')


def test_parse_args_rejects_negative_top():
    with pytest.raises(SystemExit):
        parse_args(['input.txt', '--top', '-1'])


def test_parse_args_rejects_no_blacklist_with_blacklist_out():
    with pytest.raises(SystemExit):
        parse_args(['input.txt', '--no-blacklist', '--blacklist-out', 'out.txt'])


def test_parse_args_rejects_split_caps_with_no_blacklist():
    with pytest.raises(SystemExit):
        parse_args(['input.txt', '--split-caps', '--no-blacklist'])


def test_parse_args_rejects_split_caps_with_blacklist_out():
    with pytest.raises(SystemExit):
        parse_args(['input.txt', '--split-caps', '--blacklist-out', 'out.txt'])


def test_parse_args_suspicious_tlds_with_no_values_is_empty_list_not_none():
    args = parse_args(['input.txt', '--suspicious-tlds'])
    assert args.suspicious_tlds == []


def test_version_flag_does_not_crash():
    with pytest.raises(SystemExit) as exc_info:
        parse_args(['--version'])
    assert exc_info.value.code == 0


def test_main_returns_error_for_missing_input_file(tmp_path: Path):
    missing = tmp_path / 'does-not-exist.txt'

    exit_code = main([str(missing), '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 1


def test_main_skips_report_and_blacklist_when_all_addresses_invalid(tmp_path: Path):
    input_file = tmp_path / 'senders.txt'
    input_file.write_text('not-an-email\nalso not one\n', encoding='utf-8')
    blacklist_out = tmp_path / 'existing_blacklist.txt'
    blacklist_out.write_text('@should-not-be-touched.com\n', encoding='utf-8')

    exit_code = main([str(input_file), '--blacklist-out', str(blacklist_out),
                       '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    assert blacklist_out.read_text(encoding='utf-8') == '@should-not-be-touched.com\n'


def test_main_end_to_end_writes_report_and_blacklist(tmp_path: Path):
    input_file = tmp_path / 'senders.txt'
    input_file.write_text('\n'.join(f'promo{i}@spam.xyz' for i in range(6)) + '\n', encoding='utf-8')
    blacklist_out = tmp_path / 'out' / 'blacklist.txt'

    exit_code = main([str(input_file), '--blacklist-out', str(blacklist_out), '--min-count', '5',
                       '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    assert blacklist_out.read_text(encoding='utf-8') == '@spam.xyz\n'


def test_main_excludes_major_providers_even_with_by_domain(tmp_path: Path):
    input_file = tmp_path / 'senders.txt'
    lines = [f'promo{i}@mail.yahoo.com' for i in range(6)] + [f'spammer{i}@spam.xyz' for i in range(5)]
    input_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    blacklist_out = tmp_path / 'blacklist.txt'

    exit_code = main([str(input_file), '--by-domain', '--min-count', '5',
                       '--blacklist-out', str(blacklist_out), '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    assert blacklist_out.read_text(encoding='utf-8') == '@spam.xyz\n'


def test_main_suspicious_tlds_empty_disables_check(tmp_path: Path):
    # spam.xyz would normally match a default suspicious TLD (weight 3). Passing
    # --suspicious-tlds with zero values should disable the check entirely, not fall back
    # to the defaults.
    input_file = tmp_path / 'senders.txt'
    input_file.write_text('\n'.join(f'user{i}@spam.xyz' for i in range(6)) + '\n', encoding='utf-8')
    blacklist_out = tmp_path / 'blacklist.txt'

    exit_code = main([str(input_file), '--suspicious-tlds', '--min-count', '100',
                       '--min-score', '1', '--blacklist-out', str(blacklist_out),
                       '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    assert blacklist_out.read_text(encoding='utf-8') == ''


def test_main_suspicious_tlds_case_insensitive_override(tmp_path: Path):
    # 6 addresses with no digit/length/generic-name triggers - only a matching suspicious_tld
    # (weight 3 each => total 18) can clear min-score=15. If --suspicious-tlds weren't
    # lowercased, 'COM' would never match the lowercase 'com' tld and this would stay empty.
    input_file = tmp_path / 'senders.txt'
    input_file.write_text('\n'.join(f'user{i}@spam.com' for i in range(6)) + '\n', encoding='utf-8')
    blacklist_out = tmp_path / 'blacklist.txt'

    exit_code = main([str(input_file), '--suspicious-tlds', 'COM', '--min-count', '100',
                       '--min-score', '15', '--blacklist-out', str(blacklist_out),
                       '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    assert blacklist_out.read_text(encoding='utf-8') == '@spam.com\n'


def test_main_csv_out_writes_domain_scores(tmp_path: Path):
    input_file = tmp_path / 'senders.txt'
    input_file.write_text('\n'.join(f'promo{i}@spam.xyz' for i in range(6)) + '\n', encoding='utf-8')
    csv_out = tmp_path / 'scores.csv'

    exit_code = main([str(input_file), '--csv-out', str(csv_out), '--no-blacklist',
                       '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    rows = csv_out.read_text(encoding='utf-8').splitlines()
    assert rows[0] == 'domain,count,total_score,avg_score,matched_patterns'
    assert rows[1].startswith('spam.xyz,6,')


def test_main_state_file_reports_only_new_domains_on_second_run(tmp_path: Path):
    state_file = tmp_path / 'state.txt'
    first_input = tmp_path / 'first.txt'
    first_input.write_text('a@old-domain.com\n', encoding='utf-8')
    second_input = tmp_path / 'second.txt'
    second_input.write_text('a@old-domain.com\nb@new-domain.com\n', encoding='utf-8')

    main([str(first_input), '--state-file', str(state_file), '--no-blacklist',
          '--log-file-stem', str(tmp_path / 'mf1')])
    assert load_seen_domains(state_file) == {'old-domain.com'}

    main([str(second_input), '--state-file', str(state_file), '--no-blacklist',
          '--log-file-stem', str(tmp_path / 'mf2')])
    assert load_seen_domains(state_file) == {'old-domain.com', 'new-domain.com'}


def test_main_split_caps_writes_four_files(tmp_path: Path):
    input_file = tmp_path / 'senders.txt'
    lines = [f'promo{i}@spam-a.xyz' for i in range(6)] + ['a@gmail.com', 'b@gmail.com',
                                                            'c@gmail.com', 'd@gmail.com', 'e@gmail.com']
    input_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    out_dir = tmp_path / 'banlists'

    exit_code = main([str(input_file), '--split-caps', '--min-count', '5',
                       '--primary-name', 'yahoo', '--primary-domain-cap', '1',
                       '--primary-address-cap', '1000', '--secondary-name', 'outlook',
                       '--split-out-dir', str(out_dir), '--log-file-stem', str(tmp_path / 'mf')])

    assert exit_code == 0
    assert (out_dir / 'yahoo_domains.txt').read_text(encoding='utf-8') == '@spam-a.xyz\n'
    yahoo_addresses = (out_dir / 'yahoo_addresses.txt').read_text(encoding='utf-8').splitlines()
    assert set(yahoo_addresses) == {'a@gmail.com', 'b@gmail.com', 'c@gmail.com', 'd@gmail.com', 'e@gmail.com'}
    assert (out_dir / 'outlook_domains.txt').read_text(encoding='utf-8') == '@spam-a.xyz\n'
    assert (out_dir / 'outlook_addresses.txt').read_text(encoding='utf-8') == ''
