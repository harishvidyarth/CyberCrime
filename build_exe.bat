@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ─────────────────────────────────────────────────────────────────────────
REM Build FundTrail.exe on Windows. Run this AFTER updating any feature.
REM Output: dist\FundTrail.exe  (a build artifact — NOT committed to git)
REM
REM   Double-click build_exe.bat   (or run it from a Command Prompt)
REM ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

REM ─────────────────────────────────────────────────────────────────────────
REM RECOMMENDED Python: 3.11 or 3.12 (the app is tested on 3.11). Python 3.13/3.14
REM are very new and some wheels (pandas/pywebview) may lag. If a wheel below fails
REM to install, install Python 3.12 from python.org and re-run this script with it.
REM ─────────────────────────────────────────────────────────────────────────
echo [%date% %time%] Build started
echo Detected Python:
python --version

echo [%date% %time%] Installing build dependencies (PyInstaller + app requirements)...
python -m pip install --upgrade pip
if %errorlevel% neq 0 exit /b %errorlevel%
REM No version pins on the build tools: always pull the LATEST PyInstaller / pywebview
REM that pip can install for the Python in use. This avoids "Could not find a version
REM that satisfies the requirement ...==X" whenever a pinned build has no wheel yet.
python -m pip install --upgrade pyinstaller
if %errorlevel% neq 0 exit /b %errorlevel%
python -m pip install --upgrade pywebview
if %errorlevel% neq 0 exit /b %errorlevel%
python -m pip install -r main\requirements.txt
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
REM Close any running FundTrail.exe and clear old build output FIRST. A still-running
REM app keeps dist\FundTrail\_internal\*.pyd locked, which makes PyInstaller fail with
REM "PermissionError: [WinError 5] Access is denied: ...\_internal\...pyd".
echo [%date% %time%] Closing any running FundTrail.exe and clearing old build output...
taskkill /f /im FundTrail.exe >nul 2>&1
rmdir /s /q build >nul 2>&1
rmdir /s /q dist  >nul 2>&1

echo.
REM Fix: build optimisation — abort BEFORE the slow PyInstaller step if app.py
REM does not even parse (catches syntax errors in seconds instead of minutes).
echo [%date% %time%] Pre-build syntax gate on main\app.py...
python -c "import ast; ast.parse(open('main/app.py',encoding='utf-8').read())" || (echo ABORT: app.py syntax error && exit /b 1)

echo [%date% %time%] Building FundTrail.exe (this can take a few minutes)...
python -m PyInstaller --noconfirm --clean FundTrail.spec

echo.
if exist "dist\FundTrail\FundTrail.exe" (
    echo ============================================================
    echo  Done.  Your app is:  dist\FundTrail\FundTrail.exe
    echo  Double-click it to run (keep it inside its folder).
    echo  Runtime data is stored in %%LOCALAPPDATA%%\FundTrail
    echo  and persists across rebuilds and installer upgrades.
    echo.
    echo  Creating Windows installer...
    echo ============================================================

    REM Use !ProgramFiles(x86)! (delayed expansion), NOT %ProgramFiles(x86)%: the
    REM literal ")" in "(x86)" closes this parenthesised if-block at parse time and
    REM causes ". was unexpected at this time".
    set "ISCC="
    for %%I in (ISCC.exe) do set "ISCC=%%~$PATH:I"
    if not defined ISCC if exist "!ProgramFiles(x86)!\Inno Setup 6\ISCC.exe" set "ISCC=!ProgramFiles(x86)!\Inno Setup 6\ISCC.exe"
    if not defined ISCC if exist "!ProgramFiles!\Inno Setup 6\ISCC.exe" set "ISCC=!ProgramFiles!\Inno Setup 6\ISCC.exe"

    if not defined ISCC (
        echo Inno Setup compiler not found. Trying to install it with winget...
        winget install --id JRSoftware.InnoSetup -e --silent
        if exist "!ProgramFiles(x86)!\Inno Setup 6\ISCC.exe" set "ISCC=!ProgramFiles(x86)!\Inno Setup 6\ISCC.exe"
        if not defined ISCC if exist "!ProgramFiles!\Inno Setup 6\ISCC.exe" set "ISCC=!ProgramFiles!\Inno Setup 6\ISCC.exe"
    )

    if defined ISCC (
        "!ISCC!" FundTrail.iss
        if exist "dist\FundTrail_Setup.exe" (
            echo.
            echo ============================================================
            echo  Installer ready: dist\FundTrail_Setup.exe
            echo  Install this on the target Windows machine.
            echo ============================================================
        ) else (
            echo Installer build did not produce dist\FundTrail_Setup.exe.
        )
    ) else (
        echo Could not find or auto-install Inno Setup.
        echo Install Inno Setup manually, then compile FundTrail.iss.
    )
) else (
    echo [%date% %time%] Build did NOT produce dist\FundTrail\FundTrail.exe -- scroll up for the error.
    echo Tip: if a module is missing, add it to hiddenimports in FundTrail.spec.
    pause
    exit /b 1
)
echo [%date% %time%] Build finished
pause
