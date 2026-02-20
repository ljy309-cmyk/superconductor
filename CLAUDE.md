# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Superconductor Simulator is an interactive educational platform for learning superconductor physics phenomena. It is built in Python with Tkinter (main menu) and Pygame (simulation windows). The project has 5 modules: Quantum mechanics, Superconductor physics, Quantum security, AI/Data analysis, and SCADA control.

## Common Commands

### Linting and Formatting

```bash
ruff check .                    # Run linter
ruff check --fix .              # Run linter with auto-fix
ruff format .                   # Format code
ruff format --check --diff .    # Check formatting without changing files
```

### Testing

```bash
python -m pytest tests/ -v                                    # Run all tests
python -m pytest tests/ -v --tb=short --cov=. --cov-report=term-missing --cov-fail-under=40 -x  # Run with coverage (CI mode)
python -m pytest tests/test_bb84_protocol.py -v               # Run a single test file
```

### Running the Application

```bash
python main.py    # Launch Tkinter main menu
```

### Installing Dependencies

```bash
pip install pygame numpy matplotlib pandas scikit-learn openpyxl requests flask
pip install pytest pytest-cov ruff    # Dev dependencies
```

## Architecture

- **Entry point**: `main.py` — Tkinter main menu that launches 5 module launchers
- **Module launchers**: `quantum/launcher.py`, `physics/launcher.py`, `security/launcher.py`, `data_ai/launcher.py` — Sub-menus for each module
- **Physics/logic engines**: Files named `*_physics.py` or `*_logic.py` or `*_protocol.py` contain pure computation with no UI dependencies (e.g., `quantum/tunneling_physics.py`, `security/bb84_protocol.py`)
- **Game UIs**: Pygame-based interactive visualizations (e.g., `quantum/tunneling.py`, `security/bb84_defense.py`)
- **Shared utilities**: Root-level modules (`theme.py`, `i18n.py`, `achievements.py`, `replay.py`, `config_loader.py`, `logger.py`, `presets.py`, `sound_manager.py`)
- **UI framework**: `ui/` contains reusable Pygame widgets (`base_launcher.py`, `slider.py`)
- **Configuration**: `config.json` holds all physics parameters, game settings, and difficulty presets
- **Localization**: `locale/ko.json` and `locale/en.json` — runtime-switchable Korean/English

## Key Conventions

- **Python version**: 3.10+ (target 3.10, tested on 3.10, 3.11, 3.12)
- **Line length**: 120 characters
- **Linter**: Ruff with rules E, W, F, I, B, UP enabled
- **Quote style**: Double quotes
- **Import ordering**: isort via Ruff; first-party modules listed in `pyproject.toml` under `[tool.ruff.lint.isort]`
- **i18n**: All user-facing strings use `t("key")` from `i18n.py`; never hardcode display text
- **Theme colors**: Pygame modules use `load_pg_colors()` which injects color constants into module globals dynamically (hence F821 ignores in pyproject.toml)
- **Physics separation**: Keep physics/logic code separate from Pygame rendering code (e.g., `tunneling_physics.py` vs `tunneling.py`)
- **Test coverage**: Minimum 40% required by CI; tests live in `tests/` directory
- **Comments/docstrings**: Existing code uses Korean comments; follow the same style in existing files

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on pushes to `main`, `develop`, and `claude/*` branches:

1. **Lint**: `ruff check .` and `ruff format --check --diff .` (Python 3.12)
2. **Test**: `pytest` with coverage on Python 3.10, 3.11, 3.12 (requires lint to pass first)
3. **Import checks**: Verifies core module imports work correctly

## Per-File Lint Ignores

Some files have specific Ruff rule ignores configured in `pyproject.toml`:

- **F821** (undefined names): Pygame modules that use `load_pg_colors()` for dynamic color injection
- **E402** (import order): Files with path setup or conditional imports
- **F401** (unused imports): Files with try/except availability-check patterns
