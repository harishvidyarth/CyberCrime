; Inno Setup script for FundTrail. Compile on Windows with Inno Setup (ISCC.exe)
; AFTER building dist\FundTrail.exe via build_exe.bat. Produces dist\FundTrail_Setup.exe.

[Setup]
AppName=FundTrail
AppVersion=3.0
DefaultDirName={autopf}\FundTrail
DefaultGroupName=FundTrail
UninstallDisplayIcon={app}\FundTrail.exe
OutputDir=dist
OutputBaseFilename=FundTrail_Setup
PrivilegesRequired=admin

[Files]
Source: "dist\FundTrail.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\FundTrail"; Filename: "{app}\FundTrail.exe"
Name: "{commondesktop}\FundTrail"; Filename: "{app}\FundTrail.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\FundTrail.exe"; Description: "Launch FundTrail"; Flags: postinstall nowait skipifsilent
