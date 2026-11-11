; Inno Setup script for the DrawFont Windows installer.
; Built by GitHub Actions:  ISCC /DAppVersion=1.2.3 installer\drawfont.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Keep this AppId forever: it is how Windows (and updates) recognise DrawFont as the same app.
AppId={{6F2D8E1B-3A47-4C59-9B6E-D1F0A7C4E852}
AppName=DrawFont
AppVersion={#AppVersion}
AppVerName=DrawFont {#AppVersion}
AppPublisher=DrawFont
DefaultDirName={autopf}\DrawFont
DefaultGroupName=DrawFont
DisableProgramGroupPage=yes
; Per-user install: no administrator prompt, so automatic updates are one click.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=DrawFont-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DrawFont.exe
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\DrawFont.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\DrawFont"; Filename: "{app}\DrawFont.exe"
Name: "{autodesktop}\DrawFont"; Filename: "{app}\DrawFont.exe"; Tasks: desktopicon

[Run]
; Also runs after a silent (automatic) update, so DrawFont reopens by itself.
Filename: "{app}\DrawFont.exe"; Description: "Open DrawFont"; Flags: nowait postinstall
