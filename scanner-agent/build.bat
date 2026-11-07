
@echo off
setlocal

cd /d "%~dp0"

set PYTHON=venv-build\Scripts\python.exe

echo =====================================
echo   Fingerprint Scanner Agent Builder
echo =====================================

if not exist "%PYTHON%" (
    echo ERROR: Build environment not found.
    goto error
)

if not exist "config\.env" (
    echo ERROR: config\.env not found.
    goto error
)

echo.
echo [1/4] Checking dependencies...

%PYTHON% -c "from pyzkfp import ZKFP2; import clr; import flask; print('Dependencies OK')"
if errorlevel 1 goto error

echo.
echo [2/4] Cleaning previous build...

if exist build rmdir /s /q build
if exist dist\ScannerAgent rmdir /s /q dist\ScannerAgent

echo.
echo [3/4] Building ScannerAgent.exe...

%PYTHON% -m PyInstaller --clean --noconfirm ScannerAgent.spec
if errorlevel 1 goto error

echo.
echo [4/4] Copying configuration...

if not exist "dist\ScannerAgent\config" mkdir "dist\ScannerAgent\config"

copy /Y "config\.env" "dist\ScannerAgent\config\.env"
if errorlevel 1 goto error

echo.
echo =====================================
echo   BUILD SUCCESSFUL
echo =====================================
echo.
echo Output: dist\ScannerAgent\ScannerAgent.exe
echo.
pause
exit /b 0

:error
echo.
echo =====================================
echo   BUILD FAILED
echo =====================================
pause
exit /b 1
