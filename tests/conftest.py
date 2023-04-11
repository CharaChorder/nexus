import os
import sys


# xorg
if not (sys.platform.startswith("win") or sys.platform.startswith("darwin")):
    # Check for $DISPLAY
    if "DISPLAY" not in os.environ:
        os.environ["PYTEST-HEADLESS"] = "1"
