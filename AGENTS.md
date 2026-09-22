# Repository Guidelines

## Project Structure & Module Organization

Application code lives under `app/`. Keep shared infrastructure in `app/core/`, translation logic in `app/translation/`, EPUB/PDF processing in `app/pipeline/`, background work in `app/jobs/`, and user-facing features in `app/library/`, `app/reader/`, and `app/glossary/`. CLI parsing is in `app/cli/`; `app/main.py` is the command-line entry point and `app/web.py` runs the local web application. Tests live in `tests/` and generally mirror feature modules. Runtime files belong in `data/`, `output/`, or `temp/` and should not be committed.

## Build, Test, and Development Commands

- `python -m venv .venv` creates the local virtual environment.
- `.\.venv\Scripts\Activate.ps1` activates it on Windows PowerShell.
- `pip install -r requirements.txt` installs runtime and test dependencies.
- `python -m app.main --help` lists CLI translation commands and options.
- `python -m app.web` starts the local web dashboard.
- `python -m pytest -q` runs the full test suite.
- `python -m pytest tests/test_library.py -q` runs one focused test module.

## Coding Style & Naming Conventions

Use four-space indentation and standard Python conventions: `snake_case` for functions, variables, and modules; `PascalCase` for classes; and uppercase names for constants. Prefer small, focused modules and type hints for public interfaces. Keep UI text and persisted state changes compatible with existing resumable jobs. No formatter or linter is currently enforced, so match nearby code and keep diffs focused.

## Testing Guidelines

Tests use `pytest`. Name files `test_<feature>.py` and test functions `test_<behavior>()`. Add regression tests for changes to job persistence, resume behavior, glossary generation, EPUB/PDF processing, and reader rendering. Run the narrowest relevant tests first, then the full suite before opening a pull request.

## Commit & Pull Request Guidelines

Recent history uses concise Conventional Commit-style subjects such as `feat: ...` and `chore: ...`. Use an imperative subject that describes one logical change. Pull requests should explain user-visible behavior, list validation commands, link related issues, and include screenshots for dashboard, library, or reader UI changes. Do not commit API keys, generated books, job state, or local virtual environments.

## Configuration & Security

Store credentials in local configuration or environment variables, never in tracked files. Review `.gitignore` before adding new runtime artifacts, and use sample or redacted values in documentation and tests.
