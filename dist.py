#!/usr/bin/env python

import os
import sys

# Error and exit on Python version < 3.11
if sys.version_info < (3, 11):
    print("Python 3.11 or higher is required")
    sys.exit(1)

# Get OS
os_name = "notwin"
python_name = "python"
if sys.platform.startswith("win"):
    os_name = "win"
    python_name = "py"
elif sys.platform.startswith("darwin"):
    os_name = "darwin"
print(f"OS detected as {os_name}")

# Create virtual environment if it doesn't exist
if not os.path.isdir("venv"):
    print("Existing virtual environment not found, creating new one...")
    os.system(f"{python_name} -m venv venv")
else:
    print("Found existing virtual environment")

# Activate virtual environment
print("Activating virtual environment and installing requirements...")
activate_cmd = "source venv/bin/activate"
if os_name == "win":
    activate_cmd = "venv\\Scripts\\Activate.ps1"

# Install requirements
os.system(f"{activate_cmd};"
          "python -m pip install --upgrade pip;"
          "python -m pip install -r requirements.txt;"
          "python -m pip install -r test-requirements.txt")

# Pyinstaller command
build_cmd = "pyinstaller -Fn nexus src/nexus/__main__.py"
if os_name == "notwin":
    build_cmd += " --hidden-import pynput.keyboard._xorg --hidden-import pynput.mouse._xorg"

# Build executable
print("Building executable...")
os.system(f"{activate_cmd}; {build_cmd}")

# Rename darwin executable
if os_name == "darwin":
    os.rename("dist/nexus", "dist/nexus-macos")

# Copy README and LICENSE to dist
if os_name == "win":
    os.system("copy README.md LICENSE dist")
else:
    os.system("cp README.md LICENSE dist")

print("Done! Built executable is in dist/")

# Setup git hooks
print("Setting up git hooks...")
os.system(f"{activate_cmd}; pre-commit install")
