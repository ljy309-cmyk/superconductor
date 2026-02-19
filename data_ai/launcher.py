"""데이터 사이언스, AI & 글로벌 서버 — 서브 메뉴 런처."""

from data_ai.qrng_logger import open_qrng_logger
from data_ai.ranking import open_ranking
from data_ai.tc_predictor import open_tc_predictor
from replay_viewer import open_replay_viewer
from stats_dashboard import open_stats_dashboard
from ui.base_launcher import BaseLauncher


class DataAILauncher(BaseLauncher):
    MODULE = "data_ai"
    BUTTON_WIDTH = 42
    BUTTONS = [
        ("btn_tc_predictor", lambda self: open_tc_predictor(self)),
        ("btn_qrng", lambda self: open_qrng_logger(self)),
        ("btn_ranking", lambda self: open_ranking(self)),
        ("btn_stats", lambda self: open_stats_dashboard(self)),
        ("btn_replay_viewer", lambda self: open_replay_viewer(self)),
    ]


def open_data_ai_launcher(master=None):
    DataAILauncher(master)
