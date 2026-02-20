"""터널링 시뮬레이션 데이터 관리 — 세션 내보내기/가져오기, 파일 선택 UI.

``quantum.tunneling`` 에서 분리된 데이터 I/O 전용 모듈.
"""

import csv
import json
import os
import time
from datetime import datetime

import pygame

from i18n import t
from logger import get_module_logger
from quantum.tunneling_physics import (
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
)
from theme import get_pg_theme

_log = get_module_logger("tunneling")

_EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")


# ── 세션 데이터 빌드 ────────────────────────────────


def _build_session_data(ctx) -> dict:
    """finalize_session용 세션 요약 딕셔너리 생성."""
    p = ctx.particle
    rate = p.tunnel_count / max(p.total_attempts, 1)
    elapsed_time = time.monotonic() - ctx.start_time
    elapsed_min = elapsed_time / 60.0 if elapsed_time > 0 else 1.0
    avg_bw = (
        round(sum(tr["barrier"] for tr in ctx.trial_history) / len(ctx.trial_history), 1)
        if ctx.trial_history
        else ctx.barrier_width
    )
    return {
        "total_attempts": p.total_attempts,
        "tunnel_count": p.tunnel_count,
        "reflect_count": p.reflect_count,
        "tunnel_rate": round(rate, 3),
        "barrier_width": ctx.barrier_width,
        "base_prob": round(ctx.base_prob, 3),
        "tunnel_prob": round(ctx.tunnel_prob, 3),
        "elapsed_time": round(elapsed_time, 2),
        "max_tunnel_barrier": ctx.max_tunnel_barrier,
        "barrier_configs_tried": len(ctx.barrier_configs_tried),
        "peak_rate": round(ctx.peak_rate, 3),
        "avg_barrier_width": avg_bw,
        "trials_per_minute": round(p.total_attempts / elapsed_min, 1),
        "speed_mult": round(ctx.speed_mult, 1),
        "difficulty": ctx.preset_hud.current,
        "trial_history": list(ctx.trial_history),
    }


# ── 데이터 내보내기 ──────────────────────────────────


def _export_session(ctx) -> str | None:
    """세션 통계를 JSON + CSV로 내보내기. 저장 경로 반환 (실패 시 None)."""
    export_dir = _EXPORT_DIR
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ① JSON — 세션 요약
    session = _build_session_data(ctx)
    session.pop("trial_history", None)  # CSV에 별도 저장하므로 JSON에서 제거
    session["timestamp"] = datetime.now().isoformat()
    json_path = os.path.join(export_dir, f"tunneling_stats_{ts}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
    except OSError:
        _log.warning("JSON 내보내기 실패: %s", json_path)
        return None

    # ② CSV — 시행별 이력
    csv_path = os.path.join(export_dir, f"tunneling_trials_{ts}.csv")
    try:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trial", "time_s", "barrier_width", "tunnel_prob", "result"])
            for i, tr in enumerate(ctx.trial_history, 1):
                writer.writerow([i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])])
    except OSError:
        _log.warning("CSV 내보내기 실패: %s", csv_path)

    _log.info("데이터 내보내기 완료: %s", export_dir)
    return export_dir


# ── 데이터 가져오기 ──────────────────────────────────


def _list_export_files() -> list[tuple[str, str]]:
    """tunneling 내보내기 파일 목록 반환. [(표시 이름, JSON 경로), ...] 최신순."""
    if not os.path.isdir(_EXPORT_DIR):
        return []
    files = []
    for f in sorted(os.listdir(_EXPORT_DIR), reverse=True):
        if f.startswith("tunneling_stats_") and f.endswith(".json"):
            label = f.replace("tunneling_stats_", "").replace(".json", "")
            files.append((label, os.path.join(_EXPORT_DIR, f)))
    return files


def _import_btn_rect(screen_w: int, screen_h: int, vis_index: int) -> pygame.Rect:
    """가져오기 대화상자 버튼 위치 계산."""
    btn_w, btn_h = 300, 28
    bx = screen_w // 2 - btn_w // 2
    max_visible = 6
    panel_h = 50 + min(max_visible, 6) * 34 + 30
    py = screen_h // 2 - panel_h // 2
    by = py + 40 + vis_index * 34
    return pygame.Rect(bx, by, btn_w, btn_h)


def _choose_export_file(screen, font) -> str | None:
    """내보내기 파일 선택 대화상자 (Pygame). 선택한 JSON 경로 반환, 취소 시 None."""
    pg = get_pg_theme()
    W, H = screen.get_size()
    files = _list_export_files()
    if not files:
        return None

    selected = 0
    scroll = 0
    max_visible = 6
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = max(0, selected - 1)
                    if selected < scroll:
                        scroll = selected
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = min(len(files) - 1, selected + 1)
                    if selected >= scroll + max_visible:
                        scroll = selected - max_visible + 1
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return files[selected][1]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for vi in range(min(max_visible, len(files) - scroll)):
                    idx = scroll + vi
                    btn = _import_btn_rect(W, H, vi)
                    if btn.collidepoint(mx, my):
                        return files[idx][1]
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                for vi in range(min(max_visible, len(files) - scroll)):
                    idx = scroll + vi
                    btn = _import_btn_rect(W, H, vi)
                    if btn.collidepoint(mx, my):
                        selected = idx

        # 렌더링
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((*pg.BG, 200))
        screen.blit(overlay, (0, 0))

        panel_w, panel_h = 380, 50 + min(max_visible, len(files)) * 34 + 30
        px = W // 2 - panel_w // 2
        py = H // 2 - panel_h // 2
        pygame.draw.rect(screen, pg.PANEL_BG, (px, py, panel_w, panel_h), border_radius=10)
        pygame.draw.rect(screen, pg.OVERLAY, (px, py, panel_w, panel_h), 2, border_radius=10)

        title = font.render(t("import_title"), True, pg.TEXT)
        screen.blit(title, (W // 2 - title.get_width() // 2, py + 12))

        for vi in range(min(max_visible, len(files) - scroll)):
            idx = scroll + vi
            label, _ = files[idx]
            btn = _import_btn_rect(W, H, vi)
            is_sel = idx == selected
            bg_alpha = 80 if is_sel else 30
            btn_surf = pygame.Surface((btn.width, btn.height), pygame.SRCALPHA)
            btn_surf.fill((*pg.ACCENT_BLUE[:3], bg_alpha))
            screen.blit(btn_surf, btn.topleft)
            border_w = 2 if is_sel else 1
            pygame.draw.rect(screen, pg.ACCENT_BLUE if is_sel else pg.OVERLAY, btn, border_w, border_radius=4)
            if is_sel:
                arrow = font.render(">", True, pg.ACCENT_BLUE)
                screen.blit(arrow, (btn.x - 14, btn.centery - arrow.get_height() // 2))
            lbl_surf = font.render(label, True, pg.TEXT)
            screen.blit(lbl_surf, (btn.x + 8, btn.centery - lbl_surf.get_height() // 2))

        # 스크롤 표시
        if len(files) > max_visible:
            info = font.render(f"{selected + 1}/{len(files)}", True, pg.SUBTEXT)
            screen.blit(info, (W // 2 - info.get_width() // 2, py + panel_h - 22))

        hint = font.render(t("import_hint"), True, pg.SUBTEXT)
        screen.blit(
            hint,
            (W // 2 - hint.get_width() // 2, py + panel_h - 22 if len(files) <= max_visible else py + panel_h - 10),
        )

        pygame.display.flip()
        clock.tick(30)


def _load_import_data(json_path: str) -> tuple[dict | None, list[dict]]:
    """JSON 세션 + CSV 시행 이력 로드. (session_dict, trial_list) 반환."""
    session = None
    trials: list[dict] = []

    # ① JSON 로드
    try:
        with open(json_path, encoding="utf-8") as f:
            session = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _log.warning("JSON 가져오기 실패: %s", e)
        return None, []

    # ② 매칭 CSV 찾기 (같은 타임스탬프)
    csv_path = json_path.replace("tunneling_stats_", "tunneling_trials_").replace(".json", ".csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trials.append(
                        {
                            "t": float(row["time_s"]),
                            "barrier": int(row["barrier_width"]),
                            "prob": float(row["tunnel_prob"]),
                            "result": bool(int(row["result"])),
                        }
                    )
        except (OSError, KeyError, ValueError) as e:
            _log.warning("CSV 가져오기 실패: %s", e)

    return session, trials


def _import_session(ctx) -> bool:
    """내보내기 파일을 선택하고 파라미터 적용 + 비교 데이터 로드."""
    json_path = _choose_export_file(ctx.screen, ctx.font)
    if json_path is None:
        return False

    session, trials = _load_import_data(json_path)
    if session is None:
        return False

    # 슬라이더에 파라미터 적용
    if "base_prob" in session:
        ctx.sl_prob.value = max(0.01, min(0.50, session["base_prob"]))
    if "barrier_width" in session:
        ctx.sl_barrier.value = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, session["barrier_width"]))
    if "speed_mult" in session:
        ctx.sl_speed.value = max(0.5, min(5.0, session["speed_mult"]))
    ctx.read_sliders()

    # 비교용 시행 이력 저장
    if trials:
        ctx.imported_trials = trials
        ts_label = os.path.basename(json_path).replace("tunneling_stats_", "").replace(".json", "")
        ctx.imported_label = ts_label

    _log.info("데이터 가져오기 완료: %s (%d trials)", json_path, len(trials))
    return True
