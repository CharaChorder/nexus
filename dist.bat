@echo off
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r src\requirements.txt
pyinstaller src\win32.spec
