# FundTrail — End-User Installers (Windows + macOS)

Wizard/drag installers layered on top of the existing PyInstaller build. The
PyInstaller step is unchanged and still produces the binary; these wrap it for
non-technical end users.

| Layer | Windows | macOS |
|---|---|---|
| Binary build (unchanged) | `build_exe.bat` → `dist\FundTrail.exe` | `./build_exe.sh` → `dist/FundTrail` |
| Installer wrapper (new) | `FundTrail.iss` → `dist\FundTrail_Setup.exe` | `./build_dmg.sh` → `dist/FundTrail.dmg` |
| Shortcut/launcher | Start Menu + optional Desktop | Applications → Dock/Launchpad |
| Data folder (never wiped) | `%LOCALAPPDATA%\FundTrail` | `~/.local/share/FundTrail` |

---

## Windows — Inno Setup

`FundTrail.iss` supersedes the old `installer.iss`. `build_exe.bat` auto-compiles
it if Inno Setup is found (and tries `winget install` if not).

### Manual compile
1. Build the binary: double-click **`build_exe.bat`** → produces `dist\FundTrail.exe`.
2. Install Inno Setup 6 (free): <https://jrsoftware.org/isdl.php>
   or `winget install --id JRSoftware.InnoSetup -e`.
3. Compile:
   ```
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FundTrail.iss
   ```
   (or right-click `FundTrail.iss` → **Compile**, or open in the IDE and press **F9**)
4. Output: **`dist\FundTrail_Setup.exe`** — ship this to end users.

### Wizard flow produced
Welcome → License (LICENSE) → Choose install location → Select Additional Tasks
(Desktop shortcut, checked by default) → Ready to Install → Installing → Finish
(with "Launch FundTrail"). Adds a Start Menu entry and an **Apps & Features**
uninstaller.

### Data safety
The installer writes only to the install dir (`Program Files\FundTrail`) and the
shortcuts. Case data lives in `%LOCALAPPDATA%\FundTrail` and is **never** touched
by install, upgrade, or uninstall. The fixed `AppId` GUID makes upgrades replace
in place. Do not add an `[UninstallDelete]` entry for the data folder.

### Optional branded installer icon
```
# from a real .ico (e.g. produced by an image tool or Pillow):
python -c "from PIL import Image; Image.open('main/static/logo.png').save('installer_icon.ico', sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])"
```
Then uncomment `SetupIconFile=installer_icon.ico` in `FundTrail.iss`.

---

## macOS — drag-to-Applications .dmg

Chosen format: **.dmg** (standard Mac pattern), built with `build_dmg.sh` using
only OS tools (`sips`, `iconutil`, `hdiutil`, `osascript`) — no third-party deps.

### Build
```
./build_exe.sh      # produces dist/FundTrail  (build ON a Mac; no cross-compile)
./build_dmg.sh      # produces dist/FundTrail.app and dist/FundTrail.dmg
```
The script builds a proper `.app` bundle (Info.plist + icon), then a compressed
`.dmg` whose window shows **FundTrail.app** next to an **Applications** alias so
the user drags across. Once in `/Applications`, the app appears in Launchpad and
can be kept in the Dock — no extra step.

### Data safety
Case data lives in `~/.local/share/FundTrail`; dragging the app in or out of
`/Applications` never touches it.

---

## ⚠️ macOS code-signing / notarization (real limitation — do not skip)

`build_dmg.sh` produces an **unsigned (ad-hoc) app** — verified: `codesign`
reports `Signature=adhoc`, `TeamIdentifier=not set`. On any Mac other than the
build machine, Gatekeeper will block first launch:

> "FundTrail can't be opened because Apple cannot check it for malicious software."

**End-user workaround (per machine, once):** right-click the app → **Open** →
**Open** in the dialog; or System Settings → Privacy & Security → **Open Anyway**.

**Proper fix (requires paid Apple Developer ID — $99/yr):**
```
codesign --deep --force --options runtime \
  --sign "Developer ID Application: <NAME> (<TEAMID>)" dist/FundTrail.app
xcrun notarytool submit dist/FundTrail.dmg \
  --apple-id <APPLE_ID> --team-id <TEAMID> --password <APP_SPECIFIC_PW> --wait
xcrun stapler staple dist/FundTrail.dmg
```
Without a Developer ID there is **no way** to remove the Gatekeeper warning for
other users — this is an Apple platform constraint, not a build defect.

> Windows note: `FundTrail_Setup.exe` is also unsigned, so SmartScreen may show
> "Windows protected your PC" → **More info → Run anyway**. An Authenticode
> code-signing certificate removes it (separate paid cert).
