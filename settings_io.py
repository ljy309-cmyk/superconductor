"""설정 내보내기/가져오기 — config, 업적, 튜토리얼, 프로파일을 ZIP으로 관리.

사용법:
    from settings_io import export_settings, import_settings
    path = export_settings()                   # → settings_export_20260217_153045_123456.zip
    result = import_settings("backup.zip")     # → {"imported": [...], "skipped": [...]}
"""

import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime

from logger import get_module_logger

_log = get_module_logger("settings_io")

_BASE = os.path.dirname(os.path.abspath(__file__))
_EXPORT_DIR = os.path.join(_BASE, "exports", "settings")

# 설정 내보내기 스키마 버전
SETTINGS_VERSION = 1

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

# ZIP bomb 방어: 압축 해제 최대 크기 (10MB)
_MAX_UNCOMPRESSED_SIZE = 10 * 1024 * 1024

# 내보내기 파일 최대 보관 수
_MAX_EXPORT_ZIPS = 20


def _backup_before_overwrite(dest: str) -> None:
    """기존 파일이 있으면 번호 매긴 백업 생성 (.bak, .bak.1, .bak.2)."""
    if not os.path.exists(dest):
        return
    # 기존 .bak 파일을 한 단계씩 밀어냄 (최대 3단계)
    max_backups = 3
    for i in range(max_backups - 1, 0, -1):
        old_bak = f"{dest}.bak.{i}"
        new_bak = f"{dest}.bak.{i + 1}"
        if os.path.exists(old_bak):
            try:
                os.replace(old_bak, new_bak)
            except OSError:
                pass
    bak = dest + ".bak"
    bak_1 = dest + ".bak.1"
    if os.path.exists(bak):
        try:
            os.replace(bak, bak_1)
        except OSError:
            pass
        _log.info("기존 백업 이동: %s → %s", bak, bak_1)
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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    zip_name = f"settings_export_{ts}.zip"
    zip_path = os.path.join(dest_dir, zip_name)

    try:
        file_count = 0
        # 원자적 쓰기: 임시 파일에 먼저 생성
        fd, tmp_path = tempfile.mkstemp(suffix=".zip", dir=dest_dir)
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # 버전 메타데이터 삽입
                meta = json.dumps({"version": SETTINGS_VERSION, "timestamp": ts}, ensure_ascii=False)
                zf.writestr("_meta.json", meta)

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
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return None

            os.replace(tmp_path, zip_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        _log.info("설정 내보내기 완료: %s (%d개 파일)", zip_path, file_count)
        _cleanup_old_exports()
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
            # ZIP bomb 방어: 총 압축 해제 크기 검사
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > _MAX_UNCOMPRESSED_SIZE:
                _log.error("ZIP 압축 해제 크기 초과: %d bytes (최대 %d)", total_size, _MAX_UNCOMPRESSED_SIZE)
                return result

            for member in zf.namelist():
                # 메타데이터 파일 건너뛰기
                if member == "_meta.json":
                    continue

                # 경로 순회 방지 (컴포넌트 단위 검사)
                parts = member.replace("\\", "/").split("/")
                if any(p == ".." for p in parts) or member.startswith("/"):
                    result["skipped"].append(member)
                    _log.warning("경로 순회 시도 차단: %s", member)
                    continue

                # 빈 파일명 차단
                if not member or member.endswith("/"):
                    continue

                # 허용된 파일만 가져오기
                allowed = any(member == p or member.startswith(p) for p in allowed_prefixes)
                if not allowed:
                    result["skipped"].append(member)
                    _log.warning("허용되지 않은 파일 건너뜀: %s", member)
                    continue

                # 개별 파일 크기 제한 (5MB)
                info = zf.getinfo(member)
                if info.file_size > 5 * 1024 * 1024:
                    result["skipped"].append(member)
                    _log.warning("파일 크기 초과 건너뜀: %s (%d bytes)", member, info.file_size)
                    continue

                # JSON 파일이면 유효성 검사
                raw = None
                if member.endswith(".json"):
                    raw = zf.read(member)
                    try:
                        json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        result["skipped"].append(member)
                        _log.warning("유효하지 않은 JSON 건너뜀: %s", member)
                        continue

                # 공통: 대상 경로 준비 및 백업
                dest = os.path.join(_BASE, member)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                _backup_before_overwrite(dest)

                # 원자적 쓰기: 임시 파일에 먼저 쓴 후 rename
                dest_dir = os.path.dirname(dest)
                fd, tmp_dest = tempfile.mkstemp(dir=dest_dir)
                try:
                    if raw is not None:
                        with os.fdopen(fd, "wb") as dst:
                            dst.write(raw)
                    else:
                        with zf.open(member) as src, os.fdopen(fd, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    os.replace(tmp_dest, dest)
                except BaseException:
                    try:
                        os.unlink(tmp_dest)
                    except OSError:
                        pass
                    raise
                result["imported"].append(member)
                _log.info("가져오기: %s", member)

        _log.info("설정 가져오기 완료: %d개 파일", len(result["imported"]))
    except (OSError, zipfile.BadZipFile) as e:
        _log.error("설정 가져오기 실패: %s", e)

    return result


def _cleanup_old_exports() -> None:
    """오래된 내보내기 ZIP 정리 (_MAX_EXPORT_ZIPS 초과 시 삭제)."""
    if not os.path.isdir(_EXPORT_DIR):
        return
    try:
        zips = sorted(
            (f for f in os.listdir(_EXPORT_DIR) if f.endswith(".zip")),
            reverse=True,
        )
    except OSError:
        return
    for old_zip in zips[_MAX_EXPORT_ZIPS:]:
        try:
            os.remove(os.path.join(_EXPORT_DIR, old_zip))
            _log.info("오래된 내보내기 삭제: %s", old_zip)
        except OSError:
            pass


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
    try:
        return sorted(
            [os.path.join(_EXPORT_DIR, f) for f in os.listdir(_EXPORT_DIR) if f.endswith(".zip")],
            reverse=True,
        )
    except OSError as e:
        _log.warning("내보내기 목록 조회 실패: %s", e)
        return []
