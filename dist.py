#!/usr/bin/env python

# Install pyenv and configure the latest version globally before running this script.

import os
import sys

# Error and exit on Python version < 3.11
if sys.version_info < (3, 11):
    print("Python 3.11 or higher is required")
    sys.exit(1)

# Get OS
os_name = "notwin"
venv_path = "venv/bin/"
python_name = venv_path + "python"
if sys.platform.startswith("win"):
    os_name = "win"
    venv_path = "venv\\Scripts\\"
    python_name = venv_path + "python.exe"
elif sys.platform.startswith("darwin"):
    os_name = "darwin"
print(f"OS detected as {os_name}")

# Create virtual environment if it doesn't exist
if not os.path.isdir("venv"):
    print("Existing virtual environment not found, creating new one...")
    os.system("python -m venv venv")
else:
    print("Found existing virtual environment")

# Install requirements
print("Installing requirements...")
os.system(f"{python_name} -m pip install --upgrade pip -r requirements.txt -r test-requirements.txt")

# Pyinstaller command
build_cmd = "pyinstaller -Fn nexus src/nexus/__main__.py"
if os_name == "notwin":
    build_cmd += " --hidden-import pynput.keyboard._xorg --hidden-import pynput.mouse._xorg"

# Build executable
print("Building executable...")
os.system(f"{venv_path}{build_cmd}")

# Rename darwin executable
if os_name == "darwin":
    os.rename("dist/nexus", "dist/nexus-macos")

# Copy README and LICENSE to dist
if os_name == "win":
    os.system("copy README.md dist")
    os.system("copy LICENSE dist")
else:
    os.system("cp README.md LICENSE dist")

print("Done! Built executable is in dist/")

# Setup git hooks
print("Setting up git hooks...")
os.system(f"{venv_path}pre-commit install")
