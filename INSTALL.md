# Installation

## Requirements

- Python 3.10+
- No third-party runtime dependencies (standard library only)

## Setup

A virtual environment named `.venv` is expected at the project root.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### Windows (Git Bash) / Linux / macOS

```bash
python3 -m venv .venv
source .venv/Scripts/activate   # Git Bash
# source .venv/bin/activate      # Linux/macOS
pip install -e .
```

This installs the `mailflagger` command into the virtual environment.

## Development install

To also get the tools used for testing and linting:

```bash
pip install -e ".[dev]"
```

## Verify

```bash
mailflagger --help
pytest
```
