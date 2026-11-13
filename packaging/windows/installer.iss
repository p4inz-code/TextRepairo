; SPDX-License-Identifier: GPL-3.0-or-later
; Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
; Inno Setup script. Build: iscc /DAppVersion=0.2.0 packaging\windows\installer.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6D1F7B52-3F0B-4E4A-9C53-7A2E5A1C0B11}
AppName=TextRepairo
AppVersion={#AppVersion}
AppPublisher=P4inz Interactive Labs
AppCopyright=Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
AppPublisherURL=https://github.com/p4inz-code/TextRepairo
DefaultDirName={autopf}\TextRepairo
DefaultGroupName=TextRepairo
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
AppSupportURL=https://github.com/p4inz-code/TextRepairo/issues
AppUpdatesURL=https://github.com/p4inz-code/TextRepairo/releases
OutputDir=..\..\dist
OutputBaseFilename=TextRepairo-Setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\TextRepairo.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Installs for the current user (no administrator prompt), so silent self-updates just work.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=yes
VersionInfoCompany=P4inz Interactive Labs
VersionInfoProductName=TextRepairo
; The data folder (models) is kept on uninstall.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\TextRepairo\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\TextRepairo"; Filename: "{app}\TextRepairo.exe"
Name: "{autodesktop}\TextRepairo"; Filename: "{app}\TextRepairo.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TextRepairo.exe"; Description: "Launch TextRepairo"; Flags: nowait postinstall skipifsilent
