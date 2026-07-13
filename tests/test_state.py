from pathlib import Path

from mailflagger.state import load_seen_domains, save_seen_domains


def test_load_seen_domains_missing_file_returns_empty_set(tmp_path: Path):
    assert load_seen_domains(tmp_path / 'does-not-exist.txt') == set()


def test_save_then_load_seen_domains_roundtrips(tmp_path: Path):
    path = tmp_path / 'state.txt'
    save_seen_domains(path, {'Spam.com', 'other.xyz'})

    loaded = load_seen_domains(path)

    assert loaded == {'spam.com', 'other.xyz'}


def test_save_seen_domains_creates_missing_parent_directory(tmp_path: Path):
    path = tmp_path / 'nested' / 'state.txt'

    save_seen_domains(path, {'spam.com'})

    assert load_seen_domains(path) == {'spam.com'}
