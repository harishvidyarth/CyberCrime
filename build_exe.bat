@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM Build FundTrail.exe on Windows. Run this AFTER updating any feature.
REM Output: dist\FundTrail.exe  (a build artifact — NOT committed to git)
REM
REM   Double-click build_exe.bat   (or run it from a Command Prompt)
REM ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

echo Installing build dependencies (PyInstaller + app requirements)...
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m pip install pywebview
python -m pip install -r main\requirements.txt

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
