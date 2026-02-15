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
├── meissner.py              # 프로그램 2 — 마이스너 효과 시뮬레이션
├── tc_prediction.py         # 프로그램 3 — 임계 온도 데이터 분석
├── superconductor_data.csv  # 대규모 실험 데이터 (21,263행)
├── generate_dataset.py      # CSV 데이터셋 생성 스크립트
├── test_main.py             # 메뉴 시스템 테스트 (8 tests)
├── test_meissner.py         # 마이스너 시뮬레이션 테스트 (20 tests)
├── test_superconductor.py   # 초전도 판독기 테스트 (15 tests)
├── test_tc_prediction.py    # 데이터 분석 테스트 (46 tests)
└── test_superconductor_data.csv  # 테스트용 CSV (20행)
```

## Development Setup

### Prerequisites

- Python 3.11+
- numpy, matplotlib (프로그램 2: 마이스너 시뮬레이션)
- pandas, scipy (프로그램 3: 임계 온도 데이터 분석)
- pytest (for running tests)

### Getting Started

```bash
# Install dependencies
pip install numpy matplotlib pandas scipy pytest

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

Tests use **pytest**. Total **89 tests** across four files.
Tests use `monkeypatch` to simulate `input()` and `capsys` to capture printed output.

### `test_main.py` (8 tests)

| Test Class | What it covers |
|---|---|
| `TestShowMenu` | 메뉴 출력 (4개 항목 + 종료 옵션, 제목) |
| `TestMainMenu` | 메뉴 선택 동작 (1→초전도, 2→마이스너, 3→데이터분석, 4→준비 중, 0→종료) |

### `test_meissner.py` (20 tests)

| Test Class | What it covers |
|---|---|
| `TestCreateGrid` | 격자 생성 (크기, 범위, 대칭성) |
| `TestComputeField` | 자기장 계산 (내부=0, 외부 수렴, 표면 편향, 마스크) |
| `TestPlotMeissner` | 시각화 (fig/ax 반환, 파일 저장) |
| `TestRunSimulation` | 대화형 실행 (기본값, 빈 입력, 컬러맵 선택, 오류 처리) |

### `test_tc_prediction.py` (46 tests)

| Test Class | What it covers |
|---|---|
| `TestLoadDataset` | 내장 데이터셋 로드 (DataFrame 형식, 열 이름, 행 수, 유효성) |
| `TestLoadCsv` | CSV 파일 로드 (정상/오류/필수열 검증) |
| `TestGetNumericColumns` | 수치 열 자동 감지 (내장 3개, CSV 6개) |
| `TestBasicStats` | 기본 통계 출력 (소규모 + 대규모 분위수) |
| `TestDataTable` | 데이터 테이블 출력 (소규모 전체 / 대규모 앞뒤 생략) |
| `TestTypeSummary` | 유형별 Tc 요약 통계 |
| `TestCorrelation` | 상관 분석 (내장 3개 / CSV 6개 변수, 범위 확인) |
| `TestRegression` | 회귀 분석 (선형 모델, R², CSV 확장 열) |
| `TestPlotAnalysis` | 시각화 (내장 + CSV 데이터 차트, 파일 저장) |
| `TestRunAnalysis` | 대화형 실행 (내장/CSV 로드, 유형별 요약, 오류 처리) |

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
| 2 | 마이스너 효과 시뮬레이션 | `meissner.py` |
| 3 | 임계 온도 예측 데이터 분석 | `tc_prediction.py` |
| 4 | (준비 중) | — |

### 프로그램 1: `superconductor.py`

단일 함수 `check_superconductivity()`로 구성된 교육용 프로그램:

1. **임계값 설정** — 수은(Hg) 기준: `T_c = 4.2K`, `B_0 = 0.04T`
2. **사용자 입력** — `input()`으로 현재 온도(K)와 자기장(T) 입력
3. **조건 판별** — if-else 조건문으로 상태 결정
4. **결과 출력** — 초전도/일반 상태와 판별 근거 출력

### 프로그램 2: `meissner.py`

마이스너 효과(자기장 배척) 시뮬레이션. 학습 포인트: 반복문(for), 리스트(list), matplotlib.

- **`create_grid()`** — numpy meshgrid로 2D 격자 좌표 생성
- **`compute_field_with_meissner()`** — 자기 쌍극자 모델로 초전도체 주변 자기장 계산
  - 내부: B = 0 (마이스너 효과)
  - 외부: 외부 자기장 + 쌍극자 보정 (자기장이 휘어지는 효과)
- **`plot_meissner()`** — matplotlib quiver plot으로 시각화, PNG 저장
- **`run_meissner_simulation()`** — 대화형 실행 (반지름, 격자 밀도, 자기장 세기, 컬러맵 입력)

### 프로그램 3: `tc_prediction.py`

임계 온도 예측 데이터 분석. 학습 포인트: pandas, scipy, CSV 파일 I/O, 데이터 시각화.

**데이터 소스** (실행 시 선택):
- CSV 파일 — `superconductor_data.csv` (21,263행, 9열: 물질명, 유형, 원소수, 평균원자질량, 평균가전자수, 밀도, 열전도도, 전자비열계수, Tc)
- 내장 데이터 — `SUPERCONDUCTOR_DATA` (20종, 폴백용)

**핵심 함수:**
- **`load_csv()`** — CSV 파일 로드 + 필수 열(물질명, 유형, Tc) 검증
- **`load_dataset()`** — 내장 데이터 20종 DataFrame 반환
- **`get_numeric_columns()`** — Tc 제외 수치형 열 자동 감지
- **`show_basic_stats()`** — 기본 통계 (대규모 데이터는 분위수 추가)
- **`show_data_table()`** — 표 출력 (대규모 데이터는 앞뒤 15행씩 생략 표시)
- **`show_type_summary()`** — 유형별 Tc 요약 (개수, 평균, 중앙값, 최솟/최댓값)
- **`compute_correlation()`** — pearsonr 상관계수 + 유의수준 표시 (***/**/* )
- **`fit_regression()`** — curve_fit 선형 회귀 (기울기, 절편, R²)
- **`plot_analysis()`** — 4종 서브플롯 (대규모 데이터용 점 크기/투명도 자동 조정)
- **`run_tc_analysis()`** — 하위 메뉴 대화형 실행 (1~6 분석 + 데이터 소스 선택)

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
| `meissner.py` | 프로그램 2 — 마이스너 효과 자기장 시뮬레이션 |
| `tc_prediction.py` | 프로그램 3 — 임계 온도 데이터 분석 (CSV + 내장) |
| `superconductor_data.csv` | 대규모 실험 데이터 (21,263행, 9열) |
| `generate_dataset.py` | CSV 데이터셋 생성 스크립트 |
| `test_main.py` | 메뉴 시스템 테스트 (8 tests) |
| `test_superconductor.py` | 초전도 판독기 테스트 (15 tests) |
| `test_meissner.py` | 마이스너 시뮬레이션 테스트 (20 tests) |
| `test_tc_prediction.py` | 데이터 분석 테스트 (46 tests) |
| `test_superconductor_data.csv` | 테스트용 CSV (20행) |
| `README.md` | Project description |
| `CLAUDE.md` | This guide — keep it updated as the project evolves |

## Updating This File

Keep this document current as the project grows. Update it when:
- New modules or files are added
- Dependencies change
- Linting or formatting tools are set up
- CI/CD pipelines are created
- New materials or physics models are introduced
- 새로운 프로그램(4번)이 추가되면 메뉴와 이 문서를 함께 업데이트
