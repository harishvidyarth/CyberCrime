#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Build the FundTrail binary on Mac/Linux. Run this AFTER updating any feature.
#
# NOTE: this produces a Mac/Linux binary, NOT a Windows .exe — PyInstaller
# cannot cross-compile. To get FundTrail.exe, run build_exe.bat ON Windows.
#
# Output: dist/FundTrail   (a build artifact — NOT committed to git)
# ─────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "Installing build dependencies (PyInstaller + app requirements)..."
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller
python3 -m pip install pywebview
python3 -m pip install -r main/requirements.txt

echo ""
echo "Building FundTrail (this can take a few minutes)..."
python3 -m PyInstaller --noconfirm --clean FundTrail.spec

echo ""
if [[ -f "dist/FundTrail" ]]; then
    echo "============================================================"
    echo "  Done -> dist/FundTrail   (run it on this same OS)"
    echo "  Data persists in the per-user app data folder:"
    echo "    macOS/Linux: \$XDG_DATA_HOME/FundTrail or ~/.local/share/FundTrail"
    echo "  It survives rebuilds and app moves."
    echo "============================================================"
else
    echo "Build did NOT produce dist/FundTrail — scroll up for the error." >&2
    echo "Tip: if a module is missing, add it to hiddenimports in FundTrail.spec."
fi
