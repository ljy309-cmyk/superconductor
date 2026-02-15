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
├── main.py                  # 메인 메뉴 (4개 프로그램 선택)
├── superconductor.py        # 프로그램 1 — 초전도 상태 판독기
├── test_main.py             # 메뉴 시스템 테스트 (8 tests)
└── test_superconductor.py   # 초전도 판독기 테스트 (15 tests)
```

## Development Setup

### Prerequisites

- Python 3.11+
- pytest (for running tests)

### Getting Started

```bash
# Install test dependencies
pip install pytest

# Run the program (menu)
python main.py

# Run the test suite
python -m pytest -v
```

## Build & Run Commands

```bash
# Run the main menu program
python main.py

# Run all tests (메뉴 + 초전도 판독기)
python -m pytest -v

# Run only menu tests
python -m pytest test_main.py -v

# Run only superconductor tests
python -m pytest test_superconductor.py -v

# Run a specific test class
python -m pytest test_superconductor.py::TestSuperconductingState -v
```

## Testing

Tests use **pytest**. Total **23 tests** across two files.
Tests use `monkeypatch` to simulate `input()` and `capsys` to capture printed output.

### `test_main.py` (8 tests)

| Test Class | What it covers |
|---|---|
| `TestShowMenu` | 메뉴 출력 (4개 항목 + 종료 옵션, 제목) |
| `TestMainMenu` | 메뉴 선택 동작 (1→초전도 실행, 2~4→준비 중, 0→종료, 잘못된 입력) |

### `test_superconductor.py` (15 tests)

| Test Class | What it covers |
|---|---|
| `TestCriticalFieldFormula` | B_c(T) 공식 수학적 검증 (0K, T_c/2, T_c 근처, T_c) |
| `TestSuperconductingState` | 낮은 온도 + 낮은 자기장 → 초전도 상태 확인 |
| `TestNormalStateHighTemp` | T >= T_c → 일반 상태 (경계값 포함) |
| `TestNormalStateHighField` | B >= B_c → 일반 상태 (경계값 포함) |
| `TestInvalidInput` | 문자 입력 시 오류 메시지 처리 |
| `TestHeaderOutput` | 헤더에 기준값(T_c, B_0) 출력 확인 |

Run all tests before committing:

```bash
python -m pytest -v
```

## Architecture & Key Concepts

### 메인 메뉴: `main.py`

`main()` → `show_menu()`로 4개 프로그램 메뉴를 표시하고, 사용자 선택에 따라 해당 모듈을 호출한다.
while 루프로 반복 실행되며, "0" 입력 시 종료.

| 번호 | 프로그램 | 모듈 |
|------|---------|------|
| 1 | 초전도 상태 변화 판독기 | `superconductor.py` |
| 2 | (준비 중) | — |
| 3 | (준비 중) | — |
| 4 | (준비 중) | — |

### 프로그램 1: `superconductor.py`

단일 함수 `check_superconductivity()`로 구성된 교육용 프로그램:

1. **임계값 설정** — 수은(Hg) 기준: `T_c = 4.2K`, `B_0 = 0.04T`
2. **사용자 입력** — `input()`으로 현재 온도(K)와 자기장(T) 입력
3. **조건 판별** — if-else 조건문으로 상태 결정
4. **결과 출력** — 초전도/일반 상태와 판별 근거 출력

### State Determination Logic (조건문 흐름)

```
현재 온도(T) >= T_c?
  ├─ YES → 일반 상태 (온도 초과)
  └─ NO  → B_c = B_0 * (1 - (T/T_c)²) 계산
            현재 자기장(B) < B_c?
              ├─ YES → 초전도 상태 (마이스너 효과)
              └─ NO  → 일반 상태 (자기장 초과)
```

## Linting & Code Style

_No linter configured yet._ The `.gitignore` includes patterns for Ruff (`.ruff_cache/`), suggesting Ruff may be adopted.

### Current Conventions (follow these patterns)

- Comments: Korean (`# 1. 임계값 설정`, `# 공식: Bc = B0 * ...`)
- Variable names: Physics notation (`T_c`, `B_0`, `current_T`, `current_B`, `critical_B_at_T`)
- Functions: snake_case (PEP 8)
- User-facing strings: Korean only
- Code style: 간결하고 교육 목적에 맞는 단순한 구조 유지

## CI/CD

_No CI/CD pipeline configured yet._

## Conventions for AI Assistants

### General Principles

- Read existing code before making changes — understand the patterns in use.
- Keep changes minimal and focused on the task at hand.
- Do not add unnecessary abstractions, comments, or features beyond what is requested.
- Follow existing code style and naming conventions.
- Run `python -m pytest -v` after any code changes.

### Python Conventions

- Follow PEP 8 style guidelines.
- Use physics notation for domain variables (`T_c`, `B_0`, `current_T`, `current_B`).
- Write comments in Korean for domain-level explanations.
- Keep user-facing output in Korean.
- Keep the code simple — this is an educational project focused on if-else and variables.
- Prefer standard library solutions over adding new dependencies.

### Git Workflow

- Write clear, concise commit messages describing _why_ the change was made.
- Keep commits focused — one logical change per commit.
- Do not commit environment files (`.env`), credentials, or IDE-specific configuration.

## Key Files to Watch

| File | Purpose |
|------|---------|
| `main.py` | 메인 메뉴 — 4개 프로그램 선택 진입점 |
| `superconductor.py` | 프로그램 1 — 수은 기준 초전도 상태 판별 |
| `test_main.py` | 메뉴 시스템 테스트 (8 tests) |
| `test_superconductor.py` | 초전도 판독기 테스트 (15 tests) |
| `README.md` | Project description |
| `CLAUDE.md` | This guide — keep it updated as the project evolves |

## Updating This File

Keep this document current as the project grows. Update it when:
- New modules or files are added
- Dependencies change
- Linting or formatting tools are set up
- CI/CD pipelines are created
- New materials or physics models are introduced
- 새로운 프로그램(2~4번)이 추가되면 메뉴와 이 문서를 함께 업데이트
