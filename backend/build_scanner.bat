@echo off
cd /d "%~dp0"

echo Installing dependencies...
python -m pip install -r requirements-scanner.txt

echo Building Scanner Agent...
python -m PyInstaller scanner.spec --clean

pause