"""공통 세션 데이터 내보내기/가져오기 모듈.

모든 시뮬레이션에서 동일한 JSON export/import, 파일 선택 UI를
공유할 수 있도록 일반화한 유틸리티.

사용법::

    from session_io import export_session_json, choose_import_file, load_session_json

    # 내보내기
    path = export_session_json("tunneling", session_dict, trial_rows, trial_columns)

    # 가져오기 UI
    json_path = choose_import_file(screen, font, "tunneling")

    # 데이터 로드
    session, trials = load_session_json(json_path)
"""

import csv
import json
import os
from datetime import datetime

from logger import get_module_logger

_log = get_module_logger("session_io")

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports", "sessions")


# ── 내보내기 ──────────────────────────────────────────


def export_session_json(
    prefix: str,
    session_data: dict,
    *,
    trial_rows: list[dict] | None = None,
    trial_columns: list[str] | None = None,
    trial_row_fn=None,
) -> str | None:
    """세션 데이터를 JSON(+선택적 CSV)으로 내보내기.

    Parameters
    ----------
    prefix : str
        파일명 접두사. 예: ``"tunneling"`` → ``tunneling_stats_<ts>.json``
    session_data : dict
        JSON으로 저장할 세션 요약 딕셔너리.
    trial_rows : list[dict] | None
        시행별 이력 리스트. 주어지면 CSV도 함께 생성.
    trial_columns : list[str] | None
        CSV 헤더 컬럼 목록. ``trial_rows`` 와 함께 사용.
    trial_row_fn : callable | None
        ``(index, row_dict) -> list`` 형태의 함수.
        CSV 한 행을 변환한다. 미지정 시 ``trial_columns`` 순서로 값 추출.

    Returns
    -------
    str | None
        저장된 JSON 파일 경로. 실패 시 ``None``.
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    data = dict(session_data)
    data["timestamp"] = datetime.now().isoformat()
    json_path = os.path.join(EXPORT_DIR, f"{prefix}_stats_{ts}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        _log.warning("JSON 내보내기 실패: %s", json_path)
        return None

    # CSV (선택)
    if trial_rows and trial_columns:
        csv_path = os.path.join(EXPORT_DIR, f"{prefix}_trials_{ts}.csv")
        try:
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(trial_columns)
                for i, row in enumerate(trial_rows, 1):
                    if trial_row_fn:
                        writer.writerow(trial_row_fn(i, row))
                    else:
                        writer.writerow([row.get(c, "") for c in trial_columns])
        except OSError:
            _log.warning("CSV 내보내기 실패: %s", csv_path)

    _log.info("데이터 내보내기 완료: %s", json_path)
    return json_path


# ── 파일 목록 ─────────────────────────────────────────


def list_export_files(prefix: str) -> list[tuple[str, str]]:
    """특정 prefix의 내보내기 파일 목록. ``[(표시명, JSON경로), ...]`` 최신순."""
    stats_prefix = f"{prefix}_stats_"
    if not os.path.isdir(EXPORT_DIR):
        return []
    files = []
    for f in sorted(os.listdir(EXPORT_DIR), reverse=True):
        if f.startswith(stats_prefix) and f.endswith(".json"):
            label = f.replace(stats_prefix, "").replace(".json", "")
            files.append((label, os.path.join(EXPORT_DIR, f)))
    return files


# ── 파일 선택 UI ──────────────────────────────────────


def _import_btn_rect(screen_w: int, screen_h: int, vis_index: int):
    """가져오기 대화상자 버튼 위치."""
    import pygame

    btn_w, btn_h = 300, 28
    bx = screen_w // 2 - btn_w // 2
    max_visible = 6
    panel_h = 50 + min(max_visible, 6) * 34 + 30
    py = screen_h // 2 - panel_h // 2
    by = py + 40 + vis_index * 34
    return pygame.Rect(bx, by, btn_w, btn_h)


def choose_import_file(screen, font, prefix: str) -> str | None:
    """내보내기 파일 선택 대화상자 (Pygame). JSON 경로 반환, 취소 시 ``None``."""
    import pygame

    from i18n import t
    from theme import get_pg_theme

    pg = get_pg_theme()
    W, H = screen.get_size()
    files = list_export_files(prefix)
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


# ── 데이터 로드 ───────────────────────────────────────


def load_session_json(json_path: str) -> dict | None:
    """JSON 세션 파일 로드. 실패 시 ``None``."""
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _log.warning("JSON 가져오기 실패: %s", e)
        return None


def load_session_with_trials(
    json_path: str,
    prefix: str,
    trial_parse_fn=None,
) -> tuple[dict | None, list[dict]]:
    """JSON 세션 + 매칭 CSV 시행 이력 로드.

    Parameters
    ----------
    json_path : str
        JSON 파일 경로.
    prefix : str
        파일명 접두사 (CSV 매칭에 사용).
    trial_parse_fn : callable | None
        ``(csv_row_dict) -> dict`` 형태의 변환 함수.
        미지정 시 CSV 행을 그대로 dict로 반환.

    Returns
    -------
    tuple[dict | None, list[dict]]
        ``(session_dict, trial_list)``. JSON 실패 시 ``(None, [])``.
    """
    session = load_session_json(json_path)
    if session is None:
        return None, []

    trials: list[dict] = []
    csv_path = json_path.replace(f"{prefix}_stats_", f"{prefix}_trials_").replace(".json", ".csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if trial_parse_fn:
                        trials.append(trial_parse_fn(row))
                    else:
                        trials.append(dict(row))
        except (OSError, KeyError, ValueError) as e:
            _log.warning("CSV 가져오기 실패: %s", e)

    return session, trials
