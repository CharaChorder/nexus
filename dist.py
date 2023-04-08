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

# Activate virtual environment
if sys.platform.startswith("win"):
    os.system("venv\\Scripts\\activate.bat")
else:
    os.system("source venv/bin/activate")

# Install requirements
os.system(f"pip install -r src/requirements.txt")

# Build executable
if sys.platform.startswith("win"):
    os.system(f"pyinstaller src/win.spec")
elif sys.platform.startswith("darwin"):
    os.system(f"pyinstaller src/darwin.spec")
    os.rename("dist/nexus", "dist/nexus-macos")
else:
    os.system(f"pyinstaller src/xorg.spec")
