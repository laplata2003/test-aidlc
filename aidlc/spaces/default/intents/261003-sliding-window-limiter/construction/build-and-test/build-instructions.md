# Build Instructions: Sliding-Window Rate Limiter

The project is a pure-Python library with no compile or bundle step. "Build" means: the package metadata is valid, every source file parses, and the package imports with only the standard library.

## Dependency Installation

- Runtime dependencies: none.
- Test dependency: `pytest` 7 or later.
- Recommended, in a virtual environment (keeps your system Python untouched):

```
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

- Without a virtual environment, `python3 -m pip install pytest` works on a Python that allows it. The system Python on this machine (3.14.7, Homebrew) refused that under its externally-managed-environment rule; see the Environment Change section of `code-summary.md`.

## Environment Setup

- Python 3.10 or later (3.14.7 was used for the verified run).
- No environment variables, config files, or local services.
- Run every command from the workspace root. `pyproject.toml` sets `pythonpath = ["src"]` for pytest, so the tests do not need the package installed.

## Build Commands

There is nothing to compile. Use these checks as the build:

```
python3 -B - <<'EOF'
import sys, tomllib
meta = tomllib.load(open("pyproject.toml", "rb"))
print(meta["project"]["name"], meta["project"]["requires-python"], meta["project"].get("dependencies", []))
sys.path.insert(0, "src")
import sliding_window_limiter as m
print(m.__all__)
EOF
```

To produce a wheel (optional, needs `pip install build`): `python3 -m build`.

## Build Verification

Expected output of the check above:

```
sliding-window-limiter >=3.10 []
['SlidingWindowLimiter', 'CheckResult', 'KeyState']
```

Then run the unit tests (see `unit-test-instructions.md`): `python3 -m pytest tests/test_limiter.py` should report 51 passed.

## Troubleshooting

- `No module named pytest`: install it as above, preferably in a virtual environment.
- `error: externally-managed-environment` from pip: use a virtual environment instead of installing into the system Python.
- `ModuleNotFoundError: sliding_window_limiter` when running a script by hand: add `src` to the path (`PYTHONPATH=src`) or install with `pip install -e .`. pytest does not need this.
- `tomllib` missing: it is part of Python 3.11 and later; on 3.10 skip that line of the check.
