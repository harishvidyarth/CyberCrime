; ─────────────────────────────────────────────────────────────────────────────
;  FundTrail.iss — Inno Setup wizard installer for FundTrail (Windows)
;
;  Supersedes the minimal installer.iss. Wraps the PyInstaller output
;  dist\FundTrail.exe into a wizard-style installer: Welcome → License →
;  Install location → Ready → Installing → Finish, with Start Menu + optional
;  Desktop shortcuts and an "Apps & Features" uninstaller.
;
;  PREREQUISITES
;    1. Build the binary first:  build_exe.bat   (produces dist\FundTrail.exe)
;    2. Install Inno Setup 6 (free):  https://jrsoftware.org/isdl.php
;       or:  winget install --id JRSoftware.InnoSetup -e
;
;  COMPILE (produces dist\FundTrail_Setup.exe):
;       "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" FundTrail.iss
;    or right-click FundTrail.iss → "Compile", or open in the Inno Setup IDE → F9.
;
;  DATA SAFETY: runtime case data lives in %LOCALAPPDATA%\FundTrail (set by
;  run_exe.py), NEVER inside {app}. The installer touches only {app} and the
;  shortcuts, so reinstall / upgrade / uninstall all preserve existing case data.
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName "FundTrail"
#define MyAppVersion "3.0"
#define MyAppPublisher "Tamil Nadu Cyber Crime Wing"
#define MyAppExeName "FundTrail.exe"

[Setup]
; A FIXED AppId keeps upgrades in-place and the uninstall entry stable across
; versions. Do NOT change this GUID once shipped.
AppId={{6F3A1B2C-9D4E-4A77-B1F0-FA11D0CA5E01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Show the proprietary licence as a wizard page (Welcome → License → ...).
LicenseFile=LICENSE
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
OutputDir=dist
OutputBaseFilename=FundTrail_Setup
; Fix: build optimisation — ultra64 gives a smaller installer than lzma2/max
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Fix: build optimisation — WebView2 + bundled Python need Windows 10+
MinVersion=10.0
; NOTE: no Python-presence [Code] check is needed — the PyInstaller bundle
; ships its own Python runtime inside dist\FundTrail\_internal.
; Install for all users into Program Files (data still per-user, see note above).
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
; Fix: Issue 5 — branded installer icon (same multi-size .ico the exe embeds)
SetupIconFile=main\static\img\fundtrail.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Default-checked desktop shortcut option on the "Select Additional Tasks" page.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; PyInstaller builds in one-DIR mode (faster startup — no per-launch extraction),
; so the whole dist\FundTrail\ folder ships. The launcher exe lands at
; {app}\FundTrail.exe (folder root), so the shortcuts below still point there.
Source: "dist\FundTrail\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
; Start Menu entry.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Optional Desktop shortcut (checkbox, checked by default via the task above).
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; NOTE: there is deliberately NO [UninstallDelete] entry for the data folder.
; Removing %LOCALAPPDATA%\FundTrail here would destroy the user's case database.
