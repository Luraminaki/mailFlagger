# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-07-13

### Added

- Optional real Public Suffix List support: `pip install mailflagger[psl]` pulls in
  `tldextract` (offline mode, no network calls), so `root_domain` uses the authoritative
  list instead of the curated `MULTI_PART_SUFFIXES` fallback.
- `--csv-out PATH`: writes the full per-domain spaminess scores to a CSV file, for opening
  in a spreadsheet.
- `--state-file PATH`: tracks root domains seen across runs and reports only those new
  since the last run.
- `--split-caps`: splits the suggested blacklist between a tight-cap provider (e.g. Yahoo -
  few domain slots) and a generous-cap one (e.g. Outlook), writing four ban-list files
  instead of one. See `--primary-name`, `--primary-domain-cap`, `--primary-address-cap`,
  `--secondary-name`, `--split-out-dir`.

## [0.3.0] - 2026-07-13

Fixes from a full codebase review (32 findings addressed).

### Fixed

- The freemail-provider exclusion in `suggest_blacklist` was silently bypassed
  under `--by-domain` (a subdomain like `mail.yahoo.com` didn't match the
  apex-only exclude list); it's now checked via each domain's registrable
  root, so the safeguard holds under both aggregation modes.
- `root_domain`/`tld` now strip a trailing dot before splitting, so an
  absolute FQDN (`user@example.com.`) no longer collapses unrelated domains
  into a bogus shared `com.` bucket.
- `--version` now reads `mailflagger.__version__` (which already had a safe
  fallback) instead of re-deriving the version independently; previously any
  invocation - not just `--version` - crashed outright if the package wasn't
  installed.
- `load_emails` decodes with `utf-8-sig` and replaces invalid bytes instead of
  aborting the whole run on the first bad byte or leaving a leading BOM stuck
  to the first address.
- `--suspicious-tlds` given with zero values now correctly disables the
  check instead of silently falling back to the defaults; values are also
  lowercased, so `--suspicious-tlds XYZ` behaves the same as `xyz`.
- `--top` rejects negative values instead of producing a report where the
  frequency tables and the spaminess table silently disagree.
- `--no-blacklist` and `--blacklist-out` together now raise a clear argument
  error instead of silently discarding the output path.
- A run where every address fails to parse now stops with a warning instead
  of silently overwriting a previous blacklist file with an empty one.
- `write_blacklist` and `configure_logging` now create their target's parent
  directory instead of crashing with a raw traceback when it doesn't exist.
- `reset_logging` now closes handlers before detaching them, fixing a file
  handle leak that could break log rotation (`PermissionError` on Windows) if
  logging is configured more than once in a process.
- The generic-local-part heuristic now uses word boundaries (no longer
  matches "test" inside "latest" or "info" inside "information") and also
  matches underscore-separated forms (`no_reply`, `do_not_reply`).
- `DEFAULT_EXCLUDED_DOMAINS` now includes common regional variants of the
  major freemail providers (e.g. `yahoo.de`, `hotmail.fr`, `live.co.uk`).
- `.gitignore` now covers the tool's own default blacklist output filename
  (`*_blacklist.txt`), not just `senders.txt` and `banlists/`.

### Changed

- `AnalysisResult`'s per-domain/TLD/local-part counters are now computed
  properties derived from `parsed` instead of separately hand-accumulated
  state, so they can't drift out of sync with it.
- `ParsedEmail` no longer carries an unused `raw` field.
- `logging.StreamHandler`'s stream is reconfigured to UTF-8 where supported,
  so console output no longer diverges from the (already UTF-8) log file for
  non-Latin-1 characters.
- Minor efficiency cleanups: `score_domains` no longer allocates a throwaway
  `DomainScore` on every already-seen domain; the spaminess ranking uses
  `heapq.nlargest` instead of a full sort, matching the pattern already used
  for the frequency tables.
- Added `cli.py`/`logging_utils.py` test coverage and a `conftest.py` fixture
  that isolates root-logger state between tests.

## [0.2.0] - 2026-07-13

Tuned against a real ~1000-address exported blocklist.

### Fixed

- `root_domain` no longer collapses domains registered under a multi-part
  public suffix (`co.uk`, `com.br`, `com.tr`, `ne.jp`, `uk.com`, ...) down to
  the suffix itself. Previously `mail.example.co.uk` and `other.co.uk` were
  both merged into a fake `co.uk` "domain", hiding the actual spam domain and
  risking a nonsensical blacklist entry.
- Major freemail/webmail providers (`gmail.com`, `hotmail.com`, `yahoo.com`,
  `icloud.com`, ...) are now excluded from suggested blacklists by default -
  previously enough reported addresses on one of these could push the entire
  provider domain past `--min-count` and into the blacklist, which would have
  blocked legitimate mail. Override with `--allow-major-providers`.

### Changed

- Broadened the generic-local-part heuristic to also catch `donotreply`,
  `do-not-reply`, `no.reply`, `alert(s)`, `account(s)`, and `member`.

## [0.1.0] - 2026-07-13

### Added

- Initial release of mailflagger.
- `mailflagger` CLI: parses a plain text list of sender addresses and reports
  top domains, root domains, local parts, and TLDs.
- Spaminess scoring per address (suspicious TLD, digit-heavy local part, long
  local part, generic local part), aggregated per domain.
- Suggested domain-level blacklist export, filterable by minimum sender count
  and/or minimum score.
- Rotating file logging alongside console output.
