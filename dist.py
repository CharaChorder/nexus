#!/usr/bin/env python

# Install pyenv and configure the latest version globally before running this script.

import os
import sys
import argparse

# Error and exit on Python version < 3.11
if sys.version_info < (3, 11):
    print("Python 3.11 or higher is required")
    sys.exit(1)

parser = argparse.ArgumentParser(description="Build Nexus")
parser.add_argument('-n', "--no-build", action="store_true", help="Skip building the executable, only setup")
parser.add_argument('-d', "--devel", action="store_true", help="Install module locally and git hooks")
parser.add_argument('-u', "--ui-only", action="store_true", help="Only convert ui files"
                                                                 "(you must first have set up a venv and installed the"
                                                                 "requirements to run this)")
parser.add_argument("--venv-path", type=str, help="[Relative] path to virtual environment to use")
args = parser.parse_args()

# Get OS
os_name = "notwin"
venv_path = f"{args.venv_path if args.venv_path else 'venv'}/bin/"
python_name = venv_path + "python"
if sys.platform.startswith("win"):
    os_name = "win"
    venv_path = "venv\\Scripts\\"
    python_name = venv_path + "python.exe"
elif sys.platform.startswith("darwin"):
    os_name = "darwin"
print(f"OS detected as {os_name}")

if not args.ui_only:
    # Create virtual environment if it doesn't exist
    if not os.path.isdir("venv"):
        print("Existing virtual environment not found, creating new one...")
        os.system("python -m venv venv")
    else:
        print("Found existing virtual environment")

    # Install requirements
    print("Installing requirements...")
    os.system(f"{python_name} -m pip install --upgrade pip -r requirements.txt")

# Convert ui files to python
print("Converting ui files to python...")
os.system(f"{venv_path}pyside6-uic ui/main.ui -o src/nexus/ui/MainWindow.py")
os.system(f"{venv_path}pyside6-uic ui/banlist.ui -o src/nexus/ui/BanlistDialog.py")
os.system(f"{venv_path}pyside6-uic ui/banword.ui -o src/nexus/ui/BanwordDialog.py")
os.system(f"{venv_path}pyside6-uic ui/confirm.ui -o src/nexus/ui/ConfirmDialog.py")

if not (args.no_build or args.ui_only):
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

if args.devel:
    # Install dev/test requirements
    print("Installing dev/test requirements...")
    os.system(f"{python_name} -m pip install --upgrade pip -r test-requirements.txt")

    # Setup git hooks
    print("Setting up git hooks...")
    os.system(f"{venv_path}pre-commit install")

    # Install module locally
    print("Installing module locally...")
    os.system(f"{python_name} -m pip install -e .")

print(f"Done!{' Built executable is in dist/' if not (args.no_build or args.ui_only) else ''}")
