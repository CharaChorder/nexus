#!/usr/bin/env python

import os
import sys

# Error and exit on Python version < 3.11
if sys.version_info < (3, 11):
    print("Python 3.11 or higher is required")
    sys.exit(1)

# Create virtual environment if it doesn't exist
if not os.path.isdir("venv"):
    print("Existing virtual environment not found, creating new one...")
    os.system(f"{sys.executable} -m venv venv")
else:
    print("Found existing virtual environment")

# Get OS
os_name = "notwin"
if sys.platform.startswith("win"):
    os_name = "win"
elif sys.platform.startswith("darwin"):
    os_name = "darwin"
print(f"OS detected as {os_name}")

# Activate virtual environment
print("Activating virtual environment...")
if os_name == "win":
    os.system("venv\\Scripts\\activate.bat")
else:
    os.system("source venv/bin/activate")

# Install requirements
print("Installing requirements...")
os.system("python -m pip install --upgrade pip")
os.system("pip install -r requirements.txt")

# Pyinstaller command
cmd = "pyinstaller -Fn nexus src/nexus/__main__.py"
if os_name == "notwin":
    cmd += " --hidden-import pynput.keyboard._xorg --hidden-import pynput.mouse._xorg"

# Build executable
print("Building executable...")
os.system(cmd)

# Rename darwin executable
if os_name == "darwin":
    os.rename("dist/nexus", "dist/nexus-macos")

# Copy README and LICENSE to dist
os.system("cp README.md LICENSE dist")

print("Done! Built executable is in dist/")
