@echo off
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
echo Detected Python:
python --version

echo Installing build dependencies (PyInstaller + app requirements)...
python -m pip install --upgrade pip
if %errorlevel% neq 0 exit /b %errorlevel%
REM Floor versions (not exact pins) so pip resolves a build compatible with the
REM installed Python — e.g. PyInstaller 6.11 on 3.11, 6.21+ on 3.14.
python -m pip install "pyinstaller>=6.11"
if %errorlevel% neq 0 exit /b %errorlevel%
python -m pip install "pywebview>=5.4"
if %errorlevel% neq 0 exit /b %errorlevel%
python -m pip install -r main\requirements.txt
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
echo Building FundTrail.exe (this can take a few minutes)...
python -m PyInstaller --noconfirm --clean FundTrail.spec

echo.
if exist "dist\FundTrail.exe" (
    echo ============================================================
    echo  Done.  Your app is:  dist\FundTrail.exe
    echo  Double-click it to run; the database is stored in
    echo  dist\FundTrail_data next to the exe and persists.
    echo ============================================================
) else (
    echo Build did NOT produce dist\FundTrail.exe -- scroll up for the error.
    echo Tip: if a module is missing, add it to hiddenimports in FundTrail.spec.
)
pause
