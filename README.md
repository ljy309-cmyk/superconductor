# Superconductor Simulator

초전도체 물리 현상을 인터랙티브하게 학습할 수 있는 교육용 시뮬레이션 플랫폼입니다.
양자역학, 초전도 물리, 양자 보안, AI/데이터 분석, SCADA 제어를 포함한 5개 모듈로 구성되어 있습니다.

## 요구 사항

- Python 3.10+
- 주요 의존성: `pygame`, `numpy`, `matplotlib`, `pandas`, `scikit-learn`, `openpyxl`

```bash
pip install pygame numpy matplotlib pandas scikit-learn openpyxl
```

## 실행

```bash
python main.py
```

Tkinter 메인 메뉴가 열리며, 각 모듈을 선택하여 시뮬레이션을 실행할 수 있습니다.

## 모듈 구성

### Quantum (양자역학)

| 시뮬레이션 | 설명 | 물리 개념 |
|-----------|------|----------|
| **Qubit Chain** | 6+1 큐비트 링 토폴로지에서 노이즈에 의한 스트레스 축적과 캐스케이드 붕괴를 방어 | 양자 얽힘, 캐스케이드 붕괴, QEC |
| **Tunneling** | 장벽 두께에 따른 터널링 확률 변화를 실시간 시각화, 블로흐 구 표시 | 양자 터널링, 중첩, 파동-입자 이중성 |
| **QEC Shield** | 3x5 큐비트 그리드에서 양자 오류 정정(QEC) 방어막을 가동하여 붕괴 방지 | 양자 오류 정정, 노이즈 축적 |

### Physics (초전도 물리)

| 시뮬레이션 | 설명 | 물리 개념 |
|-----------|------|----------|
| **Phase Transition** | 온도-저항 그래프로 YBCO(77K), 수은(4.2K)의 초전도 상전이 시각화 | 임계 온도, 상전이 |
| **Phase Transition Sim** | 단계별 상전이 다이어그램 탐색 | 상 다이어그램 |
| **Flux Pinning** | 마이스너 효과에 의한 초전도체 부양, 스프링-댐퍼 역학 시뮬레이션 | 마이스너 효과, 자속 피닝 |

### Security (양자 보안)

| 시뮬레이션 | 설명 | 물리 개념 |
|-----------|------|----------|
| **BB84 Defense** | BB84 양자 키 분배 프로토콜에서 도청자(Eve) 탐지 및 채널 차단 | BB84 QKD, 디코이 상태, 에러율 분석 |
| **SQUID Mines** | SQUID 자기 센서로 숨겨진 이상 신호를 탐지하는 지뢰찾기 | 자기장 감지, SQUID 센서 |

### Data & AI (데이터/인공지능)

| 도구 | 설명 |
|-----|------|
| **TC Predictor** | RandomForest로 물질 특성(밀도, 원자질량 등 6개)에서 임계 온도 예측 |
| **QRNG Logger** | 양자 노이즈 기반 256비트 난수 생성기, BB84 키 연동 |
| **Play Logger** | 게임 세션 데이터를 JSON/CSV/Excel로 기록 |
| **Ranking** | REST API 기반 로컬 리더보드 (Flask-free, http.server) |
| **Stats Dashboard** | 플레이 이력 통계 시각화 |

### SCADA (디지털 트윈)

| 도구 | 설명 |
|-----|------|
| **Dashboard** | 액체 질소 냉각 시스템 실시간 모니터링 HMI |
| **Cooler** | 히스테리시스 기반 피드백 제어 시뮬레이션 (목표: -196 C) |

## 주요 기능

- **다국어 지원**: 한국어/영어 (런타임 전환)
- **테마**: Catppuccin Mocha 다크 테마 + 색맹 모드 (Protanopia)
- **폰트 스케일링**: 0.8x ~ 1.5x 조절 가능
- **리플레이 시스템**: 프레임 단위 녹화/저장/재생
- **업적 시스템**: 5개 모듈 18개 업적 + 글로벌 뱃지
- **난이도 프리셋**: Easy / Normal / Hard (전 게임 공통)
- **성능 모니터**: FPS / 프레임 타임 실시간 표시
- **시뮬레이션 속도**: 0.5x / 1x / 2x 조절

## 설정

`config.json`에서 모든 물리 파라미터와 게임 설정을 조정할 수 있습니다:

| 섹션 | 설명 |
|-----|------|
| `display` | FPS, 창 크기 |
| `accessibility` | 색맹 모드 |
| `qubit_chain` | 스트레스 임계값, 캐스케이드 피해, 노이즈 비율, QEC 설정 |
| `tunneling` | 터널링 확률, 입자 속도, 장벽 너비 |
| `qec_shield` | 그리드 크기, QEC 감소율/쿨다운 |
| `bb84` | Eve 확률, 에러 임계값, 디코이 설정 |
| `flux_pinning` | 스프링 상수, 댐핑, 중력, 부양 진폭/주파수 |
| `phase_transition` | 온도 범위, 정상 저항값 |
| `squid_mines` | 그리드 크기, 지뢰 수, 민감도 |
| `ml` | RandomForest 하이퍼파라미터 |
| `presets` | Easy/Normal/Hard 난이도 오버라이드 |

## 공통 키보드 조작

| 키 | 동작 |
|----|------|
| `F1` | 물리 설명 도움말 오버레이 |
| `1` / `2` / `3` | 난이도 Easy / Normal / Hard |
| `[` / `]` | 시뮬레이션 속도 감소 / 증가 |
| `L` | 언어 전환 (한/영) |
| `ESC` | 종료 확인 |

## 테스트

```bash
pip install pytest
python -m pytest tests/ -v
```

## 프로젝트 구조

```
superconductor/
├── main.py                    # Tkinter 메인 메뉴
├── config.json                # 전역 설정
├── config_loader.py           # 설정 로더 (스키마 검증)
├── theme.py                   # 테마 관리 (Tkinter + Pygame)
├── i18n.py                    # 다국어 시스템
├── achievements.py            # 업적 시스템
├── replay.py                  # 리플레이 녹화/재생
├── quantum/                   # 양자역학 시뮬레이션
│   ├── qubit_chain.py         #   캐스케이드 붕괴 게임
│   ├── tunneling.py           #   터널링 게임
│   ├── qec_shield.py          #   QEC 방어 게임
│   ├── qubit_physics.py       #   큐비트 물리 엔진
│   ├── tunneling_physics.py   #   터널링 물리 엔진
│   └── qec_physics.py         #   QEC 물리 엔진
├── physics/                   # 초전도 물리 시뮬레이션
│   ├── phase_transition.py    #   상전이 그래프
│   ├── phase_transition_sim.py#   상전이 인터랙티브
│   └── flux_pinning.py        #   마이스너 부양
├── security/                  # 양자 보안 시뮬레이션
│   ├── bb84_defense.py        #   BB84 게임
│   ├── bb84_protocol.py       #   BB84 프로토콜 엔진
│   ├── squid_mines.py         #   SQUID 지뢰찾기
│   └── squid_logic.py         #   SQUID 게임 로직
├── data_ai/                   # 데이터/AI 도구
│   ├── tc_predictor.py        #   ML 임계 온도 예측
│   ├── qrng_logger.py         #   양자 난수 생성기
│   ├── play_logger.py         #   세션 기록기
│   ├── ranking_server.py      #   랭킹 REST API
│   └── ranking.py             #   리더보드 GUI
├── scada/                     # SCADA 디지털 트윈
│   ├── dashboard.py           #   모니터링 대시보드
│   └── cooler.py              #   냉각 시스템 시뮬레이터
├── ui/                        # UI 프레임워크
│   ├── base_launcher.py       #   서브메뉴 기반 클래스
│   └── slider.py              #   Pygame 슬라이더 위젯
└── tests/                     # 테스트 (488+ 케이스)
```

## 라이선스

이 프로젝트는 교육 목적으로 제작되었습니다.
