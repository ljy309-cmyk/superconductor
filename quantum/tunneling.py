"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import os
import time
from collections import deque

import pygame

from achievement_toast import AchievementToast
from achievements import check_achievements
from config_loader import cfg
from difficulty_dialog import choose_difficulty
from font_helper import get_font
from game_base import choose_difficulty_or_quit, finalize_session
from glossary import GlossaryOverlay
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from preset_hud import PresetHUD
from quantum.tunneling_experiment import (
    get_dataset_ids,
)

# ── 물리 엔진 (순수 로직) ────────────────────────────
from quantum.tunneling_physics import (
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    TRIAL_HISTORY_MAX,
    TUNNEL_PROB_BASE,
    TUNNEL_SPEED_BOOST,
    BarrierSweeper,
    QuantumParticle,
    _calc_tunnel_prob,
)

# ── 렌더링 (분리 모듈) ──────────────────────────────
from quantum.tunneling_render import (
    BG,
    BLOCH_CX,
    BLOCH_CY,
    BLOCH_R,
    FPS,
    HEIGHT,
    REFLECT_CLR,
    TEXT_CLR,
    TUNNEL_FLASH,
    WIDTH,
    ACCENT,
    _CHART_H,
    _CHART_W,
    _CHART_X,
    _CHART_Y,
    _FORMULA_H,
    _FORMULA_W,
    _FORMULA_X,
    _FORMULA_Y,
    _BlochMeshCache,
    _CIRCLE_STEPS,
    _EQUATOR_PTS,
    _MAX_TRAILS,
    _MERIDIAN_XZ,
    _MERIDIAN_YZ,
    _TextCache,
    _TRAIL_SAMPLE,
    _TrailCache,
    _draw_achievement_progress,
    _draw_bloch_sphere,
    _draw_energy_diagram,
    _draw_experiment_chart,
    _draw_formula_overlay,
    _draw_particle,
    _draw_rate_chart,
    _draw_sim_area,
    _draw_stats,
    _draw_sweep_chart,
    _draw_trails,
    _draw_wavefunction,
    _ease_out,
    _flash_ease,
    _load_theme_colors,
    _tcache,
    _update_exp_fit_stats,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from sound_manager import get_sound_manager
from theme import on_theme_change
from tutorial import TutorialOverlay
from ui.slider import PANEL_W, SliderPanel

_log = get_module_logger("tunneling")

# ── 장벽 드래그 ──────────────────────────────────────
_BARRIER_EDGE_TOL = 8  # 장벽 가장자리 감지 허용 범위 (px)

# ── 블로흐 구 인터랙션 ──────────────────────────────
_BLOCH_EL_DEFAULT = 0.25  # 기본 기울기 (rad) — 약 14°
_BLOCH_EL_MIN, _BLOCH_EL_MAX = -1.0, 1.0
_BLOCH_DRAG_SENSITIVITY = 0.008  # 마우스 픽셀 → 라디안
_BLOCH_KEY_STEP = 0.08  # 키보드 한 번 누름 → 라디안 (#24)


# ── 업적 진행도 ──────────────────────────────────────


def _build_progress_snapshot(ctx) -> dict:
    """실시간 업적 평가용 세션 데이터 스냅샷."""
    p = ctx.particle
    elapsed = time.monotonic() - ctx.start_time
    return {
        "tunnel_count": p.tunnel_count,
        "total_attempts": p.total_attempts,
        "tunnel_rate": p.tunnel_count / max(p.total_attempts, 1),
        "tunnel_prob": ctx.tunnel_prob,
        "elapsed_time": elapsed,
        "max_tunnel_barrier": ctx.max_tunnel_barrier,
        "barrier_configs_tried": len(ctx.barrier_configs_tried),
    }


def _check_realtime_achievements(ctx):
    """시행 발생 시 업적 확인 → 토스트 표시 + 효과음."""
    snap = _build_progress_snapshot(ctx)
    new_ach = check_achievements("tunneling", snap)
    for ach in new_ach:
        if ach["id"] not in ctx.unlocked_ids:
            ctx.unlocked_ids.add(ach["id"])
            ctx.toast.show(ach)
            ctx.snd.play("achievement")


# ── 시뮬레이션 상태 번들 ──────────────────────────────


class _SimContext:
    """run_simulation 내부 상태를 하나로 묶는 컨테이너."""

    def __init__(self):
        _log.info("터널링 시뮬레이션 시작")
        _load_theme_colors()
        on_theme_change(_load_theme_colors)
        pygame.init()

        self.screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
        pygame.display.set_caption(t("game_title_tunneling"))
        self.clock = pygame.time.Clock()
        self.font = get_font(12)
        self.title_font = get_font(16, bold=True)
        self.big_font = get_font(18, bold=True)

        self.particle = QuantumParticle()
        self.paused = False

        # 블로흐 구 인터랙션
        self.bloch_phi = 0.0
        self.bloch_el = _BLOCH_EL_DEFAULT
        self.bloch_dragging = False
        self.bloch_drag_prev = (0, 0)

        # 장벽 드래그
        self.barrier_dragging = False
        self.barrier_hover = False

        # 입자 궤적 잔상
        self.trails: list[tuple[list[tuple[int, int]], bool]] = []
        self.current_trail: list[tuple[int, int]] = []
        self.trail_frame = 0
        self.prev_tunneled_state: bool | None = None
        self.trail_cache = _TrailCache()

        # 슬라이더 패널
        self.panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
        self.sl_prob = self.panel.add(0.01, 0.50, TUNNEL_PROB_BASE, 0.01, "Base Prob", ".2f")
        self.sl_speed = self.panel.add(0.5, 5.0, 1.0, 0.5, "Speed Mult", ".1f")
        self.sl_barrier = self.panel.add(
            BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX, BARRIER_WIDTH_DEFAULT, 2, "Barrier W", ".0f"
        )
        self.sl_boost = self.panel.add(1.0, 5.0, TUNNEL_SPEED_BOOST, 0.5, "Tunnel Boost", ".1f")

        # 프리셋 HUD / 오버레이
        slider_map = {
            ("tunneling", "tunnel_prob_base"): self.sl_prob,
            ("tunneling", "barrier_width_default"): self.sl_barrier,
            ("tunneling", "tunnel_speed_boost"): self.sl_boost,
        }
        self.preset_hud = PresetHUD("tunneling", slider_map)
        self.help_overlay = HelpOverlay("tunneling")
        self.tutorial = TutorialOverlay("tunneling")
        self.glossary = GlossaryOverlay()

        # 사운드 / 리플레이
        self.snd = get_sound_manager()
        self.snd.init()
        self.recorder = ReplayRecorder("tunneling")

        # 물리 상태
        self.barrier_width = BARRIER_WIDTH_DEFAULT
        self.base_prob = TUNNEL_PROB_BASE
        self.tunnel_prob = _calc_tunnel_prob(self.barrier_width, self.base_prob)
        self.speed_mult = 1.0

        # 세션 통계
        self.start_time = time.monotonic()
        self.max_tunnel_barrier = 0
        self.barrier_configs_tried: set[int] = set()
        self.trial_history: deque[dict] = deque(maxlen=TRIAL_HISTORY_MAX)
        self.peak_rate = 0.0
        self.prev_attempts = 0

        # 업적 토스트 + 실시간 추적
        self.toast = AchievementToast()
        self.unlocked_ids: set[str] = set()

        # 가져온 비교 데이터 (Ctrl+I)
        self.imported_trials: list[dict] | None = None
        self.imported_label: str = ""

        # 배리어 스위퍼 (#29)
        self.sweeper: BarrierSweeper | None = None

        # 스텝별 실행 모드 (#30)
        self.step_mode = False
        self.step_pending = False  # N 키로 한 프레임 진행 요청
        self.step_count = 0  # 스텝 모드에서 진행한 총 프레임 수
        self.step_dt = 0.0  # 마지막 스텝의 dt 값

        # 되감기 (#31)
        rewind_sec = cfg("tunneling", "rewind_seconds", 5)
        self.rewind_buf: deque[dict] = deque(maxlen=int(FPS * rewind_sec))
        self.rewinding = False  # 되감기 재생 중 여부
        self.rewind_speed = cfg("tunneling", "rewind_speed", 2)  # 되감기 배속

        # 실험 데이터 비교 (#32)
        self.exp_compare_visible = False  # 비교 패널 표시 여부
        ds_ids = get_dataset_ids()
        self.exp_dataset_id: str = ds_ids[0] if ds_ids else ""
        self.exp_fit_stats: dict | None = None  # 최근 적합도 계산 결과

    def read_sliders(self):
        """슬라이더 값 → 물리 파라미터 동기화."""
        self.speed_mult = self.sl_speed.value
        self.barrier_width = int(self.sl_barrier.value)
        self.base_prob = self.sl_prob.value
        self.tunnel_prob = _calc_tunnel_prob(self.barrier_width, self.base_prob)
        self.barrier_configs_tried.add(self.barrier_width)


# ── 중간 난이도 전환 ──────────────────────────────────


def _switch_difficulty_midgame(ctx: _SimContext):
    """플레이 중 난이도 다이얼로그를 열어 프리셋 전환.

    ESC 시 기존 난이도 유지, 선택 시 슬라이더에 즉시 적용.
    """
    chosen = choose_difficulty(ctx.screen, ctx.font)
    if chosen is None:
        return  # ESC → 취소, 기존 유지
    ctx.preset_hud._apply_preset(chosen)
    ctx.read_sliders()
    ctx.snd.play("preset_change")
    _log.info("난이도 변경 → %s", chosen)


# ── 이벤트 처리 ──────────────────────────────────────


def _handle_events(ctx: _SimContext) -> bool:
    """Pygame 이벤트 처리. False 반환 시 루프 종료."""
    running = True
    for event in pygame.event.get():
        if ctx.tutorial.handle_event(event):
            continue
        if ctx.glossary.handle_event(event):
            continue
        ctx.panel.handle_event(event)
        ctx.preset_hud.handle_event(event)
        ctx.help_overlay.handle_event(event)

        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            running = _handle_key(ctx, event.key, running)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            _handle_mouse_down(ctx, event.pos)
        elif event.type == pygame.MOUSEMOTION:
            _handle_mouse_motion(ctx, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            ctx.barrier_dragging = False
            ctx.bloch_dragging = False
    return running


def _handle_key(ctx: _SimContext, key: int, running: bool) -> bool:
    """키보드 이벤트 분기."""
    ctx.snd.handle_key(key)
    if key == pygame.K_ESCAPE:
        if confirm_quit(ctx.screen, ctx.font):
            return False
    elif key == pygame.K_SPACE:
        ctx.paused = not ctx.paused
        _log.debug("일시정지 토글 → %s", "paused" if ctx.paused else "resumed")
    elif key == pygame.K_r:
        ctx.particle = QuantumParticle()
        ctx.panel.reset_all()
        ctx.trails.clear()
        ctx.current_trail.clear()
        ctx.trail_cache.clear()
        ctx.prev_tunneled_state = None
        _log.info("시뮬레이션 리셋")
    elif key == pygame.K_UP:
        ctx.sl_speed.value = ctx.sl_speed.value + 0.5
        ctx.snd.play("speed_change")
        _log.debug("속도 증가 → %.1f", ctx.sl_speed.value)
    elif key == pygame.K_DOWN:
        ctx.sl_speed.value = ctx.sl_speed.value - 0.5
        ctx.snd.play("speed_change")
        _log.debug("속도 감소 → %.1f", ctx.sl_speed.value)
    elif key == pygame.K_RIGHT:
        ctx.sl_barrier.value = ctx.sl_barrier.value + 10
        ctx.snd.play("barrier_adjust")
        _log.debug("장벽 두께 증가 → %.0f", ctx.sl_barrier.value)
    elif key == pygame.K_LEFT:
        ctx.sl_barrier.value = ctx.sl_barrier.value - 10
        ctx.snd.play("barrier_adjust")
        _log.debug("장벽 두께 감소 → %.0f", ctx.sl_barrier.value)
    # 블로흐 구 키보드 조작 (#24): WASD (Ctrl+D 는 난이도 변경)
    elif key == pygame.K_a:
        ctx.bloch_phi -= _BLOCH_KEY_STEP
        _log.debug("블로흐 phi -= %.3f → %.3f", _BLOCH_KEY_STEP, ctx.bloch_phi)
    elif key == pygame.K_d:
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            _switch_difficulty_midgame(ctx)
        else:
            ctx.bloch_phi += _BLOCH_KEY_STEP
            _log.debug("블로흐 phi += %.3f → %.3f", _BLOCH_KEY_STEP, ctx.bloch_phi)
    elif key == pygame.K_w:
        ctx.bloch_el = min(_BLOCH_EL_MAX, ctx.bloch_el + _BLOCH_KEY_STEP)
        _log.debug("블로흐 el += %.3f → %.3f", _BLOCH_KEY_STEP, ctx.bloch_el)
    elif key == pygame.K_s:
        ctx.bloch_el = max(_BLOCH_EL_MIN, ctx.bloch_el - _BLOCH_KEY_STEP)
        _log.debug("블로흐 el -= %.3f → %.3f", _BLOCH_KEY_STEP, ctx.bloch_el)
    elif key == pygame.K_l:
        toggle_locale()
    elif key == pygame.K_TAB:
        ctx.toast.toggle_history()
    elif key == pygame.K_LEFTBRACKET:
        cycle_sim_speed(-1)
    elif key == pygame.K_RIGHTBRACKET:
        cycle_sim_speed(1)
    elif key == pygame.K_x and (pygame.key.get_mods() & pygame.KMOD_CTRL):
        result = _export_session(ctx)
        if result:
            ctx.toast.show({"title": t("export_success"), "desc": result})
            ctx.snd.play("achievement")
    elif key == pygame.K_i and (pygame.key.get_mods() & pygame.KMOD_CTRL):
        if _import_session(ctx):
            ctx.toast.show({"title": t("import_success"), "desc": ctx.imported_label})
            ctx.snd.play("achievement")
    elif key == pygame.K_F3:
        # 배리어 스위퍼 토글 (#29)
        if ctx.sweeper is None or ctx.sweeper.done:
            ctx.sweeper = BarrierSweeper(base_prob=ctx.base_prob)
            _log.info("배리어 스위퍼 시작 (F3)")
        else:
            ctx.sweeper = None
            _log.info("배리어 스위퍼 취소 (F3)")
    elif key == pygame.K_F4:
        # 스텝별 실행 모드 토글 (#30)
        ctx.step_mode = not ctx.step_mode
        if ctx.step_mode:
            ctx.paused = True  # 스텝 모드 진입 시 자동 일시정지
            ctx.step_count = 0
            _log.info("스텝 모드 ON")
        else:
            _log.info("스텝 모드 OFF")
    elif key == pygame.K_n:
        # 스텝 모드에서 한 프레임 진행 (#30)
        if ctx.step_mode:
            ctx.step_pending = True
            _log.debug("스텝 진행 요청 (프레임 #%d)", ctx.step_count + 1)
    elif key == pygame.K_F5:
        # 되감기 토글 (#31)
        if ctx.rewinding:
            # 되감기 중지 → 현재 시점에서 일시정지
            ctx.rewinding = False
            ctx.paused = True
            _log.info("되감기 중지 (버퍼 %d프레임 남음)", len(ctx.rewind_buf))
        elif len(ctx.rewind_buf) > 0:
            ctx.rewinding = True
            ctx.paused = True  # 정방향 물리 중지
            _log.info("되감기 시작 (%d프레임 보유)", len(ctx.rewind_buf))
    elif key == pygame.K_F6:
        # 실험 데이터 비교 토글 (#32)
        ctx.exp_compare_visible = not ctx.exp_compare_visible
        if ctx.exp_compare_visible:
            _update_exp_fit_stats(ctx)
            _log.info("실험 비교 패널 ON (데이터셋: %s)", ctx.exp_dataset_id)
        else:
            _log.info("실험 비교 패널 OFF")
    elif key == pygame.K_F7 and ctx.exp_compare_visible:
        # 실험 데이터셋 순환 (#32)
        ds_ids = get_dataset_ids()
        if ds_ids:
            idx = ds_ids.index(ctx.exp_dataset_id) if ctx.exp_dataset_id in ds_ids else -1
            ctx.exp_dataset_id = ds_ids[(idx + 1) % len(ds_ids)]
            _update_exp_fit_stats(ctx)
            _log.info("데이터셋 전환: %s", ctx.exp_dataset_id)
    return running


def _handle_mouse_down(ctx: _SimContext, pos: tuple[int, int]):
    """마우스 클릭 — 장벽 드래그 / 블로흐 구 드래그 / 입자 재발사."""
    mx, my = pos
    left_edge = BARRIER_X - ctx.barrier_width // 2
    right_edge = BARRIER_X + ctx.barrier_width // 2
    in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H
    near_edge = in_sim_y and (abs(mx - left_edge) <= _BARRIER_EDGE_TOL or abs(mx - right_edge) <= _BARRIER_EDGE_TOL)
    if near_edge:
        ctx.barrier_dragging = True
    else:
        dx_b, dy_b = mx - BLOCH_CX, my - BLOCH_CY
        if dx_b * dx_b + dy_b * dy_b <= BLOCH_R * BLOCH_R:
            ctx.bloch_dragging = True
            ctx.bloch_drag_prev = (mx, my)
        else:
            ctx.particle.reset()
            _log.debug("입자 재발사 (클릭)")


def _handle_mouse_motion(ctx: _SimContext, pos: tuple[int, int]):
    """마우스 이동 — 드래그 업데이트 / 호버 감지."""
    mx, my = pos
    if ctx.barrier_dragging:
        half_w = abs(mx - BARRIER_X)
        old_bw = int(ctx.sl_barrier.value)
        ctx.sl_barrier.value = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, half_w * 2))
        if int(ctx.sl_barrier.value) != old_bw:
            ctx.snd.play("barrier_adjust")
    elif ctx.bloch_dragging:
        dx_m = mx - ctx.bloch_drag_prev[0]
        dy_m = my - ctx.bloch_drag_prev[1]
        ctx.bloch_phi += dx_m * _BLOCH_DRAG_SENSITIVITY
        ctx.bloch_el = max(_BLOCH_EL_MIN, min(_BLOCH_EL_MAX, ctx.bloch_el - dy_m * _BLOCH_DRAG_SENSITIVITY))
        ctx.bloch_drag_prev = (mx, my)
    else:
        left_edge = BARRIER_X - ctx.barrier_width // 2
        right_edge = BARRIER_X + ctx.barrier_width // 2
        in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H
        ctx.barrier_hover = in_sim_y and (
            abs(mx - left_edge) <= _BARRIER_EDGE_TOL or abs(mx - right_edge) <= _BARRIER_EDGE_TOL
        )


# ── 물리 업데이트 ────────────────────────────────────


# ── 되감기 스냅샷 (#31) ──────────────────────────────


def _capture_snapshot(ctx: _SimContext):
    """현재 프레임 상태를 되감기 버퍼에 저장."""
    ctx.rewind_buf.append(
        {
            "particle": ctx.particle.snapshot(),
            "barrier_width": ctx.barrier_width,
            "base_prob": ctx.base_prob,
            "tunnel_prob": ctx.tunnel_prob,
            "trail_frame": ctx.trail_frame,
            "current_trail": ctx.current_trail[:],
            "trails_len": len(ctx.trails),
            "prev_tunneled_state": ctx.prev_tunneled_state,
            "prev_attempts": ctx.prev_attempts,
            "peak_rate": ctx.peak_rate,
            "max_tunnel_barrier": ctx.max_tunnel_barrier,
            "trial_history_len": len(ctx.trial_history),
        }
    )


def _restore_snapshot(ctx: _SimContext, snap: dict):
    """스냅샷에서 시뮬레이션 상태를 복원."""
    ctx.particle.restore(snap["particle"])
    ctx.barrier_width = snap["barrier_width"]
    ctx.base_prob = snap["base_prob"]
    ctx.tunnel_prob = snap["tunnel_prob"]
    ctx.trail_frame = snap["trail_frame"]
    ctx.current_trail = snap["current_trail"]
    ctx.prev_tunneled_state = snap["prev_tunneled_state"]
    ctx.prev_attempts = snap["prev_attempts"]
    ctx.peak_rate = snap["peak_rate"]
    ctx.max_tunnel_barrier = snap["max_tunnel_barrier"]

    # trails / trial_history를 스냅샷 길이로 잘라서 되돌림
    while len(ctx.trails) > snap["trails_len"]:
        ctx.trails.pop()
    while len(ctx.trial_history) > snap["trial_history_len"]:
        ctx.trial_history.pop()
    ctx.trail_cache.mark_dirty()


def _step_physics(ctx: _SimContext, dt: float):
    """물리 시뮬레이션 한 프레임 진행 + 시행 기록 + 궤적 + 사운드."""
    p = ctx.particle

    # 속도 배율 적용 (화면 표시용, 내부 상태는 보존)
    orig_vx = p.vx
    p.vx = orig_vx * ctx.speed_mult if orig_vx > 0 else orig_vx
    p.update(dt, ctx.barrier_width, ctx.tunnel_prob, ctx.sl_boost.value)
    p.vx = orig_vx

    # 시행별 기록
    if p.total_attempts > ctx.prev_attempts:
        ctx.prev_attempts = p.total_attempts
        trial_elapsed = time.monotonic() - ctx.start_time
        tunneled = p.tunneled is True
        ctx.trial_history.append(
            {
                "t": round(trial_elapsed, 2),
                "barrier": ctx.barrier_width,
                "prob": round(ctx.tunnel_prob, 4),
                "result": tunneled,
            }
        )
        cur_rate = p.tunnel_count / p.total_attempts
        if cur_rate > ctx.peak_rate:
            ctx.peak_rate = cur_rate
        if tunneled and ctx.barrier_width > ctx.max_tunnel_barrier:
            ctx.max_tunnel_barrier = ctx.barrier_width

        # 실시간 업적 확인
        _check_realtime_achievements(ctx)

    # 사운드
    if p.tunneled is True and p.flash_timer > 0.5:
        ctx.snd.play("tunnel_success")
    elif p.tunneled is False and p.flash_timer > 0.3:
        ctx.snd.play("tunnel_reflect")

    # 궤적 기록
    ctx.trail_frame += 1
    if ctx.trail_frame % _TRAIL_SAMPLE == 0:
        ctx.current_trail.append((int(p.x), int(p.y)))

    if ctx.prev_tunneled_state is not None and p.tunneled is None:
        if ctx.current_trail:
            ctx.trails.append((ctx.current_trail[:], ctx.prev_tunneled_state))
            if len(ctx.trails) > _MAX_TRAILS:
                ctx.trails.pop(0)
            ctx.current_trail.clear()
            ctx.trail_cache.mark_dirty()
    ctx.prev_tunneled_state = p.tunneled

    ctx.preset_hud.update(dt)

    # 배리어 스위퍼 진행 (#29)
    if ctx.sweeper is not None and not ctx.sweeper.done:
        ctx.sweeper.advance()

    ctx.recorder.record_frame(
        {
            "x": round(p.x, 1),
            "tunneled": p.tunneled,
            "attempts": p.total_attempts,
            "tunnels": p.tunnel_count,
            "barrier_w": ctx.barrier_width,
            "rate": round(p.tunnel_count / max(p.total_attempts, 1), 3),
        }
    )


# ── 문맥별 힌트 ──────────────────────────────────────

_HINT_PAD = 6


def _get_contextual_hint(mx: int, my: int, ctx) -> str | None:
    """마우스 위치에 따른 문맥별 힌트 반환. 우선순위 순으로 검사."""
    # 오버레이 활성 시 / 드래그 중에는 숨김
    if ctx.tutorial.visible or ctx.help_overlay.visible or ctx.glossary.visible:
        return None
    if ctx.barrier_dragging or ctx.bloch_dragging:
        return None

    in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H

    # ① 장벽 가장자리 (최우선 — 시뮬레이션 영역보다 우선)
    left_edge = BARRIER_X - ctx.barrier_width // 2
    right_edge = BARRIER_X + ctx.barrier_width // 2
    tol2 = _BARRIER_EDGE_TOL * 2
    if in_sim_y and (abs(mx - left_edge) <= tol2 or abs(mx - right_edge) <= tol2):
        return t("ctx_hint_barrier")

    # ② 블로흐 구
    dx_b, dy_b = mx - BLOCH_CX, my - BLOCH_CY
    if dx_b * dx_b + dy_b * dy_b <= (BLOCH_R + 10) ** 2:
        return t("ctx_hint_bloch")

    # ③ 수식 오버레이
    if _FORMULA_X <= mx <= _FORMULA_X + _FORMULA_W and _FORMULA_Y <= my <= _FORMULA_Y + _FORMULA_H:
        return t("ctx_hint_formula")

    # ④ 확률 차트
    if _CHART_X <= mx <= _CHART_X + _CHART_W and _CHART_Y <= my <= _CHART_Y + _CHART_H:
        return t("ctx_hint_chart")

    # ⑤ 통계 패널 (블로흐 구 아래)
    stats_x = BLOCH_CX - BLOCH_R
    stats_y = BLOCH_CY + BLOCH_R + 60
    if stats_x <= mx <= stats_x + BLOCH_R * 2 and stats_y <= my <= stats_y + 70:
        return t("ctx_hint_stats")

    # ⑥ 슬라이더 패널
    if mx >= WIDTH + 5 and 40 <= my <= 200:
        return t("ctx_hint_sliders")

    # ⑦ 시뮬레이션 영역 (최하위 — 장벽 힌트에 덮이지 않는 영역)
    if SIM_LEFT <= mx <= SIM_LEFT + SIM_W and in_sim_y:
        return t("ctx_hint_sim")

    return None


def _draw_contextual_hint(screen, font, hint: str, mx: int, my: int):
    """마우스 근처에 툴팁 표시."""
    surf = _tcache.render(font, hint, TEXT_CLR)
    tw = surf.get_width() + _HINT_PAD * 2
    th = surf.get_height() + _HINT_PAD * 2

    # 위치: 마우스 우하단, 화면 초과 시 조정
    tx = mx + 14
    ty = my + 18
    sw = WIDTH + PANEL_W
    if tx + tw > sw:
        tx = mx - tw - 4
    if ty + th > HEIGHT:
        ty = my - th - 4

    bg = pygame.Surface((tw, th), pygame.SRCALPHA)
    bg.fill((*BG[:3], 220))
    screen.blit(bg, (tx, ty))
    pygame.draw.rect(screen, ACCENT, (tx, ty, tw, th), 1)
    screen.blit(surf, (tx + _HINT_PAD, ty + _HINT_PAD))


# ── 데이터 I/O (분리 모듈) ─────────────────────────────
from quantum.tunneling_data import (
    _EXPORT_DIR,
    _build_session_data,
    _choose_export_file,
    _export_session,
    _import_btn_rect,
    _import_session,
    _list_export_files,
    _load_import_data,
)


# ── 렌더링 ───────────────────────────────────────────


def _render_frame(ctx: _SimContext):
    """한 프레임 전체 렌더링."""
    ctx.screen.fill(BG)

    # 타이틀
    t_surf = _tcache.render(ctx.big_font, t("game_title_tunneling"), ACCENT)
    ctx.screen.blit(t_surf, (WIDTH // 2 - t_surf.get_width() // 2, 12))

    # 스텝 모드 인디케이터 (#30)
    if ctx.step_mode:
        step_label = t("tn_step_indicator", frame=ctx.step_count, dt=ctx.step_dt * 1000)
        step_surf = _tcache.render(ctx.font, step_label, TUNNEL_FLASH)
        ctx.screen.blit(step_surf, (SIM_LEFT, 38))

    # 되감기 인디케이터 (#31)
    if ctx.rewinding or ctx.rewind_buf:
        buf_max = ctx.rewind_buf.maxlen or 1
        remaining = len(ctx.rewind_buf) / buf_max * 100
        rw_label = t("tn_rewind_indicator", pct=remaining, frames=len(ctx.rewind_buf))
        rw_color = TUNNEL_FLASH if ctx.rewinding else TEXT_CLR
        rw_surf = _tcache.render(ctx.font, rw_label, rw_color)
        rw_y = 54 if ctx.step_mode else 38
        ctx.screen.blit(rw_surf, (SIM_LEFT, rw_y))

    _draw_sim_area(ctx.screen, ctx.font, ctx.barrier_width, ctx.barrier_hover, ctx.barrier_dragging)
    _draw_wavefunction(ctx.screen, ctx.barrier_width, ctx.tunnel_prob, pygame.time.get_ticks())
    _draw_trails(ctx.screen, ctx.trail_cache, ctx.trails, ctx.current_trail, ctx.particle.tunneled)
    _draw_particle(ctx.screen, ctx.particle, ctx.font)
    _draw_formula_overlay(ctx.screen, ctx.font, ctx)
    _draw_bloch_sphere(ctx.screen, ctx.particle, ctx.font, ctx.title_font, ctx.bloch_phi, ctx.bloch_el)
    _draw_stats(ctx.screen, ctx.particle, ctx.font, ctx.tunnel_prob)
    _draw_energy_diagram(ctx.screen, ctx.font, ctx.barrier_width, ctx.tunnel_prob)
    _draw_rate_chart(ctx.screen, ctx.font, ctx.trial_history, ctx.tunnel_prob, ctx.imported_trials)
    if ctx.sweeper is not None:
        _draw_sweep_chart(ctx.screen, ctx.font, ctx.sweeper)
    if ctx.exp_compare_visible:
        _draw_experiment_chart(ctx.screen, ctx.font, ctx)
    ctx.panel.draw(ctx.screen, ctx.font)
    _draw_achievement_progress(ctx.screen, ctx.font, ctx)

    # 안내 텍스트
    hints = [
        t(
            "hint_speed_info",
            speed=ctx.speed_mult,
            sim_speed=speed_label(),
            width=ctx.barrier_width,
            prob=ctx.tunnel_prob * 100,
            pause_state=(
                t("tn_rewind_title")
                if ctx.rewinding
                else t("tn_step_mode")
                if ctx.step_mode
                else t("paused")
                if ctx.paused
                else t("running_state")
            ),
        ),
        t("hint_click_launch"),
        t("hint_pause_reset")
        + f"  |  [/]: Sim Speed ({speed_label()})  |  D: Difficulty  |  Ctrl+X/I: Export/Import"
        + f"  |  F3: {t('tn_sweep_title')}  |  F4: {t('tn_step_mode')}  |  F5: {t('tn_rewind_title')}"
        + f"  |  F6: {t('exp_chart_title')}  |  G: {t('glossary_title')}",
    ]
    for i, h in enumerate(hints):
        surf = _tcache.render(ctx.font, h, TEXT_CLR)
        ctx.screen.blit(surf, (SIM_LEFT, HEIGHT - 52 + i * 16))

    # 문맥별 힌트 (오버레이 렌더링 전)
    _mx, _my = pygame.mouse.get_pos()
    _ctx_hint = _get_contextual_hint(_mx, _my, ctx)
    if _ctx_hint:
        _draw_contextual_hint(ctx.screen, ctx.font, _ctx_hint, _mx, _my)

    ctx.preset_hud.draw(ctx.screen, ctx.font)
    ctx.help_overlay.draw(ctx.screen, ctx.font)
    ctx.glossary.draw(ctx.screen, ctx.font)
    ctx.tutorial.draw(ctx.screen, ctx.font)
    ctx.toast.draw(ctx.screen, ctx.font)
    ctx.toast.draw_history(ctx.screen, ctx.font)


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    ctx = _SimContext()

    if not choose_difficulty_or_quit(ctx.screen, ctx.font, ctx.preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        raw_dt = ctx.clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)

        running = _handle_events(ctx)
        ctx.read_sliders()

        # 되감기 모드 (#31): 버퍼에서 스냅샷을 역순으로 복원
        if ctx.rewinding:
            for _ in range(ctx.rewind_speed):
                if ctx.rewind_buf:
                    _restore_snapshot(ctx, ctx.rewind_buf.pop())
                else:
                    ctx.rewinding = False
                    ctx.paused = True
                    break
        # 스텝 모드 (#30): N 키로 한 프레임씩 진행
        elif ctx.step_mode and ctx.step_pending:
            ctx.step_pending = False
            ctx.step_count += 1
            ctx.step_dt = dt
            _capture_snapshot(ctx)
            _step_physics(ctx, dt)
        elif not ctx.paused:
            _capture_snapshot(ctx)
            _step_physics(ctx, dt)

        ctx.toast.update(raw_dt)
        _render_frame(ctx)
        pygame.display.flip()

    finalize_session(
        "tunneling",
        _build_session_data(ctx),
        recorder=ctx.recorder,
        snd=ctx.snd,
        theme_callback=_load_theme_colors,
    )


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
