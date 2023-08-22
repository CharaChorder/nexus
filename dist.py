#!/usr/bin/env python

# Install pyenv and configure the latest version globally before running this script.

import os
import sys
import argparse
import glob
from pathlib import Path

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


def run_command(command: str):
    ret: int = os.system(command)
    if ret != os.EX_OK:
        sys.exit(ret)


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
        run_command("python3 -m venv venv")
    else:
        print("Found existing virtual environment")

    # Install requirements
    print("Installing requirements...")
    run_command(f"{python_name} -m pip install --upgrade pip -r requirements.txt")

# Convert ui files to python
print("Converting ui files to python...")
run_command(f"{venv_path}pyside6-uic ui/main.ui -o src/nexus/ui/MainWindow.py")
run_command(f"{venv_path}pyside6-uic ui/banlist.ui -o src/nexus/ui/BanlistDialog.py")
run_command(f"{venv_path}pyside6-uic ui/banword.ui -o src/nexus/ui/BanwordDialog.py")
run_command(f"{venv_path}pyside6-uic ui/confirm.ui -o src/nexus/ui/ConfirmDialog.py")

# Generate translations
print("Generating TS templates...")
run_command(f"{venv_path}pyside6-lupdate " +
            ' '.join(glob.glob('ui/*.ui') + ["src/nexus/GUI.py"]) +
            " -ts translations/i18n_en.ts")
print("Generating QM files...")
os.makedirs('src/nexus/translations', exist_ok=True)
for i in glob.glob('translations/*.ts'):
    run_command(f"{venv_path}pyside6-lrelease {i} -qm src/nexus/translations/{Path(i).stem}.qm")

if not (args.no_build or args.ui_only):
    # Pyinstaller command - onefile, windowed, name, entrypoint
    build_cmd = "pyinstaller -Fwn nexus src/nexus/__main__.py"
    if os_name == "notwin":  # Add hidden imports for Linux
        build_cmd += " --hidden-import pynput.keyboard._xorg --hidden-import pynput.mouse._xorg"

    # Build executable
    print("Building executable...")
    run_command(f"{venv_path}{build_cmd}")

    # Rename darwin executable
    if os_name == "darwin":
        os.rename("dist/nexus", "dist/nexus-macos")

    # Copy README and LICENSE to dist
    if os_name == "win":
        run_command("copy README.md dist")
        run_command("copy LICENSE dist")
    else:
        run_command("cp README.md LICENSE dist")

if args.devel:
    # Install dev/test requirements
    print("Installing dev/test requirements...")
    run_command(f"{python_name} -m pip install --upgrade pip -r test-requirements.txt")

    # Setup git hooks
    print("Setting up git hooks...")
    run_command(f"{venv_path}pre-commit install")

    # Install module locally
    print("Installing module locally...")
    run_command(f"{python_name} -m pip install -e .")

print(f"Done!{' Built executable is in dist/' if not (args.no_build or args.ui_only) else ''}")
