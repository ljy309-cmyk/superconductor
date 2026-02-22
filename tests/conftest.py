"""conftest.py — 테스트 세션 전역 설정.

MPLBACKEND 환경변수를 설정하여 matplotlib가 항상 비-GUI(Agg) 백엔드를 사용하도록 한다.
이로써 tkinter 미설치 환경에서도 matplotlib 관련 테스트가 안정적으로 동작한다.
"""

import os

os.environ.setdefault("MPLBACKEND", "Agg")
