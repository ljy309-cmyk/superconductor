# CLAUDE.md — AI Assistant Guide for superconductor

## Project Overview

**superconductor** (초전도체) is a Python educational project that simulates superconductor physics. It determines whether a material is in a **superconducting state** or **normal state** based on temperature and magnetic field inputs, using the critical magnetic field curve equation:

```
B_c(T) = B_0 × [1 - (T / T_c)²]
```

- **Primary language**: Python 3.11+
- **Repository**: Git-based, hosted on GitHub
- **Default branch**: `master`

## Repository Structure

```
superconductor/
├── .gitignore               # Python-specific ignore patterns
├── CLAUDE.md                # This file — AI assistant guide
├── README.md                # Project title and description
├── superconductor.py        # Main module — state determination logic and CLI
└── test_superconductor.py   # pytest test suite (17 tests)
```

## Development Setup

### Prerequisites

- Python 3.11+
- pytest (for running tests)

### Getting Started

```bash
# Install test dependencies
pip install pytest

# Run the program interactively
python superconductor.py

# Run the test suite
python -m pytest test_superconductor.py -v
```

## Build & Run Commands

```bash
# Run the interactive CLI program
python superconductor.py

# Run all tests
python -m pytest test_superconductor.py -v

# Run a specific test class
python -m pytest test_superconductor.py::TestCriticalMagneticField -v

# Run a single test
python -m pytest test_superconductor.py::TestDetermineState::test_superconducting_state -v
```

## Testing

Tests use **pytest** and live in `test_superconductor.py`. There are 17 tests organized into three classes:

| Test Class | What it covers |
|---|---|
| `TestCriticalMagneticField` | The `critical_magnetic_field()` function — boundary values, mid-range, error handling |
| `TestDetermineState` | The `determine_state()` function — superconducting/normal classification, boundary conditions |
| `TestWithRealMaterials` | Integration tests using real material data from the `MATERIALS` dict |

Run all tests before committing:

```bash
python -m pytest test_superconductor.py -v
```

## Architecture & Key Concepts

### Core Module: `superconductor.py`

- **`MATERIALS`** dict — Physical constants (T_c, B_0) for real superconductor materials (Pb, Nb, Sn, Al, Hg)
- **`critical_magnetic_field(T, T_c, B_0)`** — Computes B_c(T) from the critical field curve equation
- **`determine_state(T, B, T_c, B_0)`** — Returns the material state ("초전도 상태" or "일반 상태") and the critical field value
- **`main()`** — Interactive CLI that lets users pick a material, enter conditions, and see results

### State Determination Logic

A material is in the **superconducting state** when BOTH conditions are met:
1. Temperature `T` < critical temperature `T_c`
2. Magnetic field `B` < critical magnetic field `B_c(T)`

Otherwise it is in the **normal state**. At the boundary (T = T_c or B = B_c), the state is normal.

## Linting & Code Style

_No linter configured yet._ The `.gitignore` includes patterns for Ruff (`.ruff_cache/`), suggesting Ruff may be adopted.

### Current Conventions (follow these patterns)

- Docstrings: Korean descriptions with English parameter names
- Comments: Korean for domain-level explanations
- Variable names: Physics notation (`T`, `B`, `T_c`, `B_0`, `B_c`) for domain variables
- Functions: snake_case (PEP 8)
- All user-facing strings are bilingual (Korean with English in parentheses)

## CI/CD

_No CI/CD pipeline configured yet._

## Conventions for AI Assistants

### General Principles

- Read existing code before making changes — understand the patterns in use.
- Keep changes minimal and focused on the task at hand.
- Do not add unnecessary abstractions, comments, or features beyond what is requested.
- Follow existing code style and naming conventions.
- Run `python -m pytest test_superconductor.py -v` after any code changes.

### Python Conventions

- Follow PEP 8 style guidelines.
- Use physics notation for domain variables (T, B, T_c, B_0).
- Write docstrings in Korean with English parameter names.
- Keep user-facing output bilingual (Korean + English).
- Prefer standard library solutions over adding new dependencies.

### Git Workflow

- Write clear, concise commit messages describing _why_ the change was made.
- Keep commits focused — one logical change per commit.
- Do not commit environment files (`.env`), credentials, or IDE-specific configuration.

## Key Files to Watch

| File | Purpose |
|------|---------|
| `superconductor.py` | Core logic — state determination, critical field equation, materials data |
| `test_superconductor.py` | Test suite — 17 tests covering all public functions |
| `README.md` | Project description |
| `CLAUDE.md` | This guide — keep it updated as the project evolves |

## Updating This File

Keep this document current as the project grows. Update it when:
- New modules or files are added
- Dependencies change
- Linting or formatting tools are set up
- CI/CD pipelines are created
- New materials or physics models are introduced
