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

import pygame

# 모듈별 도움말 텍스트 (한국어)
_HELP_TEXTS: dict[str, list[str]] = {
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
        "  클릭: 큐비트 오류 정정 (stress -> 0)",
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
        "  클릭: 입자 재발사",
        "  Up/Down: 속도 배율",
        "  Left/Right: 장벽 두께",
        "  1/2/3: 난이도 프리셋",
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
        "  클릭: 지뢰 마킹",
        "  Up/Down: 민감도 조절",
        "  M: 사운드 ON/OFF",
        "  1/2/3: 난이도 프리셋",
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
        "  마우스 드래그: 자석 이동",
        "  F: 자석 N/S 뒤집기",
        "  SPACE: 초전도 ON/OFF (온도 변화)",
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
            hint = font.render("F1: Help", True, (88, 91, 112))
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
        close = font.render("Press F1 or ESC to close", True, (88, 91, 112))
        screen.blit(close, (box_x + box_w // 2 - close.get_width() // 2, box_y + box_h - 24))
