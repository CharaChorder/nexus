#!/usr/bin/env python

import os
import sys

# Error and exit on Python version < 3.11
if sys.version_info < (3, 11):
    print("Python 3.11 or higher is required")
    sys.exit(1)

# Create virtual environment if it doesn't exist
if not os.path.isdir("venv"):
    os.system(f"{sys.executable} -m venv venv")

# Get OS
os_name = "notwin"
if sys.platform.startswith("win"):
    os_name = "win"
elif sys.platform.startswith("darwin"):
    os_name = "darwin"

# Activate virtual environment
if os_name == "win":
    os.system("venv\\Scripts\\activate.bat")
else:
    os.system("source venv/bin/activate")

# Install requirements
os.system(f"pip install -r src/requirements.txt")

# Modify spec file to load hidden imports for PyInstaller (in case of headless build server)
spec = None
if os_name == "notwin":
    with open("src/nexus.spec", "r") as f:
        spec = f.read()
    modified_spec = spec.replace("hiddenimports=[],", "hiddenimports=['pynput.keyboard._xorg', 'pynput.mouse._xorg'],")
    with open("src/nexus.spec", "w") as f:
        f.write(modified_spec)

# Build executable
os.system(f"pyinstaller src/nexus.spec")

# Rename darwin executable
if os_name == "darwin":
    os.rename("dist/nexus", "dist/nexus-macos")

# Replace spec file with original if it was modified
if os_name == "notwin" and spec:
    with open("src/nexus.spec", "w") as f:
        f.write(spec)
