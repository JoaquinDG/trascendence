"""Shared bootstrap for the three validator front doors.

The validators live next to the templates they validate, because that is where
someone editing a charter will look for them. The logic lives in
`src/trascendence/`, because the detectors import it too. This file is the two
lines that join them, in one place rather than three.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
