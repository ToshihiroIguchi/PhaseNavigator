# CLAUDE.md

Guidance for Claude Code (and any AI assistant) working in this repository.

## 0. Language Policy (highest priority)

- **Conversation with the user and plans**: always Japanese, with no exceptions.
  Every chat reply, question, explanation, progress note, and status report
  addressed to the user must be written in Japanese. Plans must also be written
  entirely in Japanese: this covers the plan file itself (for example the files
  under `~/.claude/plans/`), its headings, and the text shown for approval in
  plan mode. Do not draft a plan in English and translate it afterwards.
- **Everything else**: always English. Source code, identifiers, comments,
  docstrings, log messages, UI strings, test names, documentation (`README.md`,
  `DEPENDENCIES.md`, this file), commit messages, branch names, and pull request
  descriptions must be written entirely in English.

## 1. Python Environment (venv is mandatory)

- The project virtual environment lives in `./venv` at the repository root and is
  **not** tracked by Git.
- Never install packages into, or run this project with, the system Python.
  The system interpreter carries different (older) versions of `fastapi`,
  `pymatgen`, and friends, which produces import errors and hard-to-reproduce bugs.
- Requires **Python 3.11 or newer** (`pymatgen`, `mp-api`, and `emmet-core`
  dropped support for 3.10).
- Bootstrap and use the environment through the wrapper scripts:

  | Task  | Windows (PowerShell) | Linux / macOS |
  |-------|----------------------|---------------|
  | Setup | `.\setup.ps1`        | `./setup.sh`  |
  | Run   | `.\run.ps1`          | `./run.sh`    |
  | Test  | `.\test.ps1`         | `./test.sh`   |

- When invoking Python directly, always use the interpreter inside the venv:
  `venv\Scripts\python.exe -m pytest` (Windows) or `venv/bin/python -m pytest`
  (Linux/macOS). A bare `python`, `pip`, `pytest`, or `uvicorn` command is a bug.
- The optional pymatgen add-ons (`enumlib`, `bader`) are **not** required by the
  phase diagram pipeline. Install them only on request via
  `./setup.sh --with-pmg-addons` or `.\setup.ps1 -WithPmgAddons`.

## 2. Coding Standards & Code Quality

- **Python**: follow PEP 8. Use type hints actively for readability and maintainability.
- **JavaScript**: modern ES6+, no global variables, modular and clean function separation.
- **Comments and docstrings**: every function and class needs an English docstring
  describing parameters, return types, and raised exceptions.

## 3. Testing & Quality Assurance

- Run the test suite (`./test.sh` or `.\test.ps1`) after any code modification to
  catch regressions.
- Add unit tests under `tests/` for every new feature or API endpoint.

## 4. Dependency Management

- Update `requirements.txt` immediately when adding a library, and keep the lower
  version bounds in sync with the versions the project is verified against.

## 5. Git Rules

- Commit messages: English, `Conventional Commits` format
  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
- Never commit `venv/`, `.env`, log files, or build artifacts.

## 6. Technical Constraints & Architecture

- **Frontend**: do not introduce external CSS frameworks (e.g. TailwindCSS) unless
  requested. Keep the existing Vanilla CSS single-page application architecture.
- **API key security**: never hardcode or server-side store the Materials Project
  API key. The key is encrypted client-side (AES-GCM) and stored in the browser;
  the server accepts it only through the `X-API-KEY` header.
- **Static edition**: the static site (`scripts/build_static_site.py`, `phasecore/`)
  needs no API key; its data is downloaded in advance with
  `scripts/build_static_data.py`. Read the key for that script only from an
  environment variable or a file outside the repository, and never print or log it.
  Keep the downloaded data (`static_site/`) out of Git, include only CC BY 4.0
  materials (never GNoME / CC BY-NC), and keep `phasecore` free of pymatgen so it
  runs in Pyodide.
- **Breaking changes**: do not change existing major API routes (such as `/diagram`)
  without user approval.

## 7. AI Assistant Operational Constraints

- Verify changes by launching the backend server from the venv and performing manual
  checks when applicable.
- Report honestly: if a step was skipped or could not be verified, say so.
