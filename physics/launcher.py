"""초전도 물리 엔진 — 서브 메뉴 런처."""

from physics.cooper_pair import open_cooper_pair
from physics.flux_pinning import open_flux_pinning
from physics.josephson_junction import open_josephson_junction
from physics.phase_transition import open_phase_transition
from physics.phase_transition_sim import open_phase_transition_sim
from ui.base_launcher import BaseLauncher


class PhysicsLauncher(BaseLauncher):
    MODULE = "physics"
    BUTTON_WIDTH = 42
    BUTTONS = [
        ("btn_phase_transition", lambda self: open_phase_transition(self)),
        ("btn_phase_transition_sim", lambda self: self._launch_pygame(open_phase_transition_sim)),
        ("btn_flux_pinning", lambda self: self._launch_pygame(open_flux_pinning)),
        ("btn_cooper_pair", lambda self: self._launch_pygame(open_cooper_pair)),
        ("btn_josephson", lambda self: self._launch_pygame(open_josephson_junction)),
    ]


def open_physics_launcher(master=None):
    PhysicsLauncher(master)
