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
            "title": "1. Quantum Tunneling",
            "text": "입자가 에너지 장벽을 확률적으로 통과하는 현상입니다.\n고전 물리학: 에너지 부족 → 장벽 통과 불가능\n양자역학: 일정 확률로 장벽을 '터널링' 가능!\n이 시뮬레이션에서 직접 관찰해 봅시다.",
            "highlight": "center",
        },
        {
            "title": "2. Classical vs Quantum",
            "text": "고전 입자는 공처럼 벽에 튕겨 나갑니다.\n양자 입자는 '파동'으로 행동합니다.\n파동은 장벽에서 완전히 사라지지 않고,\n장벽 너머로 '스며들' 수 있습니다.",
            "highlight": "none",
        },
        {
            "title": "3. Wave Function ψ(x)",
            "text": "파동함수 ψ(x)는 입자의 존재 확률 진폭입니다.\n장벽 앞: 진행파 + 반사파 (진동)\n장벽 안: 지수 감쇠  ψ ~ e^(−κx)\n장벽 뒤: 투과파 (진폭 감소, 그러나 0이 아님!)",
            "highlight": "none",
        },
        {
            "title": "4. Tunneling Probability",
            "text": "터널링 확률 공식: P ≈ exp(−2κd)\nκ = 감쇠 상수 (장벽 높이에 비례)\nd = 장벽 두께\n→ 장벽이 두꺼울수록 확률이 지수적으로 감소!\n←/→ 키 또는 장벽 가장자리 드래그로 확인하세요.",
            "highlight": "none",
        },
        {
            "title": "5. Superposition & Bloch Sphere",
            "text": "큐비트는 |0⟩과 |1⟩ 상태를 동시에 가집니다 (중첩).\n오른쪽 블로흐 구의 벡터가 이를 시각화합니다.\nθ: |0⟩ vs |1⟩ 비율  |  φ: 위상\n마우스로 블로흐 구를 드래그하여 회전해 보세요!",
            "highlight": "none",
        },
        {
            "title": "6. Probability Interpretation",
            "text": "|ψ|² = 입자를 발견할 확률\n시행 횟수가 늘면 실측 확률 → 이론값으로 수렴합니다.\n하단 그래프에서 녹색 선이 수렴하는 과정을 관찰하세요.\n노란 점선 = 이론 확률  |  녹색 실선 = 실측 누적률",
            "highlight": "none",
        },
        {
            "title": "7. Experiment Guide",
            "text": "① 장벽 두께를 좁게 설정 → 터널링 빈번\n② 장벽을 넓히면 → 터널링 희소\n③ 시행 반복 → 누적률이 이론값으로 수렴 (대수의 법칙)\n④ 블로흐 구에서 중첩 상태 변화를 관찰\n이것이 양자역학의 확률 해석입니다!",
            "highlight": "none",
        },
        {
            "title": "8. Controls",
            "text": "클릭: 입자 재발사  |  장벽 드래그: 두께 조절\n↑↓: 속도  |  ←→: 장벽 두께  |  [/]: Sim Speed\n블로흐 구 드래그: 회전  |  1/2/3: 난이도 프리셋\nR: 리셋  |  SPACE: 일시정지  |  T: 튜토리얼 재시작",
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
