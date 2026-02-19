"""인게임 튜토리얼 오버레이 — 스텝 바이 스텝 가이드.

각 Pygame 게임 모듈에서 첫 플레이 시 (또는 T 키로) 활성화.
단계별로 조작법과 물리 개념을 설명합니다.

사용법:
    from tutorial import TutorialOverlay
    tutorial = TutorialOverlay("qubit_chain")

    # 이벤트 루프:
    if tutorial.handle_event(event):
        continue  # 이벤트 소비됨

    # 렌더링 (맨 마지막):
    tutorial.draw(screen, font)
"""

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

import json
import os

from i18n import t
from logger import get_module_logger

_log = get_module_logger("tutorial")
_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tutorial_state.json")

# 모듈별 튜토리얼 스텝
_TUTORIAL_STEPS: dict[str, list[dict]] = {
    "qubit_chain": [
        {
            "title": "Welcome to Qubit Cascade!",
            "text": "초전도 큐비트 7개가 얽힘으로 연결되어 있습니다.\n외부 노이즈가 큐비트를 불안정하게 만듭니다.",
            "highlight": "center",
        },
        {
            "title": "Step 1: Error Correction",
            "text": "큐비트를 클릭하면 stress가 0으로 초기화됩니다.\n빨간색으로 변하기 전에 클릭하세요!",
            "highlight": "click",
        },
        {
            "title": "Step 2: QEC Shield",
            "text": "S 키를 누르면 QEC 방어막이 활성화됩니다.\n노이즈와 연쇄 데미지가 크게 감소합니다.",
            "highlight": "shield",
        },
        {
            "title": "Step 3: Healing",
            "text": "H 키를 누르면 모든 큐비트의 stress가 감소합니다.\n쿨다운이 있으니 타이밍을 맞추세요!",
            "highlight": "heal",
        },
        {
            "title": "Step 4: Presets",
            "text": "1/2/3 키로 난이도를 바꿀 수 있습니다.\n1=Easy, 2=Normal, 3=Hard",
            "highlight": "preset",
        },
        {
            "title": "Goal: Survive!",
            "text": "모든 큐비트가 붕괴하면 게임 오버입니다.\n최대한 오래 생존하세요! R 키로 리셋 가능.",
            "highlight": "none",
        },
    ],
    "tunneling": [
        {
            "title": "Quantum Tunneling",
            "text": "입자가 에너지 장벽을 확률적으로 통과합니다.\n고전 물리에서는 불가능하지만 양자역학에서는 가능!",
            "highlight": "center",
        },
        {
            "title": "Controls",
            "text": "클릭: 입자 재발사\nUp/Down: 속도 조절\nLeft/Right: 장벽 두께",
            "highlight": "none",
        },
    ],
    "qkd_advanced": [
        {
            "title": "Advanced QKD Protocols",
            "text": "E91(얽힘 기반), 키 시프팅/프라이버시 증폭,\n다자간 QKD(GHZ), BB84 vs E91 비교를 실험합니다.",
            "highlight": "center",
        },
        {
            "title": "E91 Protocol",
            "text": "EPR 벨 쌍으로 양자 키를 분배합니다.\n벨 부등식(S>2)으로 도청 여부를 검증합니다!",
            "highlight": "none",
        },
        {
            "title": "OTP Encryption Demo",
            "text": "PA 완료 후 최종 키로 XOR 암호화 시연!\nQKD → 실용 암호(One-Time Pad) 연결을 확인하세요.",
            "highlight": "none",
        },
        {
            "title": "Multi-Party GHZ (3~5)",
            "text": "GHZ 모드에서 Up/Down 키로 파티 수를 변경합니다.\n3→4→5자간 얽힘 네트워크를 확장할 수 있습니다!",
            "highlight": "none",
        },
        {
            "title": "BB84 vs E91 Compare",
            "text": "같은 Eve 조건에서 BB84(QBER)와 E91(Bell)\n두 탐지 방식의 차이를 실시간 비교합니다.",
            "highlight": "none",
        },
        {
            "title": "Controls",
            "text": "SPACE: 배치 실행  |  Tab: 모드 전환  |  E: Eve 토글\nS: 키 시프팅  |  A: 자동  |  R: 리셋  |  Up/Down: 파티 수",
            "highlight": "none",
        },
    ],
    "bb84_defense": [
        {
            "title": "BB84 Quantum Key Distribution",
            "text": "Alice가 Bob에게 양자 키를 전송합니다.\nEve(도청자)가 중간에서 도청을 시도합니다!",
            "highlight": "center",
        },
        {
            "title": "Defense",
            "text": "SPACE: 통신망 폐쇄/재개\nA: 자동차단 ON/OFF\n에러율이 높으면 Eve가 도청 중입니다!",
            "highlight": "none",
        },
    ],
    "squid_mines": [
        {
            "title": "SQUID Magnetic Sensor",
            "text": "SQUID 센서로 숨겨진 자기 지뢰를 찾으세요.\n마우스를 움직이면 자기 선속이 변합니다.",
            "highlight": "center",
        },
        {
            "title": "Detection",
            "text": "클릭: 지뢰 마킹\nUp/Down: 민감도 조절\n그래프를 잘 관찰하세요!",
            "highlight": "none",
        },
    ],
    "scada_security": [
        {
            "title": "SCADA Security Scenario",
            "text": "SCADA 시스템이 MITM(중간자) 공격을 받습니다.\n공격자가 센서 데이터를 조작하여 시스템을 속입니다.",
            "highlight": "center",
        },
        {
            "title": "BB84 QKD Defense",
            "text": "BB84 양자 키 분배로 QBER을 모니터링합니다.\nQBER > 11% → 공격 탐지 → 양자 인증 채널 구축!",
            "highlight": "none",
        },
        {
            "title": "Controls",
            "text": "SPACE: 수동 공격/방어  |  A: 자동 시나리오 토글\nQ: QKD 토글  |  P: 일시정지  |  R: 리셋",
            "highlight": "none",
        },
    ],
    "entanglement": [
        {
            "title": "Quantum Entanglement",
            "text": "벨 상태, CHSH 부등식, 양자 텔레포테이션을\n직접 실험해 볼 수 있습니다.",
            "highlight": "center",
        },
        {
            "title": "3 Modes",
            "text": "Tab 키로 모드를 전환합니다:\n1) Bell States  2) CHSH  3) Teleportation",
            "highlight": "none",
        },
        {
            "title": "Bell States",
            "text": "1-4 키로 4종 벨 상태를 선택하고\nSPACE로 측정하여 상관관계를 확인하세요!",
            "highlight": "none",
        },
    ],
    "qec_shield": [
        {
            "title": "QEC Shield — Error Correction",
            "text": "양자 오류 정정(QEC) 방어막으로 큐비트 네트워크를\n노이즈로부터 보호하는 시뮬레이션입니다.",
            "highlight": "center",
        },
        {
            "title": "Shield & Heal",
            "text": "S: QEC 방어막 활성화 (노이즈 감소)\nH: 전체 큐비트 힐링 (stress 감소)",
            "highlight": "none",
        },
        {
            "title": "Compare Mode",
            "text": "C: 비교 모드 (QEC/Heal 비활성화)\nQEC 없이 버틴 시간 vs QEC 사용 비교!",
            "highlight": "none",
        },
        {
            "title": "Controls",
            "text": "Left/Right: QEC 감쇠 계수 조절\nR: 리셋  |  SPACE: 일시정지\n1/2/3: 난이도 프리셋",
            "highlight": "none",
        },
    ],
    "gate_builder": [
        {
            "title": "Quantum Gate Builder",
            "text": "양자 회로를 시각적으로 구성하고\n실시간으로 상태 벡터를 확인합니다.",
            "highlight": "center",
        },
        {
            "title": "Build a Circuit",
            "text": "팔레트에서 게이트를 클릭 → 와이어를 클릭하여 배치\nCNOT은 제어-타겟 큐비트 자동 연결!",
            "highlight": "none",
        },
        {
            "title": "Measurement",
            "text": "Enter: 측정 실행 (히스토그램 갱신)\nTab: 블로흐 구 표시 큐비트 전환\nBackspace: 마지막 게이트 제거",
            "highlight": "none",
        },
    ],
    "grover_search": [
        {
            "title": "Grover's Search Algorithm",
            "text": "정렬되지 않은 데이터베이스에서 원하는 항목을\n양자 컴퓨터로 빠르게 찾는 알고리즘입니다.",
            "highlight": "center",
        },
        {
            "title": "Step 1: Superposition",
            "text": "Hadamard 게이트로 모든 큐비트를 균등 중첩 상태로\n만듭니다. 모든 상태가 동일한 확률을 가집니다.",
            "highlight": "none",
        },
        {
            "title": "Step 2: Oracle",
            "text": "오라클이 정답 상태의 위상을 반전합니다.\n|x⟩ → −|x⟩ (정답인 경우만)",
            "highlight": "none",
        },
        {
            "title": "Step 3: Diffusion",
            "text": "진폭 증폭(Amplitude Amplification)으로\n정답 상태의 확률을 높입니다.",
            "highlight": "none",
        },
        {
            "title": "Optimal Iterations",
            "text": "반복 횟수 ≈ π/4 × √(N/M)\n너무 많이 반복하면 오히려 확률이 줄어듭니다!",
            "highlight": "none",
        },
        {
            "title": "Quantum Advantage",
            "text": "고전 탐색: O(N) 쿼리 / 양자 탐색: O(√N) 쿼리\n→ 2차 속도 향상(Quadratic Speedup)!",
            "highlight": "none",
        },
        {
            "title": "3 Modes",
            "text": "Tab 키로 모드를 전환합니다:\n1) Step-by-Step  2) Auto Run  3) Compare Race",
            "highlight": "none",
        },
        {
            "title": "Controls",
            "text": "SPACE: 다음 단계/시작  |  N: 새 탐색  |  R: 리셋\nTab: 모드 전환  |  ↑↓: 속도/DB 크기",
            "highlight": "none",
        },
    ],
}


def _load_progress() -> dict:
    """튜토리얼 진행 상태 로드.

    반환 형식: {"module": {"completed": bool, "step": int}, ...}
    레거시 형식(리스트)도 호환.
    """
    if os.path.exists(_SAVE_PATH):
        try:
            with open(_SAVE_PATH) as f:
                data = json.load(f)
            # 레거시 호환: 리스트 → dict 변환
            if isinstance(data, list):
                return {m: {"completed": True, "step": 0} for m in data}
            return data
        except (OSError, json.JSONDecodeError, TypeError) as e:
            _log.warning("튜토리얼 상태 로드 실패: %s", e)
    return {}


def _save_progress(progress: dict):
    try:
        with open(_SAVE_PATH, "w") as f:
            json.dump(progress, f, indent=2)
    except OSError as e:
        _log.warning("튜토리얼 상태 저장 실패: %s", e)


class TutorialOverlay:
    """스텝 바이 스텝 튜토리얼 오버레이."""

    def __init__(self, module_name: str, auto_show: bool = True):
        self.module_name = module_name
        self.steps = _TUTORIAL_STEPS.get(module_name, [])
        self.current_step = 0
        self.visible = False
        self._completed = False

        if auto_show and self.steps:
            progress = _load_progress()
            mod_state = progress.get(module_name, {})
            if mod_state.get("completed"):
                self._completed = True
            else:
                self.visible = True
                # 이전 진행률에서 이어서 시작
                saved_step = mod_state.get("step", 0)
                if 0 < saved_step < len(self.steps):
                    self.current_step = saved_step

    def handle_event(self, event) -> bool:
        """이벤트 처리. T 키로 토글, Enter/Space로 다음 스텝."""
        if pygame is None:
            return False

        if event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_t and not self.visible:
            self.visible = True
            self.current_step = 0
            return True

        if not self.visible:
            return False

        if event.key in (pygame.K_RETURN, pygame.K_RIGHT, pygame.K_SPACE):
            self.current_step += 1
            if self.current_step >= len(self.steps):
                self._finish()
            else:
                self._save_step()
            return True

        if event.key == pygame.K_LEFT:
            self.current_step = max(0, self.current_step - 1)
            self._save_step()
            return True

        if event.key == pygame.K_ESCAPE:
            self._finish()
            return True

        return False

    def _save_step(self):
        """현재 진행 단계 저장."""
        progress = _load_progress()
        progress[self.module_name] = {
            "completed": False,
            "step": self.current_step,
        }
        _save_progress(progress)

    def _finish(self):
        """튜토리얼 완료."""
        self.visible = False
        self._completed = True
        progress = _load_progress()
        progress[self.module_name] = {
            "completed": True,
            "step": len(self.steps),
        }
        _save_progress(progress)

    def draw(self, screen, font):
        """튜토리얼 오버레이 렌더링."""
        if not self.visible or not self.steps or pygame is None:
            return

        w, h = screen.get_size()
        step = self.steps[self.current_step]

        # 반투명 배경
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # 박스
        box_w, box_h = min(500, w - 40), min(200, h - 40)
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2

        pygame.draw.rect(screen, (30, 30, 46), (box_x, box_y, box_w, box_h), border_radius=12)
        pygame.draw.rect(screen, (137, 180, 250), (box_x, box_y, box_w, box_h), 2, border_radius=12)

        # 스텝 표시
        step_text = f"Step {self.current_step + 1}/{len(self.steps)}"
        step_surf = font.render(step_text, True, (88, 91, 112))
        screen.blit(step_surf, (box_x + box_w - step_surf.get_width() - 12, box_y + 10))

        # 타이틀
        title_surf = font.render(step["title"], True, (249, 226, 175))
        screen.blit(title_surf, (box_x + 16, box_y + 10))

        # 본문
        lines = step["text"].split("\n")
        for i, line in enumerate(lines):
            line_surf = font.render(line, True, (205, 214, 244))
            screen.blit(line_surf, (box_x + 16, box_y + 36 + i * 18))

        # 네비게이션 힌트
        nav = t("tutorial_nav_hint")
        nav_surf = font.render(nav, True, (88, 91, 112))
        screen.blit(nav_surf, (box_x + box_w // 2 - nav_surf.get_width() // 2, box_y + box_h - 22))
