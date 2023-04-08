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
os.system(f"pip install -r requirements.txt")

# Modify spec file to load hidden imports for PyInstaller (in case of headless build server)
hidden_imports = []
if os_name == "notwin":
    hiddenimports = ['pynput.keyboard._xorg', 'pynput.mouse._xorg']

# Build executable
os.system(f"pyinstaller -Fn nexus nexus/__main__.py --hidden-import {','.join(hidden_imports)}")

# Rename darwin executable
if os_name == "darwin":
    os.rename("dist/nexus", "dist/nexus-macos")
