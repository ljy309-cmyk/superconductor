"""공통 세션 데이터 내보내기/가져오기 모듈.

모든 시뮬레이션에서 동일한 export/import, 파일 선택 UI를
공유할 수 있도록 일반화한 유틸리티.

사용법::

    from session_io import export_session, choose_import_file, load_session

    # 내보내기 (JSON 포맷)
    path = export_session("tunneling", session_dict)

    # 내보내기 (CSV 포맷)
    path = export_session("tunneling", session_dict, fmt="csv",
                          trial_rows=trials, trial_columns=columns)

    # 가져오기 UI
    file_path = choose_import_file(screen, font, "tunneling")

    # 데이터 로드 (포맷 자동 감지)
    data = load_session(file_path)
"""

import csv
import json
import os
from datetime import datetime

from logger import get_module_logger

_log = get_module_logger("session_io")

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports", "sessions")


# ── 내보내기 ──────────────────────────────────────────


def export_session(
    prefix: str,
    session_data: dict,
    *,
    fmt: str = "json",
    trial_rows: list[dict] | None = None,
    trial_columns: list[str] | None = None,
    trial_row_fn=None,
) -> str | None:
    """세션 데이터를 선택한 포맷(JSON 또는 CSV)으로 내보내기.

    Parameters
    ----------
    prefix : str
        파일명 접두사. 예: ``"tunneling"``
    session_data : dict
        세션 요약 딕셔너리.
    fmt : str
        내보내기 포맷. ``"json"`` 또는 ``"csv"``.
    trial_rows : list[dict] | None
        시행별 이력 리스트.
    trial_columns : list[str] | None
        CSV 헤더 컬럼 목록. ``trial_rows`` 와 함께 사용.
    trial_row_fn : callable | None
        ``(index, row_dict) -> list`` 형태의 함수.
        CSV 한 행을 변환한다. 미지정 시 ``trial_columns`` 순서로 값 추출.

    Returns
    -------
    str | None
        저장된 파일 경로. 실패 시 ``None``.
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S_%f")

    if fmt not in ("json", "csv"):
        _log.warning("지원하지 않는 포맷: %s (json으로 대체)", fmt)
        fmt = "json"

    if fmt == "csv":
        return _export_as_csv(prefix, session_data, ts, now, trial_rows, trial_columns, trial_row_fn)
    return _export_as_json(prefix, session_data, ts, now, trial_rows)


def _export_as_json(prefix, session_data, ts, now, trial_rows=None):
    """JSON 포맷으로 내보내기 (내부)."""
    data = dict(session_data)
    data["timestamp"] = now.isoformat()
    if trial_rows:
        data["trial_history"] = trial_rows
    path = os.path.join(EXPORT_DIR, f"{prefix}_stats_{ts}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        _log.warning("JSON 내보내기 실패: %s — %s", path, e)
        return None
    _log.info("데이터 내보내기 완료: %s", path)
    return path


def _export_as_csv(prefix, session_data, ts, now, trial_rows=None, trial_columns=None, trial_row_fn=None):
    """CSV 포맷으로 내보내기 (내부)."""
    path = os.path.join(EXPORT_DIR, f"{prefix}_stats_{ts}.csv")
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if trial_rows and not trial_columns:
                _log.warning("trial_rows가 있지만 trial_columns가 없어 시행 데이터 무시")
            if trial_rows and trial_columns:
                # 시행 데이터가 있으면 시행 데이터를 CSV로
                writer.writerow(trial_columns)
                for i, row in enumerate(trial_rows, 1):
                    if trial_row_fn:
                        writer.writerow(trial_row_fn(i, row))
                    else:
                        writer.writerow([row.get(c, "") for c in trial_columns])
            else:
                # 세션 요약만 flat CSV로
                data = dict(session_data)
                data["timestamp"] = now.isoformat()
                headers = list(data.keys())
                values = []
                for k in headers:
                    v = data[k]
                    if v is None:
                        values.append("")
                    elif isinstance(v, bool):
                        values.append(str(v))
                    elif isinstance(v, (dict, list)):
                        values.append(json.dumps(v, ensure_ascii=False))
                    else:
                        values.append(v)
                writer.writerow(headers)
                writer.writerow(values)
    except OSError as e:
        _log.warning("CSV 내보내기 실패: %s — %s", path, e)
        return None
    _log.info("데이터 내보내기 완료: %s", path)
    return path



# ── 파일 목록 ─────────────────────────────────────────


def list_export_files(prefix: str) -> list[tuple[str, str]]:
    """특정 prefix의 내보내기 파일 목록. ``[(표시명, 파일경로), ...]`` 최신순.

    JSON과 CSV 파일을 모두 포함하며, 표시명에 포맷을 표기합니다.
    """
    stats_prefix = f"{prefix}_stats_"
    if not os.path.isdir(EXPORT_DIR):
        return []
    try:
        entries = sorted(os.listdir(EXPORT_DIR), reverse=True)
    except OSError as e:
        _log.warning("내보내기 목록 조회 실패: %s", e)
        return []
    files = []
    for f in entries:
        if not f.startswith(stats_prefix):
            continue
        if f.endswith(".json"):
            label = f.replace(stats_prefix, "").replace(".json", "") + " (JSON)"
            files.append((label, os.path.join(EXPORT_DIR, f)))
        elif f.endswith(".csv"):
            label = f.replace(stats_prefix, "").replace(".csv", "") + " (CSV)"
            files.append((label, os.path.join(EXPORT_DIR, f)))
    return files


def delete_export(path: str) -> bool:
    """내보내기 파일 삭제. 성공 시 ``True``."""
    try:
        os.remove(path)
        _log.info("내보내기 파일 삭제: %s", path)
        return True
    except OSError as e:
        _log.warning("파일 삭제 실패: %s", e)
        return False


# ── 파일 선택 UI ──────────────────────────────────────


def _import_btn_rect(screen_w: int, screen_h: int, vis_index: int):
    """가져오기 대화상자 버튼 위치."""
    import pygame

    btn_w, btn_h = 300, 28
    bx = screen_w // 2 - btn_w // 2
    max_visible = 6
    panel_h = 50 + max_visible * 34 + 30
    py = screen_h // 2 - panel_h // 2
    by = py + 40 + vis_index * 34
    return pygame.Rect(bx, by, btn_w, btn_h)


def choose_import_file(screen, font, prefix: str) -> str | None:
    """내보내기 파일 선택 대화상자 (Pygame). 선택한 파일 경로 반환, 취소 시 ``None``."""
    import pygame

    from i18n import t
    from theme import get_pg_theme

    pg = get_pg_theme()
    W, H = screen.get_size()
    files = list_export_files(prefix)
    if not files:
        # 빈 목록 안내 표시 (1.5초)
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((*pg.BG, 200))
        screen.blit(overlay, (0, 0))
        msg = font.render(t("import_empty"), True, pg.SUBTEXT)
        screen.blit(msg, (W // 2 - msg.get_width() // 2, H // 2 - msg.get_height() // 2))
        pygame.display.flip()
        pygame.time.wait(1500)
        return None

    selected = 0
    scroll = 0
    max_visible = 6
    clock = pygame.time.Clock()

    # Surface 캐싱 — 루프 내 반복 생성 방지
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    btn_sample = _import_btn_rect(W, H, 0)
    btn_surf = pygame.Surface((btn_sample.width, btn_sample.height), pygame.SRCALPHA)
    title_surf = font.render(t("import_title"), True, pg.TEXT)
    hint_surf = font.render(t("import_hint"), True, pg.SUBTEXT)

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
                if event.key == pygame.K_d and files:
                    # 선택된 파일 삭제
                    _, del_path = files[selected]
                    if delete_export(del_path):
                        files.pop(selected)
                        if not files:
                            return None
                        selected = min(selected, len(files) - 1)
                        scroll = min(scroll, max(0, len(files) - max_visible))
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for vi in range(min(max_visible, len(files) - scroll)):
                    idx = scroll + vi
                    btn = _import_btn_rect(W, H, vi)
                    if btn.collidepoint(mx, my):
                        return files[idx][1]
            if event.type == pygame.MOUSEWHEEL:
                if event.y > 0:  # 위로 스크롤
                    selected = max(0, selected - 1)
                    if selected < scroll:
                        scroll = selected
                elif event.y < 0:  # 아래로 스크롤
                    selected = min(len(files) - 1, selected + 1)
                    if selected >= scroll + max_visible:
                        scroll = selected - max_visible + 1
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                for vi in range(min(max_visible, len(files) - scroll)):
                    idx = scroll + vi
                    btn = _import_btn_rect(W, H, vi)
                    if btn.collidepoint(mx, my):
                        selected = idx

        # 렌더링
        overlay.fill((*pg.BG, 200))
        screen.blit(overlay, (0, 0))

        panel_w, panel_h = 380, 50 + min(max_visible, len(files)) * 34 + 30
        px = W // 2 - panel_w // 2
        py = H // 2 - panel_h // 2
        pygame.draw.rect(screen, pg.PANEL_BG, (px, py, panel_w, panel_h), border_radius=10)
        pygame.draw.rect(screen, pg.OVERLAY, (px, py, panel_w, panel_h), 2, border_radius=10)

        screen.blit(title_surf, (W // 2 - title_surf.get_width() // 2, py + 12))

        for vi in range(min(max_visible, len(files) - scroll)):
            idx = scroll + vi
            label, _ = files[idx]
            btn = _import_btn_rect(W, H, vi)
            is_sel = idx == selected
            bg_alpha = 80 if is_sel else 30
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

        screen.blit(
            hint_surf,
            (W // 2 - hint_surf.get_width() // 2, py + panel_h - 22 if len(files) <= max_visible else py + panel_h - 10),
        )

        pygame.display.flip()
        clock.tick(30)


# ── 데이터 로드 ───────────────────────────────────────


def load_session(path: str | None) -> dict | None:
    """세션 파일 로드 (포맷 자동 감지). 실패 시 ``None``.

    ``.json`` → JSON으로 로드, ``.csv`` → CSV로 로드.
    지원하지 않는 확장자는 경고 후 ``None`` 반환.
    """
    if not path:
        return None
    if path.endswith(".csv"):
        return _load_session_csv(path)
    if path.endswith(".json"):
        return _load_session_json(path)
    _log.warning("지원하지 않는 파일 형식: %s (json, csv만 지원)", path)
    return None


def _load_session_json(json_path: str) -> dict | None:
    """JSON 세션 파일 로드 (내부). 실패 시 ``None``."""
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _log.warning("JSON 가져오기 실패: %s", e)
        return None


def _load_session_csv(csv_path: str) -> dict | None:
    """CSV 세션 파일 로드. 실패 시 ``None``.

    단일 행 CSV (세션 요약)는 dict로 반환.
    다중 행 CSV (시행 이력)는 ``{"rows": [행 목록]}`` 형태로 반환.
    JSON 문자열로 인코딩된 필드(dict/list)는 자동 파싱합니다.
    """
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            return None
        if len(rows) == 1:
            # 단일 행 → 세션 요약 dict로 반환
            result = dict(rows[0])
            _auto_parse_csv_values(result)
            return result
        # 다중 행 → 시행 이력
        for row in rows:
            _auto_parse_csv_values(row)
        return {"rows": rows}
    except (OSError, csv.Error) as e:
        _log.warning("CSV 가져오기 실패: %s", e)
        return None


def _auto_parse_csv_values(row: dict):
    """CSV 행의 문자열 값을 원래 타입으로 복원 (in-place)."""
    for k, v in row.items():
        if not isinstance(v, str):
            continue
        # 빈 문자열 → None 복원
        if v == "":
            row[k] = None
            continue
        # bool 복원
        if v.lower() == "true":
            row[k] = True
            continue
        if v.lower() == "false":
            row[k] = False
            continue
        # JSON 인코딩된 dict/list 복원
        if v.startswith(("{", "[")):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, (dict, list)):
                    row[k] = parsed
                    continue
            except (json.JSONDecodeError, ValueError):
                pass
        # 숫자 복원
        try:
            if "." in v:
                row[k] = float(v)
            else:
                row[k] = int(v)
        except ValueError:
            pass


