"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import math
import random

import pygame

from config_loader import cfg
from theme import get_pg_theme
from ui.slider import SliderPanel, PANEL_W
from preset_hud import PresetHUD
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from achievements import check_achievements
from replay import ReplayRecorder
from logger import get_module_logger

_log = get_module_logger("tunneling")

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 600
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (203, 166, 247)
BARRIER_CLR = (249, 226, 175)
PARTICLE_CLR = (137, 180, 250)
TUNNEL_FLASH = (166, 227, 161)  # 터널링 성공
REFLECT_CLR = (243, 139, 168)   # 반사
BLOCH_RING = (88, 91, 112)


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    global BG, TEXT_CLR, ACCENT, BARRIER_CLR, PARTICLE_CLR
    global TUNNEL_FLASH, REFLECT_CLR, BLOCH_RING
    pg = get_pg_theme()
    BG = pg.BG
    TEXT_CLR = pg.TEXT
    ACCENT = pg.ACCENT_PURPLE
    BARRIER_CLR = pg.ACCENT_YELLOW
    PARTICLE_CLR = pg.ACCENT_BLUE
    TUNNEL_FLASH = pg.GREEN       # 성공 = safe color
    REFLECT_CLR = pg.RED          # 실패 = danger color
    BLOCH_RING = pg.SUBTEXT

# ── 물리 파라미터 (config.json에서 로드) ──────────────
TUNNEL_PROB_BASE = cfg("tunneling", "tunnel_prob_base", 0.10)
PARTICLE_SPEED = cfg("tunneling", "particle_speed", 200.0)
PARTICLE_RADIUS = 10
BARRIER_WIDTH_DEFAULT = cfg("tunneling", "barrier_width_default", 12)
BARRIER_WIDTH_MIN = cfg("tunneling", "barrier_width_min", 4)
BARRIER_WIDTH_MAX = cfg("tunneling", "barrier_width_max", 200)
SUPERPOSITION_HZ = cfg("tunneling", "superposition_hz", 6.0)
TUNNEL_SPEED_BOOST = cfg("tunneling", "tunnel_speed_boost", 2.0)
_TUNNEL_DECAY = cfg("tunneling", "tunnel_decay_rate", 0.02)
_VY_RANGE = cfg("tunneling", "particle_vy_range", 60.0)
_TUNNEL_FLASH = cfg("tunneling", "tunnel_flash_sec", 0.6)
_REFLECT_FLASH = cfg("tunneling", "reflect_flash_sec", 0.4)

# ── 영역 레이아웃 ────────────────────────────────────
# 왼쪽: 터널링 시뮬레이션 | 오른쪽: 블로흐 구
SIM_LEFT, SIM_TOP = 30, 70
SIM_W, SIM_H = 520, 420
BLOCH_CX, BLOCH_CY = 730, 280
BLOCH_R = 110

# 장벽 위치 (시뮬레이션 영역 중앙)
BARRIER_X = SIM_LEFT + SIM_W // 2


def _calc_tunnel_prob(barrier_width: int) -> float:
    """벽 두께에 따른 터널링 확률 — 두꺼울수록 확률 감소.

    기본 두께(12px)에서 10 %, 두께 200px이면 ~0.5 % 수준으로 지수 감쇠.
    """
    return TUNNEL_PROB_BASE * math.exp(-_TUNNEL_DECAY * (barrier_width - BARRIER_WIDTH_DEFAULT))


# ── 입자 클래스 ──────────────────────────────────────

class QuantumParticle:
    """양자 입자 — 중첩 상태 + 터널링."""

    def __init__(self):
        self.reset()
        self.tunnel_count = 0
        self.reflect_count = 0
        self.total_attempts = 0

    def reset(self):
        """입자를 왼쪽에서 다시 발사."""
        self.x = SIM_LEFT + 40.0
        self.y = SIM_TOP + SIM_H / 2.0
        self.vx = PARTICLE_SPEED
        self.vy = (random.random() - 0.5) * _VY_RANGE  # 약간의 수직 랜덤
        self.alive = True
        self.tunneled: bool | None = None  # None=미결정, True=터널링, False=반사
        self.flash_timer = 0.0

    @property
    def qubit_state(self) -> int:
        """현재 중첩 상태에서의 '관측값' (빠르게 교차)."""
        # sin 기반 확률적 교차: 양의 반주기면 |0⟩, 음이면 |1⟩
        phase = math.sin(pygame.time.get_ticks() / 1000.0 * SUPERPOSITION_HZ * 2 * math.pi)
        return 0 if phase >= 0 else 1

    @property
    def superposition_alpha(self) -> float:
        """블로흐 구 위의 각도 (0~π): 0=|0⟩, π=|1⟩."""
        phase = math.sin(pygame.time.get_ticks() / 1000.0 * SUPERPOSITION_HZ * 2 * math.pi)
        return math.pi * (1 - phase) / 2  # 0→π 매핑

    def update(self, dt: float, barrier_width: int = BARRIER_WIDTH_DEFAULT,
               tunnel_prob: float = TUNNEL_PROB_BASE,
               speed_boost: float = TUNNEL_SPEED_BOOST):
        if not self.alive:
            return

        self.x += self.vx * dt
        self.y += self.vy * dt

        # 상하 벽 반사
        if self.y - PARTICLE_RADIUS < SIM_TOP:
            self.y = SIM_TOP + PARTICLE_RADIUS
            self.vy = abs(self.vy)
        elif self.y + PARTICLE_RADIUS > SIM_TOP + SIM_H:
            self.y = SIM_TOP + SIM_H - PARTICLE_RADIUS
            self.vy = -abs(self.vy)

        # 장벽 충돌 판정
        if self.tunneled is None and self.vx > 0:
            # 오른쪽으로 진행 중, 장벽에 도달
            if self.x + PARTICLE_RADIUS >= BARRIER_X - barrier_width / 2:
                self.total_attempts += 1
                if random.random() < tunnel_prob:
                    # 터널링 성공! 장벽 반대편으로 좌표 이동 + 속도 부스트
                    self.x = BARRIER_X + barrier_width / 2 + PARTICLE_RADIUS + 5
                    self.vx = abs(self.vx) * speed_boost
                    self.tunneled = True
                    self.tunnel_count += 1
                    self.flash_timer = _TUNNEL_FLASH
                else:
                    # 반사
                    self.vx = -abs(self.vx) * 0.8
                    self.x = BARRIER_X - barrier_width / 2 - PARTICLE_RADIUS - 2
                    self.tunneled = False
                    self.reflect_count += 1
                    self.flash_timer = _REFLECT_FLASH

        # 화면 밖으로 나가면 재발사
        if self.x < SIM_LEFT - 20 or self.x > SIM_LEFT + SIM_W + 20:
            self.reset()

        if self.flash_timer > 0:
            self.flash_timer -= dt


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_sim_area(screen, font, barrier_width: int = BARRIER_WIDTH_DEFAULT):
    """시뮬레이션 영역 배경."""
    pygame.draw.rect(screen, (24, 24, 37), (SIM_LEFT, SIM_TOP, SIM_W, SIM_H))
    pygame.draw.rect(screen, (69, 71, 90), (SIM_LEFT, SIM_TOP, SIM_W, SIM_H), 1)

    # 장벽
    bx = BARRIER_X - barrier_width // 2
    pygame.draw.rect(screen, BARRIER_CLR, (bx, SIM_TOP, barrier_width, SIM_H))

    # 장벽 라벨
    label = font.render("BARRIER", True, BG)
    label_rot = pygame.transform.rotate(label, 90)
    screen.blit(label_rot, (bx - 2, SIM_TOP + SIM_H // 2 - label_rot.get_height() // 2))

    # 영역 라벨
    left_label = font.render("Classical Region", True, (69, 71, 90))
    screen.blit(left_label, (SIM_LEFT + 10, SIM_TOP + 5))
    right_label = font.render("Tunneled Region", True, (69, 71, 90))
    screen.blit(right_label, (BARRIER_X + 20, SIM_TOP + 5))


def _draw_particle(screen, p: QuantumParticle, font):
    """입자 렌더링."""
    cx, cy = int(p.x), int(p.y)

    # 터널링/반사 플래시
    if p.flash_timer > 0:
        flash_r = int(PARTICLE_RADIUS + 20 * p.flash_timer)
        flash_clr = TUNNEL_FLASH if p.tunneled else REFLECT_CLR
        glow = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
        alpha = int(120 * p.flash_timer)
        pygame.draw.circle(glow, (*flash_clr, alpha), (flash_r, flash_r), flash_r)
        screen.blit(glow, (cx - flash_r, cy - flash_r))

    # 입자 본체 — 터널링 성공 시 흰색, 평상시 파랑
    color = (255, 255, 255) if (p.tunneled is True and p.flash_timer > 0) else PARTICLE_CLR
    pygame.draw.circle(screen, color, (cx, cy), PARTICLE_RADIUS)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), PARTICLE_RADIUS, 1)

    # 중첩 |0⟩/|1⟩ 텍스트
    state_text = f"|{p.qubit_state}⟩"
    surf = font.render(state_text, True, (255, 255, 255))
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


def _draw_bloch_sphere(screen, p: QuantumParticle, font, title_font):
    """블로흐 구 시각화."""
    # 타이틀
    label = title_font.render("Bloch Sphere", True, ACCENT)
    screen.blit(label, (BLOCH_CX - label.get_width() // 2, BLOCH_CY - BLOCH_R - 40))

    # 구 외곽 (원)
    pygame.draw.circle(screen, BLOCH_RING, (BLOCH_CX, BLOCH_CY), BLOCH_R, 1)

    # 적도 타원
    pygame.draw.ellipse(
        screen, BLOCH_RING,
        (BLOCH_CX - BLOCH_R, BLOCH_CY - BLOCH_R // 4, BLOCH_R * 2, BLOCH_R // 2),
        1,
    )

    # 축
    pygame.draw.line(screen, (69, 71, 90), (BLOCH_CX, BLOCH_CY - BLOCH_R - 8), (BLOCH_CX, BLOCH_CY + BLOCH_R + 8), 1)

    # |0⟩, |1⟩ 라벨
    z0 = font.render("|0⟩", True, TUNNEL_FLASH)
    z1 = font.render("|1⟩", True, REFLECT_CLR)
    screen.blit(z0, (BLOCH_CX + 8, BLOCH_CY - BLOCH_R - 18))
    screen.blit(z1, (BLOCH_CX + 8, BLOCH_CY + BLOCH_R + 4))

    # 상태 벡터 (θ 기반)
    theta = p.superposition_alpha
    tip_x = BLOCH_CX + int(BLOCH_R * 0.4 * math.sin(theta))
    tip_y = BLOCH_CY - int(BLOCH_R * math.cos(theta))

    pygame.draw.line(screen, ACCENT, (BLOCH_CX, BLOCH_CY), (tip_x, tip_y), 2)
    pygame.draw.circle(screen, ACCENT, (tip_x, tip_y), 6)

    # 현재 상태 텍스트
    state_label = f"|{'0' if theta < math.pi / 2 else '1'}⟩  θ={math.degrees(theta):.0f}°"
    sl = font.render(state_label, True, TEXT_CLR)
    screen.blit(sl, (BLOCH_CX - sl.get_width() // 2, BLOCH_CY + BLOCH_R + 26))


def _draw_stats(screen, p: QuantumParticle, font, tunnel_prob: float = TUNNEL_PROB_BASE):
    """통계 패널."""
    stats_x = BLOCH_CX - BLOCH_R
    stats_y = BLOCH_CY + BLOCH_R + 60

    lines = [
        f"총 시도: {p.total_attempts}",
        f"터널링: {p.tunnel_count}  ({(p.tunnel_count / max(p.total_attempts, 1) * 100):.1f}%)",
        f"반사:   {p.reflect_count}  ({(p.reflect_count / max(p.total_attempts, 1) * 100):.1f}%)",
        f"현재 확률: {tunnel_prob * 100:.1f}%",
    ]
    for i, line in enumerate(lines):
        color = TUNNEL_FLASH if "터널링" in line else REFLECT_CLR if "반사" in line else TEXT_CLR
        surf = font.render(line, True, color)
        screen.blit(surf, (stats_x, stats_y + i * 17))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
    pygame.display.set_caption("Quantum Superposition & Tunneling")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    title_font = pygame.font.SysFont("Consolas", 16, bold=True)
    big_font = pygame.font.SysFont("Consolas", 18, bold=True)

    particle = QuantumParticle()
    paused = False

    # ── 슬라이더 패널 ─────────────────────────────────
    panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_speed = panel.add(0.5, 5.0, 1.0, 0.5, "Speed Mult", ".1f")
    sl_barrier = panel.add(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX, BARRIER_WIDTH_DEFAULT, 2, "Barrier W", ".0f")
    sl_boost = panel.add(1.0, 5.0, TUNNEL_SPEED_BOOST, 0.5, "Tunnel Boost", ".1f")

    # ── 프리셋 HUD ──
    slider_map = {
        ("tunneling", "tunnel_prob_base"): sl_speed,
        ("tunneling", "barrier_width_default"): sl_barrier,
        ("tunneling", "tunnel_speed_boost"): sl_boost,
    }
    preset_hud = PresetHUD("tunneling", slider_map)
    help_overlay = HelpOverlay("tunneling")

    # ── 사운드 ──
    snd = get_sound_manager()
    snd.init()

    # ── 리플레이 ──
    recorder = ReplayRecorder("tunneling")

    barrier_width = BARRIER_WIDTH_DEFAULT
    tunnel_prob = _calc_tunnel_prob(barrier_width)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            panel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    particle = QuantumParticle()
                    panel.reset_all()
                elif event.key == pygame.K_UP:
                    sl_speed.value = sl_speed.value + 0.5
                elif event.key == pygame.K_DOWN:
                    sl_speed.value = sl_speed.value - 0.5
                elif event.key == pygame.K_RIGHT:
                    sl_barrier.value = sl_barrier.value + 10
                elif event.key == pygame.K_LEFT:
                    sl_barrier.value = sl_barrier.value - 10
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 클릭으로 입자 재발사
                particle.reset()

        # ── 슬라이더 값 읽기 ─────────────────────────
        speed_mult = sl_speed.value
        barrier_width = int(sl_barrier.value)
        tunnel_prob = _calc_tunnel_prob(barrier_width)

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            orig_vx = particle.vx
            particle.vx = orig_vx * speed_mult if orig_vx > 0 else orig_vx
            particle.update(dt, barrier_width, tunnel_prob, sl_boost.value)
            particle.vx = orig_vx  # 속도 배율은 화면용, 내부 상태 보존

            # ── 사운드 ──
            if particle.tunneled is True and particle.flash_timer > 0.5:
                snd.play("tunnel_success")
            elif particle.tunneled is False and particle.flash_timer > 0.3:
                snd.play("tunnel_reflect")

            preset_hud.update(dt)

            recorder.record_frame({
                "x": round(particle.x, 1),
                "tunneled": particle.tunneled,
                "attempts": particle.total_attempts,
                "tunnels": particle.tunnel_count,
            })

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        t_surf = big_font.render("Quantum Superposition & Tunneling", True, ACCENT)
        screen.blit(t_surf, (WIDTH // 2 - t_surf.get_width() // 2, 12))

        # 시뮬레이션 영역
        _draw_sim_area(screen, font, barrier_width)

        # 입자
        _draw_particle(screen, particle, font)

        # 블로흐 구
        _draw_bloch_sphere(screen, particle, font, title_font)

        # 통계
        _draw_stats(screen, particle, font, tunnel_prob)

        # 슬라이더 패널 그리기
        panel.draw(screen, font)

        # 안내
        hints = [
            f"속도: x{speed_mult:.1f}  |  벽 두께: {barrier_width}px  |  확률: {tunnel_prob*100:.1f}%  |  {'일시정지' if paused else '실행 중'}",
            "클릭: 재발사  |  ↑↓/←→: 파라미터  |  우측 패널: 슬라이더",
            "SPACE: 일시정지  |  R: 리셋  |  ESC: 종료",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (SIM_LEFT, HEIGHT - 52 + i * 16))

        preset_hud.draw(screen, font)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    # 최종미션: 플레이 기록 저장
    try:
        from data_ai.play_logger import get_logger
        rate = particle.tunnel_count / max(particle.total_attempts, 1)
        get_logger().log_session("tunneling", {
            "total_attempts": particle.total_attempts,
            "tunnel_count": particle.tunnel_count,
            "reflect_count": particle.reflect_count,
            "tunnel_rate": round(rate, 3),
            "barrier_width": barrier_width,
            "tunnel_prob": round(tunnel_prob, 3),
        })
    except Exception as e:
        _log.error("플레이 기록 실패: %s", e)

    try:
        from report import generate_report
        generate_report("tunneling", {
            "total_attempts": particle.total_attempts,
            "tunnel_count": particle.tunnel_count,
            "reflect_count": particle.reflect_count,
            "tunnel_rate": round(rate, 3),
            "barrier_width": barrier_width,
        })
    except Exception as e:
        _log.error("보고서 생성 실패: %s", e)

    try:
        check_achievements("tunneling", {
            "tunnel_count": particle.tunnel_count,
            "tunnel_rate": round(rate, 3),
            "total_attempts": particle.total_attempts,
        })
    except Exception as e:
        _log.error("업적 확인 실패: %s", e)

    recorder.save()
    snd.quit()

    pygame.quit()


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
