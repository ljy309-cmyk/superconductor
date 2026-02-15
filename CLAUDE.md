# CLAUDE.md — AI Assistant Guide for superconductor

## Project Overview

**superconductor** (초전도체) is a Python project. The repository is in its early stages of development.

- **Primary language**: Python
- **Repository**: Git-based, hosted on GitHub
- **Default branch**: `master`

## Repository Structure

```
superconductor/
├── .gitignore          # Python-specific ignore patterns
├── README.md           # Project title and description
└── CLAUDE.md           # This file — AI assistant guide
```

## Development Setup

### Prerequisites

- Python 3.x (version TBD — no `.python-version` or `pyproject.toml` yet)

### Getting Started

No build system or dependency management is configured yet. When one is added, update this section with:
- How to create a virtual environment
- How to install dependencies
- How to run the project

## Build & Run Commands

_No build system configured yet._ When tooling is added, document commands here:

```bash
# Example placeholders — replace when real tooling is added:
# python -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt
# python -m superconductor
```

## Testing

_No test framework configured yet._ The `.gitignore` includes patterns for pytest, tox, nox, and coverage — suggesting pytest is the likely choice.

When tests are added, document:
- How to run the full test suite
- How to run a single test file or test case
- How to check code coverage

## Linting & Code Style

_No linter configured yet._ The `.gitignore` includes patterns for Ruff (`.ruff_cache/`), suggesting Ruff may be adopted.

When linting is configured, document:
- How to run the linter
- How to auto-fix lint issues
- Any project-specific style rules

## CI/CD

_No CI/CD pipeline configured yet._ When one is added (e.g., GitHub Actions), document:
- What checks run on PRs
- How to interpret CI failures
- Required checks before merging

## Conventions for AI Assistants

### General Principles

- Read existing code before making changes — understand the patterns in use.
- Keep changes minimal and focused on the task at hand.
- Do not add unnecessary abstractions, comments, or features beyond what is requested.
- Follow existing code style and naming conventions once source code is established.

### Python Conventions (anticipated)

- Follow PEP 8 style guidelines unless the project adopts specific overrides.
- Use type hints where the existing codebase uses them.
- Write docstrings for public functions/classes if the codebase follows that pattern.
- Prefer standard library solutions over adding new dependencies when practical.

### Git Workflow

- Write clear, concise commit messages describing _why_ the change was made.
- Keep commits focused — one logical change per commit.
- Do not commit environment files (`.env`), credentials, or IDE-specific configuration.

## Key Files to Watch

| File | Purpose |
|------|---------|
| `README.md` | Project description and setup instructions |
| `.gitignore` | Files excluded from version control (Python-focused) |
| `CLAUDE.md` | This guide — keep it updated as the project evolves |

## Updating This File

Keep this document current as the project grows. Update it when:
- A build system or dependency manager is added (e.g., `pyproject.toml`, `requirements.txt`)
- A test framework is configured
- Linting or formatting tools are set up
- CI/CD pipelines are created
- Major architectural decisions are made
- New key directories or modules are introduced
