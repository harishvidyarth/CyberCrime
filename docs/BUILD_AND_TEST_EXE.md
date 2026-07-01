# FundTrail — Building & Testing the Windows `.exe` / Installer

This guide covers (A) testing a prebuilt FundTrail executable, (B) building the
`FundTrail_Setup.exe` graphical installer from source on Windows, (C) installing and
opening it, and (D) the macOS alternative.

> **Platform rule:** a Windows `.exe` and the `FundTrail_Setup.exe` installer can **only
> be produced on Windows** (PyInstaller emits a binary for the OS it runs on, and Inno
> Setup is Windows-only). You cannot build the Windows installer on macOS/Linux — use a
> Windows 10/11 machine. For macOS, see section D.

---

## What already exists in this project
| Artifact | Path | Platform | Notes |
|---|---|---|---|
| Prebuilt app binary | `old_files/prebuilt-dist/dist/FundTrail.exe` | Windows | One-folder PyInstaller build (keep it inside its folder). |
| Mac app + disk image | `new_files/dist/FundTrail.app`, `new_files/dist/FundTrail.dmg` | macOS | Built earlier via `build_dmg.sh`. |
| Graphical installer | *(not built yet)* `dist/FundTrail_Setup.exe` | Windows | Produced by section B. |

The build inputs live in the repo root: `build_exe.bat` (Windows build script),
`FundTrail.spec` (PyInstaller recipe), `FundTrail.iss` (Inno Setup installer recipe),
`run_exe.py` (the desktop launcher that starts the Flask app).

---

## A. Test a prebuilt `FundTrail.exe` (Windows, no build needed)
1. Copy the **whole** `dist\FundTrail\` folder to the Windows machine (the loose
   `FundTrail.exe` needs the sibling `_internal\` folder — don't move the exe out alone).
2. Double-click **`FundTrail.exe`**. A desktop window opens and the bundled web app starts
   on **http://127.0.0.1:5050** (port 5050 — 5000 is used by AirPlay on some systems).
3. **First-run credentials:** on first launch the app creates an admin + officer with
   **random** passwords and writes them to
   **`%LOCALAPPDATA%\FundTrail\INITIAL_CREDENTIALS.txt`**. Open that file to log in, then
   change the password when prompted.
4. **Smoke test:** log in as admin → upload a sample
   `BankAction_CompleteTrail*.xlsx` → open the case → confirm the fund-flow graph renders,
   the Put-On-Hold summary opens, and a state/UT-wise summary appears.
5. **Data location:** all case data lives in **`%LOCALAPPDATA%\FundTrail`** (not inside
   the app folder), so it **survives** rebuilds, upgrades, and uninstall.

---

## B. Build `FundTrail_Setup.exe` from source (Windows)
**Prerequisites**
- **Python 3.11 or 3.12** from python.org (the app is tested on 3.11; 3.13/3.14 wheels may
  lag). Tick *"Add Python to PATH"* during install.
- **Inno Setup 6** (free): https://jrsoftware.org/isdl.php — or
  `winget install --id JRSoftware.InnoSetup -e`. `build_exe.bat` will try to auto-install
  it if missing.

**Steps**
1. Open **Command Prompt** in the repo root (the folder containing `build_exe.bat`).
2. Run:
   ```bat
   build_exe.bat
   ```
   The script: upgrades pip → installs PyInstaller + pywebview + `main\requirements.txt`
   → kills any running `FundTrail.exe` → clears old `build\`/`dist\` → runs
   `PyInstaller --noconfirm --clean FundTrail.spec` → then compiles `FundTrail.iss` with
   Inno Setup.
3. On success you get two outputs in `dist\`:
   - **`dist\FundTrail\FundTrail.exe`** — the runnable app (one-folder build).
   - **`dist\FundTrail_Setup.exe`** — the graphical wizard installer (this is the
     "setup.exe").

**If the build fails**
- *"Could not find ISCC"* → install Inno Setup 6, reopen Command Prompt, re-run.
- *Missing module at runtime* → add it to `hiddenimports` in `FundTrail.spec`, rebuild.
- *PermissionError on `_internal\*.pyd`* → close any running `FundTrail.exe` first.

---

## C. Install & open the `Setup.exe`
1. Double-click **`FundTrail_Setup.exe`**. The wizard runs: Welcome → License → choose
   install location (default `C:\Program Files\FundTrail`) → Ready → Installing → Finish.
2. It adds a **Start Menu** entry (and an optional **Desktop** shortcut) and an entry in
   **Apps & Features** for clean uninstall.
3. Launch **FundTrail** from the Start Menu; it opens on **http://127.0.0.1:5050** exactly
   as in section A. Log in using `%LOCALAPPDATA%\FundTrail\INITIAL_CREDENTIALS.txt`.
4. **Upgrades/uninstall** keep your data: the installer never touches
   `%LOCALAPPDATA%\FundTrail`, so reinstalling a newer build preserves all cases.

> Tip: the installer's AppId GUID in `FundTrail.iss` is fixed — keep it unchanged so
> future versions upgrade in place instead of installing side-by-side.

---

## D. macOS alternative (`.app` / `.dmg`)
On a Mac, build the desktop app with:
```bash
./build_dmg.sh
```
This produces `dist/FundTrail.app` and `dist/FundTrail.dmg`. Open the `.dmg`, drag
**FundTrail** to Applications, launch it, and it serves the same app on
http://127.0.0.1:5050 with data in `~/Library/Application Support/FundTrail` (or the
configured per-user data dir).

---

## Quick reference
| Item | Value |
|---|---|
| App URL | `http://127.0.0.1:5050` |
| First-run credentials file | `%LOCALAPPDATA%\FundTrail\INITIAL_CREDENTIALS.txt` (Windows) |
| Data directory (persists) | `%LOCALAPPDATA%\FundTrail` (Windows) |
| Build script | `build_exe.bat` (Windows) · `build_dmg.sh` (macOS) |
| Installer output | `dist\FundTrail_Setup.exe` |
| Build on macOS for Windows? | **No** — build the Windows installer on Windows. |

See also `docs/INSTALLERS.md` for icon generation and signing notes.
