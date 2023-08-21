@echo off

echo Pulling latest changes...
git pull

echo Installing requirements
python -m pip install -r requirements.txt

echo Building Nexus...
python dist.py

echo Launching...
START /D .\dist .\dist\nexus.exe
