"""초전도 물리 엔진 — 서브 메뉴 런처."""

from physics.phase_transition import open_phase_transition
from physics.flux_pinning import open_flux_pinning
from ui.base_launcher import BaseLauncher


class PhysicsLauncher(BaseLauncher):
    MODULE = "physics"
    BUTTON_WIDTH = 42
    BUTTONS = [
        ("btn_phase_transition", lambda self: open_phase_transition(self)),
        ("btn_flux_pinning",     lambda self: self._launch_pygame(open_flux_pinning)),
    ]


def open_physics_launcher(master=None):
    PhysicsLauncher(master)
