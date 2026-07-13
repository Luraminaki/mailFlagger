# MAILFLAGGER

Blocking spam one address at a time doesn't scale: mail providers cap how many individual senders you're allowed to blacklist (Yahoo is particularly petty about it), and spammers rotate addresses anyway. In practice, most spam comes from a small number of domains.

`mailflagger` takes a plain text list of sender addresses (e.g. copied out of a Junk folder) and turns it into something you can actually act on: which domains and TLDs show up the most, which addresses look machine-generated, and a ranked, ready-to-paste **blacklist of domains** worth blocking instead of individual addresses.

## VERSION

The current version lives in [pyproject.toml](pyproject.toml). See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## TABLE OF CONTENT

<!-- TOC -->

- [MAILFLAGGER](#mailflagger)
  - [VERSION](#version)
  - [TABLE OF CONTENT](#table-of-content)
  - [TL;DR](#tldr)
  - [INSTALL AND RUN](#install-and-run)
  - [USAGE](#usage)
  - [SCORING](#scoring)
  - [SPLITTING ACROSS PROVIDERS WITH DIFFERENT CAPS](#splitting-across-providers-with-different-caps)
  - [TRACKING NEW DOMAINS ACROSS RUNS](#tracking-new-domains-across-runs)
  - [CSV EXPORT](#csv-export)
  - [SCOPE](#scope)
  - [LOGGING](#logging)
  - [TESTING](#testing)
  - [DEVELOPMENT](#development)

<!-- /TOC -->

## TL;DR

```bash
mailflagger path/to/senders.txt
```

`senders.txt` is one address per line (blank lines and `#`-prefixed comments are ignored). This prints a report and writes a suggested domain blacklist next to the input file.

## INSTALL AND RUN

For detailed setup, see [INSTALL.md](INSTALL.md).

Quick start, once the virtual environment is active:

```bash
pip install -e .
mailflagger path/to/senders.txt
```

For accurate domain collapsing on obscure suffixes, install the optional Public Suffix List backend instead:

```bash
pip install -e ".[psl]"
```

## USAGE

Everything is driven by CLI flags, read once at startup:

| Flag | Default | Meaning |
|---|---|---|
| `--top N` | `20` | Rows to show per report table |
| `--min-count N` | `5` | Minimum distinct senders on a domain to suggest blocking it |
| `--min-score N` | *(none)* | Also suggest domains whose total spam score reaches this value |
| `--by-domain` | off | Score/blacklist by full domain instead of root domain (`mail.spam.com` vs `spam.com`) |
| `--suspicious-tlds ...` | built-in list | Override the TLDs treated as suspicious (e.g. `--suspicious-tlds xyz top click`) |
| `--blacklist-out PATH` | `<input>_blacklist.txt` | Where to write the suggested blacklist |
| `--no-blacklist` | off | Skip writing a blacklist file |
| `--allow-major-providers` | off | Allow major freemail providers (`gmail.com`, `hotmail.com`, ...) into the blacklist (see [SCOPE](#scope)) |
| `--csv-out PATH` | *(none)* | Also write full per-domain scores to CSV (see [CSV EXPORT](#csv-export)) |
| `--state-file PATH` | *(none)* | Track domains across runs, report only new ones (see [TRACKING NEW DOMAINS](#tracking-new-domains-across-runs)) |
| `--split-caps` | off | Split the blacklist across two providers with different caps (see [SPLITTING ACROSS PROVIDERS](#splitting-across-providers-with-different-caps)) |
| `--log-level` | `INFO` | Root logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `--log-file-stem` | `mailflagger` | Stem for the rotating log file (see [LOGGING](#logging)) |
| `--version` | - | Print the installed version and exit |

## SCORING

Each address is scored against a few simple heuristics, and scores are aggregated per domain:

| Pattern | Points | Example |
|---|---|---|
| Suspicious TLD (`.xyz`, `.top`, `.click`, ...) | +3 | `user@offer.xyz` |
| 4+ consecutive digits in the local part | +2 | `promo2024@...` |
| Local part longer than 20 characters | +2 | `a1b2c3d4e5f6g7h8i9j0k@...` |
| Generic local part (`admin`, `noreply`, `promo`, ...) | +1 | `noreply@...` |

A domain is added to the suggested blacklist if it was seen at least `--min-count` times, or (when `--min-score` is set) its total score reaches that value. Domain aggregation collapses subdomains down to the registrable domain (e.g. `mail.spam.com` -> `spam.com`), correctly handling multi-part suffixes like `co.uk`, `com.br`, or `uk.com` so unrelated senders sharing one of those don't get merged into a single fake "domain". By default this uses a curated subset of the [Public Suffix List](https://publicsuffix.org/) covering the common cases; install the optional `psl` extra (`pip install mailflagger[psl]`) to use the real, complete list instead.

Major freemail providers (`gmail.com`, `hotmail.com`, `yahoo.com`, `icloud.com`, and similar - see `DEFAULT_EXCLUDED_DOMAINS` in [blacklist.py](src/mailflagger/blacklist.py)) are never suggested, regardless of count or score: too many unrelated people share those domains for a domain-wide block to be safe. Use `--allow-major-providers` to disable that safeguard.

## SPLITTING ACROSS PROVIDERS WITH DIFFERENT CAPS

Some providers cap how many *domains* you can block much more tightly than how many *addresses* (e.g. Yahoo: a handful of domains vs. up to 1000 addresses), while another provider you also use might allow a much larger combined pool (e.g. Outlook). `--split-caps` writes four files instead of one, into `--split-out-dir` (default `<input stem>_banlists/`):

| File | Contents |
|---|---|
| `<primary-name>_domains.txt` | Highest-value domains, capped to `--primary-domain-cap` (default `3`) |
| `<primary-name>_addresses.txt` | Freemail addresses, plus addresses on repeat domains that didn't make the domain cap, capped to `--primary-address-cap` (default `1000`) |
| `<secondary-name>_domains.txt` | The full suggested domain blacklist, uncapped |
| `<secondary-name>_addresses.txt` | Everything else (one-off addresses, plus any overflow beyond the primary address cap) |

```bash
mailflagger senders.txt --split-caps --primary-name yahoo --secondary-name outlook
```

`--primary-name`/`--secondary-name` default to `primary`/`secondary` and only affect output filenames. Not compatible with `--no-blacklist` or `--blacklist-out`, since it replaces the single-file blacklist output.

## TRACKING NEW DOMAINS ACROSS RUNS

`--state-file PATH` remembers every root domain seen across runs. Each run reports only the domains that are new since the last one (`=== New root domains since last run ===`) before updating the file - useful so re-running mailflagger on an accumulating junk export doesn't mean re-eyeballing the same hundreds of historical domains every time.

## CSV EXPORT

`--csv-out PATH` writes the full per-domain spaminess table (`domain,count,total_score,avg_score,matched_patterns`) to a CSV file, unlike the console report which truncates to `--top` rows - useful for opening in a spreadsheet.

## SCOPE

`mailflagger` does not connect to your mailbox, send anything, or block addresses for you — it only reads a local text file and writes a local text file. Applying the resulting blacklist (as domain blocks / "report as junk") in Yahoo, Outlook, or wherever else, is on you.

## LOGGING

All output goes through the standard `logging` module, formatted as:

```
[%(asctime)s] [%(process)s] [%(name)s] [%(levelname)s]: %(funcName)s -- %(message)s
```

Lines are written to both the console and a rotating file at `<log-file-stem>.log` (5 MB per file, 5 backups kept), via `logging.handlers.RotatingFileHandler`. Only lines at or above `--log-level` are emitted.

## TESTING

```bash
pytest
```

Covers the analyzer (parsing, normalization, frequency tables), the scoring heuristics, and the blacklist selection/export logic.

## DEVELOPMENT

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
