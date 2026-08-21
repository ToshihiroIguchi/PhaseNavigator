# Rules

- **Communication**: All chat conversations with the user must be in Japanese.
- **Development & Source Code**: Everything else must be in English. All source code, including comments, docstrings, variable names, and documentation, must be written entirely in English.

## 1. Coding Standards & Code Quality
- **Python**: Follow PEP 8 standards. Use static type hints actively for better readability and maintainability.
- **JavaScript**: Write in modern ES6+ standards, avoid global variables, and practice modular, clean function separation.
- **Comments and Docstrings**: Every function and class must include English docstrings detailing parameters, return types, and exceptions.

## 2. Testing & Quality Assurance
- **Automated Tests**: Run `pytest` after any code modification to ensure no regressions.
- **New Feature Tests**: Always write corresponding unit tests under the `tests/` directory when adding new features or API endpoints.

## 3. Git Commit Rules
- **Language**: Commit messages must be written in English.
- **Format**: Follow `Conventional Commits` format (e.g., `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

## 4. Technical Constraints & Architecture
- **Frontend**: Do not introduce external CSS frameworks (such as TailwindCSS) unless requested. Stick to the existing Vanilla CSS and Single-Page Application (SPA) architecture.
- **API Key Security**: Never hardcode or server-side store the Materials Project API key. It is encrypted client-side (AES-GCM) in the browser and sent to the server only through the `X-API-KEY` header.
- **Dependency Management**: Update [requirements.txt](file:///c:/Users/toshi/python/PhaseNavigator/requirements.txt) immediately when adding new libraries.
- **Python Environment**: Always use the Python virtual environment (`venv`) located in the root directory (Python 3.11+ required). Installing dependencies, running tests, and starting the application must be executed within this `venv` environment - use the wrapper scripts (`setup`, `run`, `test` in `.sh` and `.ps1` variants) or the interpreter inside `venv`. See [CLAUDE.md](CLAUDE.md) for the full rule set.

## 5. AI Assistant Operational Constraints
- **Validation**: Verify changes by launching the backend server and running manual checks if applicable.
- **Breaking Changes**: Do not change existing major API routes (like `/diagram`) without user approval.
