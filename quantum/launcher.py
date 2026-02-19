"""양자 역학 시뮬레이터 — 서브 메뉴 런처."""

from quantum.entanglement import open_entanglement
from quantum.gate_builder import open_gate_builder
from quantum.qec_shield import open_qec_shield
from quantum.qubit_chain import open_qubit_chain
from quantum.grover_search import open_grover_search
from quantum.shor_algorithm import open_shor_algorithm
from quantum.tunneling import open_tunneling
from ui.base_launcher import BaseLauncher


class QuantumLauncher(BaseLauncher):
    MODULE = "quantum"
    BUTTON_WIDTH = 42
    BUTTONS = [
        ("btn_qubit_chain", lambda self: self._launch_pygame(open_qubit_chain)),
        ("btn_tunneling", lambda self: self._launch_pygame(open_tunneling)),
        ("btn_qec_shield", lambda self: self._launch_pygame(open_qec_shield)),
        ("btn_gate_builder", lambda self: self._launch_pygame(open_gate_builder)),
        ("btn_entanglement", lambda self: self._launch_pygame(open_entanglement)),
        ("btn_shor_algorithm", lambda self: self._launch_pygame(open_shor_algorithm)),
        ("btn_grover_search", lambda self: self._launch_pygame(open_grover_search)),
    ]


def open_quantum_launcher(master=None):
    QuantumLauncher(master)
