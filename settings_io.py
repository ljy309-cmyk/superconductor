"""설정 내보내기/가져오기 — config, 업적, 튜토리얼, 프로파일을 ZIP으로 관리.

사용법:
    from settings_io import export_settings, import_settings
    path = export_settings()                   # → settings_export_20260217.zip
    result = import_settings("backup.zip")     # → {"imported": [...], "skipped": [...]}
"""

import json
import os
import shutil
import zipfile
from datetime import datetime

from logger import get_module_logger

_log = get_module_logger("settings_io")

_BASE = os.path.dirname(os.path.abspath(__file__))
_EXPORT_DIR = os.path.join(_BASE, "exports", "settings")

# 내보낼 파일 목록 (상대 경로)
_EXPORT_FILES = [
    "config.json",
    "achievements.json",
    "tutorial_state.json",
]

# 내보낼 디렉터리
_EXPORT_DIRS = [
    "profiles",
]


def _backup_before_overwrite(dest: str) -> None:
    """기존 파일이 있으면 ``.bak`` 백업 생성."""
    if os.path.exists(dest):
        bak = dest + ".bak"
        try:
            shutil.copy2(dest, bak)
            _log.info("백업 생성: %s", bak)
        except OSError as e:
            _log.warning("백업 실패: %s", e)


def export_settings(output_dir: str | None = None) -> str | None:
    """현재 설정을 ZIP 파일로 내보내기.

    Returns:
        생성된 ZIP 파일 경로 (실패 시 ``None``).
    """
    dest_dir = output_dir or _EXPORT_DIR
    os.makedirs(dest_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"settings_export_{ts}.zip"
    zip_path = os.path.join(dest_dir, zip_name)

    try:
        file_count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 개별 파일
            for rel_path in _EXPORT_FILES:
                abs_path = os.path.join(_BASE, rel_path)
                if os.path.exists(abs_path):
                    zf.write(abs_path, rel_path)
                    file_count += 1
                    _log.info("내보내기: %s", rel_path)

            # 디렉터리
            for rel_dir in _EXPORT_DIRS:
                abs_dir = os.path.join(_BASE, rel_dir)
                if os.path.isdir(abs_dir):
                    for root, _dirs, files in os.walk(abs_dir):
                        for fname in files:
                            fpath = os.path.join(root, fname)
                            arcname = os.path.relpath(fpath, _BASE)
                            zf.write(fpath, arcname)
                            file_count += 1
                            _log.info("내보내기: %s", arcname)

        if file_count == 0:
            _log.warning("내보낼 설정 파일이 없음 — 빈 ZIP 삭제")
            os.remove(zip_path)
            return None

        _log.info("설정 내보내기 완료: %s (%d개 파일)", zip_path, file_count)
        return zip_path
    except (OSError, zipfile.BadZipFile) as e:
        _log.error("설정 내보내기 실패: %s", e)
        return None


def import_settings(zip_path: str) -> dict:
    """ZIP 파일에서 설정 가져오기.

    Returns:
        {"imported": [파일 목록], "skipped": [건너뜀 목록]}
    """
    result = {"imported": [], "skipped": []}

    if not os.path.exists(zip_path):
        _log.error("파일 없음: %s", zip_path)
        return result

    # 허용되는 경로 접두사
    allowed_prefixes = list(_EXPORT_FILES) + [d + "/" for d in _EXPORT_DIRS]

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                # 경로 순회 방지 (컴포넌트 단위 검사)
                parts = member.replace("\\", "/").split("/")
                if any(p == ".." for p in parts) or member.startswith("/"):
                    result["skipped"].append(member)
                    _log.warning("경로 순회 시도 차단: %s", member)
                    continue

                # 허용된 파일만 가져오기
                allowed = any(member == p or member.startswith(p) for p in allowed_prefixes)
                if not allowed:
                    result["skipped"].append(member)
                    _log.warning("허용되지 않은 파일 건너뜀: %s", member)
                    continue

                # JSON 파일이면 유효성 검사
                if member.endswith(".json"):
                    raw = zf.read(member)
                    try:
                        json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        result["skipped"].append(member)
                        _log.warning("유효하지 않은 JSON 건너뜀: %s", member)
                        continue
                    dest = os.path.join(_BASE, member)
                    dest_dir = os.path.dirname(dest)
                    os.makedirs(dest_dir, exist_ok=True)
                    _backup_before_overwrite(dest)
                    with open(dest, "wb") as dst:
                        dst.write(raw)
                else:
                    dest = os.path.join(_BASE, member)
                    dest_dir = os.path.dirname(dest)
                    os.makedirs(dest_dir, exist_ok=True)
                    _backup_before_overwrite(dest)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                result["imported"].append(member)
                _log.info("가져오기: %s", member)

        _log.info("설정 가져오기 완료: %d개 파일", len(result["imported"]))
    except (OSError, zipfile.BadZipFile) as e:
        _log.error("설정 가져오기 실패: %s", e)

    return result


def delete_export(zip_path: str) -> bool:
    """내보내기 ZIP 파일 삭제. 성공 시 ``True``."""
    try:
        os.remove(zip_path)
        _log.info("내보내기 파일 삭제: %s", zip_path)
        return True
    except OSError as e:
        _log.warning("파일 삭제 실패: %s", e)
        return False


def list_exports() -> list[str]:
    """내보내기 디렉터리의 ZIP 파일 목록."""
    if not os.path.isdir(_EXPORT_DIR):
        return []
    return sorted(
        [os.path.join(_EXPORT_DIR, f) for f in os.listdir(_EXPORT_DIR) if f.endswith(".zip")],
        reverse=True,
    )
