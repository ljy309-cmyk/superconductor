"""F1 인게임 도움말 오버레이 — 물리 현상 설명.

각 Pygame 게임 모듈에서 F1을 누르면 반투명 오버레이가 나타나
현재 시뮬레이션의 물리 원리를 설명합니다.

사용법:
    from help_overlay import HelpOverlay
    overlay = HelpOverlay("qubit_chain")

    # 이벤트 루프:
    overlay.handle_event(event)

    # 렌더링 (맨 마지막에):
    overlay.draw(screen, font)
"""

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

from i18n import t

# 모듈별 도움말 텍스트 (한국어)
_HELP_TEXTS: dict[str, list[str]] = {
    "gate_builder": [
        "=== Quantum Gate Builder ===",
        "",
        "[양자 게이트]",
        "  H (Hadamard): |0⟩→|+⟩, |1⟩→|−⟩  중첩 생성",
        "  X (Pauli-X): 비트 플립 (NOT)  |0⟩↔|1⟩",
        "  Y (Pauli-Y): Y축 회전",
        "  Z (Pauli-Z): 위상 플립  |1⟩→-|1⟩",
        "  S (Phase): π/2 위상 회전",
        "  T (π/8): π/4 위상 회전",
        "  CNOT: 조건부 NOT (제어 큐비트 = 1이면 타겟 플립)",
        "",
        "[블로흐 구]",
        "  |0⟩ = 북극, |1⟩ = 남극",
        "  |+⟩ = +X, |−⟩ = −X",
        "  Tab: 표시할 큐비트 전환",
        "",
        "[조작법]",
        "  팔레트 클릭 → 와이어 클릭: 게이트 배치",
        "  Enter: 측정  |  Backspace: 마지막 게이트 삭제",
        "  Delete: 전체 초기화",
    ],
    "qubit_chain": [
        "=== Qubit Entanglement Cascade ===",
        "",
        "[물리 원리]",
        "  초전도 큐비트는 외부 노이즈(열, 자기장)에 취약합니다.",
        "  양자 얽힘(Entanglement)으로 연결된 큐비트는",
        "  하나가 붕괴하면 연쇄적으로 인접 큐비트도 데미지를 받습니다.",
        "",
        "[QEC 방어막]",
        "  양자 오류 정정(Quantum Error Correction)은",
        "  노이즈를 감쇠시켜 큐비트 수명을 연장합니다.",
        "  현실에서는 여분의 큐비트를 사용해 에러를 탐지/복구합니다.",
        "",
        "[조작법]",
        "  클릭/Enter: 큐비트 오류 정정 (stress -> 0)",
        "  Tab: 큐비트 포커스 순환 (키보드 선택)",
        "  S: QEC 방어막 활성화",
        "  H: 전체 힐링 (-stress)",
        "  N: 랜덤 노이즈 주입",
        "  1/2/3: 난이도 프리셋",
        "  F5: 프로파일 저장 | F9: 불러오기",
    ],
    "tunneling": [
        "=== Quantum Superposition & Tunneling ===",
        "",
        "[양자 중첩]",
        "  큐비트는 |0>과 |1> 상태를 동시에 가질 수 있습니다.",
        "  블로흐 구(Bloch Sphere) 위의 벡터로 시각화됩니다.",
        "  관측 전까지 확률적으로 두 상태를 오갑니다.",
        "",
        "[양자 터널링]",
        "  고전 물리에서는 에너지가 부족하면 장벽을 통과 불가능.",
        "  양자역학에서는 확률적으로 장벽을 '통과'할 수 있습니다!",
        "  장벽이 두꺼울수록 통과 확률은 지수적으로 감소합니다.",
        "  수식: P ~ exp(-2 * kappa * d)",
        "",
        "[조작법]",
        "  클릭: 입자 재발사  |  장벽 드래그: 두께 조절",
        "  SPACE: 일시정지  |  R: 리셋  |  ESC: 종료",
        "  Up/Down: 속도 배율  |  Left/Right: 장벽 두께",
        "  W/A/S/D: 블로흐 구 회전 (키보드 조작)",
        "  [/]: 시뮬레이션 속도  |  Tab: 업적 기록",
        "  L: 언어 전환  |  D: 난이도 변경  |  1/2/3: 프리셋",
        "  Ctrl+X: 데이터 내보내기  |  Ctrl+I: 가져오기",
        "  F3: 배리어 스위프 (자동 폭 순회 통계)",
        "  F4: 스텝 모드 (N: 한 프레임 진행)",
        "  F1: 도움말 토글",
    ],
    "qec_shield": [
        "=== Quantum Error Correction Shield ===",
        "",
        "[양자 오류 정정]",
        "  큐비트는 환경 노이즈로 인해 끊임없이 에러가 발생합니다.",
        "  QEC는 여분의 큐비트를 사용해 에러를 탐지/복구하는 기술입니다.",
        "",
        "[감쇠 계수]",
        "  x0.0 = 완전 차단 (무적) — 현실에서는 불가능",
        "  x0.5 = 50% 차단 — 표면 코드 수준",
        "  x1.0 = 차단 없음 — QEC 미적용",
        "",
        "[조작법]",
        "  S: 방어막 활성화",
        "  H: 전체 힐링",
        "  Left/Right: 감쇠 계수 조절",
        "  1/2/3: 난이도 프리셋",
    ],
    "bb84_defense": [
        "=== BB84 Quantum Key Distribution ===",
        "",
        "[BB84 프로토콜]",
        "  Alice가 랜덤 기저(+/x)로 큐비트를 Bob에게 전송.",
        "  Bob도 랜덤 기저로 측정. 기저가 일치하면 키 비트 공유.",
        "  Eve가 도청하면 양자 상태가 교란되어 에러율 급증!",
        "",
        "[도청 탐지 원리]",
        "  양자 복제 불가능 정리(No-Cloning Theorem):",
        "  Eve는 큐비트를 복사할 수 없어 반드시 흔적을 남깁니다.",
        "  에러율(QBER) > 11%이면 도청이 있다고 판단합니다.",
        "",
        "[디코이 상태 프로토콜]",
        "  Alice가 가짜 큐비트(디코이)를 섞어 보내면",
        "  Eve가 디코이를 건드렸을 때 2배 에러가 발생합니다.",
        "",
        "[조작법]",
        "  SPACE: 통신망 폐쇄/재개",
        "  A: 자동차단 ON/OFF",
        "  1/2/3: 난이도 프리셋",
    ],
    "qkd_advanced": [
        "=== Advanced QKD — E91 · Key Sifting · Multi-Party ===",
        "",
        "[E91 프로토콜 (Ekert 1991)]",
        "  EPR 소스에서 |Φ+⟩ 벨 쌍 생성 → Alice/Bob 분배",
        "  Alice 기저: {0°, π/8, π/4}",
        "  Bob 기저: {π/8, π/4, 3π/8}",
        "  같은 기저 → 키 비트 생성  |  다른 기저 → 벨 부등식 검증",
        "  S ≈ 2√2 이면 양자 상관 확인 → 도청 없음!",
        "",
        "[QKD 후처리 파이프라인 (4단계)]",
        "  1. QBER 추정: 원시 키의 20%를 공개 비교 → 에러율 측정",
        "     (QBER > 11%이면 도청 의심 → 키 폐기)",
        "  2. 에러 정정: 블록 패리티(4-bit) + 이진 탐색으로 수정",
        "  3. 프라이버시 증폭: Toeplitz 범용 해시로 키 압축",
        "     (2-universal hash → Leftover Hash Lemma로 보안 보장)",
        "     → Eve의 부분 정보를 정보이론적으로 제거!",
        "  4. OTP 암호화 데모: 최종 키로 XOR 암호화/복호화 시연",
        "     (One-Time Pad: 키 ≥ 메시지 → 정보이론적 보안)",
        "",
        "[다자간 QKD (GHZ) — 3~5자간 확장]",
        "  |GHZ⟩ = (|00…0⟩+|11…1⟩)/√2 (N자간 얽힘)",
        "  Z 기저: 모든 파티 같은 결과 → 키 비트",
        "  X 기저: 짝수 패리티 확인 → 일관성 검증",
        "  Eve 도청 시 패리티 깨짐 → 도청 탐지",
        "  일관성 패스율 수렴 그래프: 실시간 보안 추이 확인",
        "  Up/Down 키 또는 클릭으로 파티 수 변경 (3→4→5)",
        "",
        "[BB84 vs E91 비교 모드]",
        "  같은 Eve 조건에서 두 프로토콜을 나란히 실행:",
        "  BB84 — QBER 기반 통계적 탐지 + QBER 그래프 + 키 생성률",
        "  E91 — 벨 부등식(CHSH) 물리적 탐지 + Bell S 그래프 + 키 생성률",
        "  키 생성률 비교: BB84 ~50% vs E91 ~22% (기저 쌍 확률)",
        "  SPACE로 배치 실행  |  S: E91 키 시프팅/PA",
        "",
        "[조작법]",
        "  Tab/클릭: 모드 전환 (E91/Sift/GHZ/Compare)",
        "  SPACE: 배치 실행  |  S: 키 시프팅/PA",
        "  E: Eve 단계 순환 (0→10→30→50→80→100%)",
        "  A: 자동 실행  |  P: 일시정지  |  R: 리셋",
    ],
    "squid_mines": [
        "=== SQUID Magnetic Flux Sensor ===",
        "",
        "[SQUID 센서]",
        "  초전도 양자 간섭 소자(SQUID)는 세계에서 가장",
        "  민감한 자기장 센서입니다.",
        "  조셉슨 접합(Josephson Junction)을 이용합니다.",
        "",
        "[자기 선속 양자화]",
        "  초전도체 고리를 통과하는 자기 선속(Phi)은",
        "  양자화되어 Phi_0 = h/(2e) 단위로만 존재합니다.",
        "  이 원리로 극미세 자기장 변화를 감지합니다.",
        "",
        "[게임 메카닉]",
        "  마우스를 지뢰에 가까이 가져갈수록",
        "  하단 자기 선속 그래프가 크게 요동칩니다.",
        "  민감도를 높이면 감지 범위가 넓어집니다.",
        "",
        "[조작법]",
        "  클릭/Enter: 지뢰 마킹",
        "  WASD: 그리드 커서 이동 (키보드 탐색)",
        "  Up/Down: 민감도 조절",
        "  M: 사운드 ON/OFF",
        "  1/2/3: 난이도 프리셋",
    ],
    "cooper_pair": [
        "=== Cooper Pair & BCS Theory ===",
        "",
        "[BCS 이론]",
        "  초전도 현상은 전자가 쌍(Cooper Pair)을 이루어 설명됩니다.",
        "  1957년 Bardeen-Cooper-Schrieffer가 발표한 이론입니다.",
        "",
        "[쿠퍼 쌍 형성]",
        "  전자 하나가 격자 이온을 끌어당기면(포논 방출),",
        "  이 격자 변형이 다른 전자를 유인합니다.",
        "  결과: 두 전자가 포논을 매개로 간접 인력을 느낍니다.",
        "  이 쌍은 보손처럼 행동하여 저항 없이 흐를 수 있습니다.",
        "",
        "[에너지 갭 Δ(T)]",
        "  T < Tc: 에너지 갭 존재 → 산란 불가 → 저항 = 0",
        "  수식: Δ(T) ≈ Δ₀ × √(1 - (T/Tc)²)",
        "  T ≥ Tc: 갭 소멸 → 쌍 해체 → 정상 저항",
        "",
        "[조작법]",
        "  Up/Down: 온도 조절 (5K 단위)",
        "  마우스 드래그: 온도 슬라이더",
        "  [/]: 시뮬레이션 속도",
    ],
    "phase_transition_sim": [
        "=== Phase Transition Simulation ===",
        "",
        "[상전이]",
        "  온도가 임계 온도(Tc) 이하로 내려가면 초전도 상태로 전이됩니다.",
        "  격자 원자의 열진동이 감소 → 전자 산란 감소 → 저항 = 0.",
        "",
        "[물질 목록 (8종)]",
        "  YBCO (92K), BSCCO (110K), MgB₂ (39K), Nb₃Sn (18K),",
        "  Nb (9.3K), Pb (7.2K), Hg (4.2K), Al (1.2K)",
        "",
        "[쿠퍼쌍]",
        "  Tc 이하에서 전자가 포논을 매개로 쌍(Cooper Pair)을 형성합니다.",
        "  파란 연결선 = 쿠퍼쌍 결합, 녹색 글로우 = 초전도 상태.",
        "",
        "[조작법]",
        "  Tab: 물질 변경 (8종 순환)",
        "  Up/Down: 온도 조절 (5K 단위)",
        "  SPACE: 자동 냉각/가열 토글",
        "  R: 리셋 (300K)  |  L: 언어 전환",
    ],
    "josephson_junction": [
        "=== Josephson Junction ===",
        "",
        "[조셉슨 효과]",
        "  두 초전도체 사이에 얇은 장벽(절연체/금속)을 끼운 구조입니다.",
        "  1962년 Brian Josephson이 예측, 노벨상 수상.",
        "",
        "[DC 조셉슨 효과]",
        "  전압 없이도 초전류가 흐릅니다:",
        "  I = Ic × sin(φ),  φ = 위상 차이",
        "  바이어스 전류 |I| ≤ Ic이면 제로 전압 상태.",
        "",
        "[AC 조셉슨 효과]",
        "  |I| > Ic 이면 전압이 발생하고 위상이 진동합니다:",
        "  dφ/dt = 2eV/ℏ",
        "  주파수 f = 2eV/h ≈ 483.6 GHz/mV",
        "",
        "[워시보드 퍼텐셜]",
        "  U(φ) = -Ic cos(φ) - I_bias φ/(2π)",
        "  바이어스가 작으면 우물에 갇힘 (DC 효과)",
        "  바이어스가 크면 우물 소멸 (AC 효과, 위상 미끄러짐)",
        "",
        "[조작법]",
        "  Up/Down: 바이어스 전류 ±0.1",
        "  마우스 드래그: 바이어스 슬라이더",
        "  R: 리셋  |  [/]: 시뮬레이션 속도",
    ],
    "flux_pinning": [
        "=== Meissner Levitation & Flux Pinning ===",
        "",
        "[마이스너 효과]",
        "  초전도체는 내부 자기장을 완전히 배제합니다.",
        "  이로 인해 자석 위에서 안정적으로 부상할 수 있습니다.",
        "",
        "[플럭스 피닝]",
        "  Type-II 초전도체에서는 자기 선속이",
        "  소용돌이(vortex) 형태로 초전도체를 관통합니다.",
        "  이 소용돌이가 결함에 '고정'되어 초전도체가",
        "  공간상에 안정적으로 잠깁니다 (Quantum Locking).",
        "",
        "[조작법]",
        "  마우스 드래그/화살표키: 자석 이동",
        "  F: 자석 N/S 뒤집기",
        "  SPACE: 초전도 ON/OFF (온도 변화)",
    ],
    "scada_security": [
        "=== SCADA Security — MITM Attack & QKD Defense ===",
        "",
        "[SCADA 시스템]",
        "  SCADA(Supervisory Control and Data Acquisition)는",
        "  산업 제어 시스템의 핵심으로, 센서→컨트롤러→HMI로",
        "  구성된 네트워크로 물리적 프로세스를 모니터링합니다.",
        "",
        "[MITM 공격 (중간자 공격)]",
        "  공격자(Eve)가 센서-컨트롤러 사이에 침투하여:",
        "  - 센서 데이터를 조작 (실제 온도 상승, 표시 온도 정상)",
        "  - 냉각 명령을 방해 → 시스템 과열 위험",
        "  HMI 운영자는 정상 온도를 보지만 실제로는 위험!",
        "",
        "[BB84 양자 키 분배 (QKD)]",
        "  양자 역학을 이용한 통신 보안:",
        "  - QBER(양자 비트 에러율) 모니터링",
        "  - 정상: QBER < 11%  |  공격 시: QBER > 11%",
        "  - QBER 임계값 초과 → 공격 탐지 → 양자 인증 채널 구축",
        "  - No-Cloning Theorem: 도청자는 반드시 흔적을 남긴다",
        "",
        "[시나리오 흐름]",
        "  NORMAL → ATTACK → DETECTED → PROTECTED → NORMAL",
        "  자동 모드: 공격이 주기적으로 발생/탐지/차단",
        "",
        "[조작법]",
        "  SPACE: 수동 공격/방어 트리거",
        "  A: 자동 시나리오 ON/OFF",
        "  Q: QKD 모니터링 ON/OFF",
        "  P: 일시정지  |  R: 리셋",
    ],
    "entanglement": [
        "=== Quantum Entanglement Simulator ===",
        "",
        "[벨 상태 (Bell States)]",
        "  |Φ+⟩ = (|00⟩+|11⟩)/√2  측정 시 00 또는 11",
        "  |Φ-⟩ = (|00⟩-|11⟩)/√2  측정 시 00 또는 11",
        "  |Ψ+⟩ = (|01⟩+|10⟩)/√2  측정 시 01 또는 10",
        "  |Ψ-⟩ = (|01⟩-|10⟩)/√2  측정 시 01 또는 10",
        "  두 큐비트가 완벽하게 상관/반상관됩니다.",
        "",
        "[CHSH 부등식]",
        "  고전 물리: |S| ≤ 2 (숨은 변수 이론)",
        "  양자역학: |S| ≤ 2√2 ≈ 2.828 (치렐슨 한계)",
        "  벨 상태로 실험하면 S ≈ 2.828 → 고전 한계 위반!",
        "  이는 양자 얽힘이 '비국소적(nonlocal)'임을 증명합니다.",
        "",
        "[양자 텔레포테이션]",
        "  1. 입력 상태 준비: |ψ⟩ = α|0⟩ + β|1⟩",
        "  2. Alice-Bob 벨 쌍 공유",
        "  3. Alice: 입력+자신의 큐비트에 CNOT+H 적용",
        "  4. Alice 측정 → 2비트 고전 정보",
        "  5. Bob: 고전 정보로 보정 게이트(X, Z) 적용",
        "  6. Bob의 큐비트 = 원래 입력 상태 (Fidelity ≈ 1)",
        "",
        "[조작법]",
        "  Tab: 모드 전환 (Bell / CHSH / Teleport)",
        "  SPACE: 측정 / 실험 / 다음 단계",
        "  1-4: 벨 상태 선택  |  R: 초기화",
    ],
}


class HelpOverlay:
    """F1 도움말 오버레이."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self.visible = False
        self.lines = _HELP_TEXTS.get(module_name, ["No help available."])

    def handle_event(self, event: pygame.event.Event) -> bool:
        """F1 키로 토글. True 반환 시 이벤트 소비됨."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
            self.visible = not self.visible
            return True
        # ESC로 닫기
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.visible:
            self.visible = False
            return True
        return False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        """오버레이 렌더링."""
        if not self.visible:
            # F1 힌트만 작게 표시
            hint = font.render(t("help_f1_hint"), True, (88, 91, 112))
            screen.blit(hint, (screen.get_width() - hint.get_width() - 10, 4))
            return

        w, h = screen.get_size()

        # 반투명 배경
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        # 도움말 박스
        box_w, box_h = min(600, w - 60), min(500, h - 60)
        box_x, box_y = (w - box_w) // 2, (h - box_h) // 2

        pygame.draw.rect(screen, (30, 30, 46), (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(screen, (137, 180, 250), (box_x, box_y, box_w, box_h), 2, border_radius=10)

        # 텍스트 렌더링
        ty = box_y + 16
        for line in self.lines:
            if line.startswith("==="):
                color = (137, 180, 250)  # 타이틀 파랑
            elif line.startswith("["):
                color = (249, 226, 175)  # 섹션 노랑
            elif line.startswith("  수식") or line.startswith("  P ~") or line.startswith("  Phi"):
                color = (203, 166, 247)  # 수식 보라
            else:
                color = (205, 214, 244)  # 일반 텍스트

            if line:
                surf = font.render(line, True, color)
                screen.blit(surf, (box_x + 20, ty))
            ty += 18
            if ty > box_y + box_h - 30:
                break

        # 닫기 안내
        close = font.render(t("help_close"), True, (88, 91, 112))
        screen.blit(close, (box_x + box_w // 2 - close.get_width() // 2, box_y + box_h - 24))
