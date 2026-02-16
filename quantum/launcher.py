"""양자 역학 시뮬레이터 — 서브 메뉴 런처."""

from quantum.qubit_chain import open_qubit_chain
from quantum.tunneling import open_tunneling
from quantum.qec_shield import open_qec_shield
from ui.base_launcher import BaseLauncher


class QuantumLauncher(BaseLauncher):
    MODULE = "quantum"
    BUTTON_WIDTH = 42
    BUTTONS = [
        ("btn_qubit_chain", lambda self: self._launch_pygame(open_qubit_chain)),
        ("btn_tunneling",   lambda self: self._launch_pygame(open_tunneling)),
        ("btn_qec_shield",  lambda self: self._launch_pygame(open_qec_shield)),
    ]


def open_quantum_launcher(master=None):
    QuantumLauncher(master)
