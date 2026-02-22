"""스냅샷 테스트 — 물리 엔진/설정 출력의 회귀 검증.

syrupy 없이 JSON 기반으로 스냅샷을 비교합니다.
처음 실행 시 스냅샷 파일을 생성하고, 이후 실행에서는 비교합니다.
--update-snapshots 플래그로 스냅샷을 갱신할 수 있습니다.

사용법:
    python -m pytest tests/test_snapshot.py -v
    python -m pytest tests/test_snapshot.py -v --update-snapshots  # 스냅샷 갱신
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 스냅샷 디렉토리
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__snapshots__")


def _ensure_snapshot_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def _snapshot_path(name: str) -> str:
    return os.path.join(SNAPSHOT_DIR, f"{name}.json")


def _should_update() -> bool:
    """--update-snapshots 플래그 확인."""
    return "--update-snapshots" in sys.argv


def assert_snapshot(test_case: unittest.TestCase, name: str, data: dict | list):
    """스냅샷 비교 또는 생성.

    처음 실행: 스냅샷 파일 생성
    이후 실행: 기존 스냅샷과 비교
    --update-snapshots: 스냅샷 갱신
    """
    _ensure_snapshot_dir()
    path = _snapshot_path(name)
    serialized = json.dumps(data, indent=2, sort_keys=True, default=str)

    if _should_update() or not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(serialized)
        return  # 생성/갱신 시에는 비교하지 않음

    with open(path, encoding="utf-8") as f:
        expected = f.read()

    test_case.assertEqual(
        serialized,
        expected,
        f"스냅샷 불일치: {name}\n스냅샷을 갱신하려면: pytest --update-snapshots\n파일: {path}",
    )


# ═══════════════════════════════════════════════════════════
# 1. 물리 엔진 출력 스냅샷
# ═══════════════════════════════════════════════════════════


class TestTunnelingPhysicsSnapshot(unittest.TestCase):
    """터널링 물리 엔진 출력 스냅샷."""

    def test_tunnel_probability_snapshot(self):
        """다양한 장벽 폭에 대한 터널링 확률 스냅샷."""
        from quantum.tunneling_physics import _calc_tunnel_prob

        results = []
        for width in [10, 20, 30, 50, 80, 100, 150, 200]:
            prob = _calc_tunnel_prob(width)
            results.append({"barrier_width": width, "probability": round(prob, 10)})

        assert_snapshot(self, "tunneling_probabilities", results)

    def test_particle_initialization_snapshot(self):
        """QuantumParticle 초기 상태 스냅샷."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle(seed=42)
        state = {
            "x": p.x,
            "vx": p.vx,
            "alive": p.alive,
            "tunnel_count": p.tunnel_count,
            "reflect_count": p.reflect_count,
        }
        assert_snapshot(self, "particle_init_state", state)


class TestQECPhysicsSnapshot(unittest.TestCase):
    """QEC 물리 엔진 출력 스냅샷."""

    def test_qubit_grid_snapshot(self):
        """QEC 큐비트 그리드 초기 상태."""
        from quantum.qec_physics import build_grid

        grid = build_grid()
        state = []
        for q in grid:
            state.append(
                {
                    "qid": q.qid,
                    "x": q.x,
                    "y": q.y,
                    "stress": round(q.stress, 6),
                    "collapsed": q.collapsed,
                }
            )
        assert_snapshot(self, "qec_grid_5x3", state)


class TestQubitPhysicsSnapshot(unittest.TestCase):
    """큐비트 물리 엔진 출력 스냅샷."""

    def test_qubit_network_snapshot(self):
        """QubitNetwork 초기 상태."""
        from quantum.qubit_physics import QubitNetwork

        net = QubitNetwork()
        state = {
            "num_qubits": len(net.nodes),
            "nodes": [
                {
                    "qid": n.qid,
                    "stress": round(n.stress, 6),
                    "collapsed": n.collapsed,
                }
                for n in net.nodes
            ],
        }
        assert_snapshot(self, "qubit_network_default", state)


class TestBB84ProtocolSnapshot(unittest.TestCase):
    """BB84 프로토콜 출력 스냅샷 (결정론적 부분만)."""

    def test_bb84_config_snapshot(self):
        """BB84Game 초기 설정 스냅샷."""
        from security.bb84_protocol import BB84Game

        game = BB84Game()
        state = {
            "channel_open": game.channel_open,
            "eve_active": game.eve_active,
            "error_rate": game.error_rate,
            "round_id": game.round_id,
            "score": game.score,
        }
        assert_snapshot(self, "bb84_config", state)


class TestSQUIDLogicSnapshot(unittest.TestCase):
    """SQUID 로직 출력 스냅샷."""

    def test_squid_init_snapshot(self):
        """SQUIDGame 초기 상태 스냅샷."""
        from security.squid_logic import GRID_COLS, GRID_ROWS, NUM_MINES, SQUIDGame

        game = SQUIDGame()
        state = {
            "grid_rows": GRID_ROWS,
            "grid_cols": GRID_COLS,
            "num_mines_config": NUM_MINES,
            "actual_mines": len(game.mines),
            "revealed": game.revealed,
            "won": game.won,
        }
        assert_snapshot(self, "squid_init", state)


# ═══════════════════════════════════════════════════════════
# 2. 설정/구성 스냅샷
# ═══════════════════════════════════════════════════════════


class TestConfigSnapshot(unittest.TestCase):
    """config.json 구조 스냅샷."""

    def test_config_structure_snapshot(self):
        """config.json의 최상위 키 구조."""
        from config_loader import cfg

        # 값이 아닌 구조만 스냅샷 (값은 변경될 수 있음)
        structure = sorted(cfg.keys()) if isinstance(cfg, dict) else []
        assert_snapshot(self, "config_top_level_keys", structure)

    def test_presets_snapshot(self):
        """프리셋 구조 스냅샷."""
        from presets import get_preset

        presets = {}
        for name in ["easy", "normal", "hard"]:
            preset = get_preset(name)
            if preset:
                presets[name] = sorted(preset.keys())
        assert_snapshot(self, "preset_structures", presets)


class TestI18nSnapshot(unittest.TestCase):
    """i18n 키 구조 스냅샷."""

    def test_locale_key_count(self):
        """로케일 키 수가 일관되는지 확인."""
        from i18n import _load_locale

        ko = _load_locale("ko")
        en = _load_locale("en")
        state = {
            "ko_key_count": len(ko),
            "en_key_count": len(en),
            "ko_only_keys_count": len(set(ko.keys()) - set(en.keys())),
            "en_only_keys_count": len(set(en.keys()) - set(ko.keys())),
        }
        assert_snapshot(self, "i18n_key_counts", state)


class TestThemeSnapshot(unittest.TestCase):
    """테마 색상 스냅샷."""

    def test_pg_colors_snapshot(self):
        """Pygame 색상 스냅샷."""
        from theme import PG

        colors = {
            "BG": list(PG.BG),
            "TEXT": list(PG.TEXT),
            "GREEN": list(PG.GREEN),
            "RED": list(PG.RED),
            "ACCENT_BLUE": list(PG.ACCENT_BLUE),
        }
        assert_snapshot(self, "pg_theme_colors", colors)

    def test_tk_colors_snapshot(self):
        """Tkinter 색상 스냅샷."""
        from theme import TK

        colors = {
            "BG": TK.BG,
            "TEXT": TK.TEXT,
            "GREEN": TK.GREEN,
            "RED": TK.RED,
            "ACCENT_BLUE": TK.ACCENT_BLUE,
        }
        assert_snapshot(self, "tk_theme_colors", colors)


# ═══════════════════════════════════════════════════════════
# 3. 업적/리플레이 구조 스냅샷
# ═══════════════════════════════════════════════════════════


class TestAchievementsSnapshot(unittest.TestCase):
    """업적 데이터 구조 스냅샷."""

    def test_achievements_structure(self):
        """전체 업적 목록 구조."""
        from achievements import get_all_achievements

        all_ach = get_all_achievements()
        # 구조만 확인 (unlocked 상태는 가변)
        structure = [{"id": a.get("id", ""), "title": a.get("title", ""), "icon": a.get("icon", "")} for a in all_ach]
        assert_snapshot(self, "achievements_structure", structure)


class TestGlossarySnapshot(unittest.TestCase):
    """용어집 데이터 스냅샷."""

    def test_glossary_entry_count(self):
        """용어집 항목 수."""
        # glossary.py는 pygame 의존이므로 직접 데이터만 검사
        from unittest.mock import MagicMock, patch

        _pg_mock = MagicMock()
        _pg_mock.KEYDOWN = 768
        _pg_mock.K_g = 103
        _pg_mock.K_ESCAPE = 27
        _pg_mock.K_DOWN = 274
        _pg_mock.K_UP = 273
        _pg_mock.K_PAGEDOWN = 281
        _pg_mock.K_PAGEUP = 280
        _pg_mock.SRCALPHA = 0x00010000

        with patch.dict(sys.modules, {"pygame": _pg_mock}):
            # glossary 모듈의 캐시된 버전 제거 후 재임포트
            mod_name = "glossary"
            old_mod = sys.modules.pop(mod_name, None)
            try:
                import glossary

                entries = glossary._GLOSSARY_ENTRIES
                state = {
                    "total_entries": len(entries),
                    "categories": [e.get("category", "") for e in entries if "category" in e],
                    "terms_with_formulas": len([e for e in entries if "formula" in e]),
                }
                assert_snapshot(self, "glossary_structure", state)
            finally:
                sys.modules.pop(mod_name, None)
                if old_mod is not None:
                    sys.modules[mod_name] = old_mod


class TestHelpTextsSnapshot(unittest.TestCase):
    """도움말 텍스트 구조 스냅샷."""

    def test_help_modules_covered(self):
        """모든 게임 모듈에 도움말이 있는지 확인."""
        from unittest.mock import MagicMock, patch

        _pg_mock = MagicMock()
        _pg_mock.KEYDOWN = 768
        _pg_mock.K_F1 = 282
        _pg_mock.K_ESCAPE = 27
        _pg_mock.SRCALPHA = 0x00010000

        with patch.dict(sys.modules, {"pygame": _pg_mock}):
            old_mod = sys.modules.pop("help_overlay", None)
            try:
                import help_overlay

                modules = sorted(help_overlay._HELP_TEXTS.keys())
                line_counts = {m: len(lines) for m, lines in help_overlay._HELP_TEXTS.items()}
                state = {"modules": modules, "line_counts": line_counts}
                assert_snapshot(self, "help_texts_structure", state)
            finally:
                sys.modules.pop("help_overlay", None)
                if old_mod is not None:
                    sys.modules["help_overlay"] = old_mod


if __name__ == "__main__":
    unittest.main()
