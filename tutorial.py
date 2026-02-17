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

from logger import get_module_logger

_log = get_module_logger("tutorial")
_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tutorial_state.json")

# 모듈별 튜토리얼 스텝
_TUTORIAL_STEPS: dict[str, list[dict]] = {
    "qubit_chain": [
        {"title": "Welcome to Qubit Cascade!",
         "text": "초전도 큐비트 7개가 얽힘으로 연결되어 있습니다.\n외부 노이즈가 큐비트를 불안정하게 만듭니다.",
         "highlight": "center"},
        {"title": "Step 1: Error Correction",
         "text": "큐비트를 클릭하면 stress가 0으로 초기화됩니다.\n빨간색으로 변하기 전에 클릭하세요!",
         "highlight": "click"},
        {"title": "Step 2: QEC Shield",
         "text": "S 키를 누르면 QEC 방어막이 활성화됩니다.\n노이즈와 연쇄 데미지가 크게 감소합니다.",
         "highlight": "shield"},
        {"title": "Step 3: Healing",
         "text": "H 키를 누르면 모든 큐비트의 stress가 감소합니다.\n쿨다운이 있으니 타이밍을 맞추세요!",
         "highlight": "heal"},
        {"title": "Step 4: Presets",
         "text": "1/2/3 키로 난이도를 바꿀 수 있습니다.\n1=Easy, 2=Normal, 3=Hard",
         "highlight": "preset"},
        {"title": "Goal: Survive!",
         "text": "모든 큐비트가 붕괴하면 게임 오버입니다.\n최대한 오래 생존하세요! R 키로 리셋 가능.",
         "highlight": "none"},
    ],
    "tunneling": [
        {"title": "Quantum Tunneling",
         "text": "입자가 에너지 장벽을 확률적으로 통과합니다.\n고전 물리에서는 불가능하지만 양자역학에서는 가능!",
         "highlight": "center"},
        {"title": "Controls",
         "text": "클릭: 입자 재발사\nUp/Down: 속도 조절\nLeft/Right: 장벽 두께",
         "highlight": "none"},
    ],
    "bb84_defense": [
        {"title": "BB84 Quantum Key Distribution",
         "text": "Alice가 Bob에게 양자 키를 전송합니다.\nEve(도청자)가 중간에서 도청을 시도합니다!",
         "highlight": "center"},
        {"title": "Defense",
         "text": "SPACE: 통신망 폐쇄/재개\nA: 자동차단 ON/OFF\n에러율이 높으면 Eve가 도청 중입니다!",
         "highlight": "none"},
    ],
    "squid_mines": [
        {"title": "SQUID Magnetic Sensor",
         "text": "SQUID 센서로 숨겨진 자기 지뢰를 찾으세요.\n마우스를 움직이면 자기 선속이 변합니다.",
         "highlight": "center"},
        {"title": "Detection",
         "text": "클릭: 지뢰 마킹\nUp/Down: 민감도 조절\n그래프를 잘 관찰하세요!",
         "highlight": "none"},
    ],
}


def _load_seen() -> set[str]:
    """이미 본 튜토리얼 모듈 목록."""
    if os.path.exists(_SAVE_PATH):
        try:
            with open(_SAVE_PATH, "r") as f:
                return set(json.load(f))
        except (OSError, json.JSONDecodeError, TypeError) as e:
            _log.warning("튜토리얼 상태 로드 실패: %s", e)
    return set()


def _save_seen(seen: set[str]):
    try:
        with open(_SAVE_PATH, "w") as f:
            json.dump(sorted(seen), f)
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
            seen = _load_seen()
            if module_name not in seen:
                self.visible = True

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
            return True

        if event.key == pygame.K_LEFT:
            self.current_step = max(0, self.current_step - 1)
            return True

        if event.key == pygame.K_ESCAPE:
            self._finish()
            return True

        return False

    def _finish(self):
        """튜토리얼 완료."""
        self.visible = False
        self._completed = True
        seen = _load_seen()
        seen.add(self.module_name)
        _save_seen(seen)

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
        nav = "Enter/Right: Next  |  Left: Previous  |  ESC: Skip"
        nav_surf = font.render(nav, True, (88, 91, 112))
        screen.blit(nav_surf, (box_x + box_w // 2 - nav_surf.get_width() // 2, box_y + box_h - 22))
