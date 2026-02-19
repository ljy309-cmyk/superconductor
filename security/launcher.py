"""첨단 센서 및 암호 보안 — 서브 메뉴 런처."""

from security.bb84_defense import open_bb84_defense
from security.qkd_advanced import open_qkd_advanced
from security.scada_security import open_scada_security
from security.squid_mines import open_squid_mines
from ui.base_launcher import BaseLauncher


class SecurityLauncher(BaseLauncher):
    MODULE = "security"
    BUTTON_WIDTH = 42
    BUTTONS = [
        ("btn_squid_mines", lambda self: self._launch_pygame(open_squid_mines)),
        ("btn_bb84", lambda self: self._launch_pygame(open_bb84_defense)),
        ("btn_scada_security", lambda self: self._launch_pygame(open_scada_security)),
        ("btn_qkd_advanced", lambda self: self._launch_pygame(open_qkd_advanced)),
    ]


def open_security_launcher(master=None):
    SecurityLauncher(master)
