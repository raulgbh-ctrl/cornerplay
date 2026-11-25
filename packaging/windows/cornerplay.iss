; Inno Setup script for Cornerplay on Windows. Built by build.ps1:
;   iscc /DAppVersion=0.24.0 cornerplay.iss
; Installs for the current user only (no administrator rights), like the Linux installer.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1E0E7A-3B5B-4C55-9F0E-C0A7E7B1A0D1}
AppName=Cornerplay
AppVersion={#AppVersion}
AppVerName=Cornerplay {#AppVersion}
AppPublisher=Cornerplay
AppPublisherURL=https://github.com/raulgbh-ctrl/cornerplay
DefaultDirName={localappdata}\Programs\Cornerplay
DefaultGroupName=Cornerplay
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=cornerplay-{#AppVersion}-windows-setup
SetupIconFile=cornerplay.ico
UninstallDisplayIcon={app}\Cornerplay.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "nxm"; Description: "Open Nexus Mods ""Mod Manager Download"" links with Cornerplay"; Flags: unchecked

[Files]
Source: "..\..\dist\Cornerplay\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cornerplay"; Filename: "{app}\Cornerplay.exe"
Name: "{group}\Cornerplay (TV mode)"; Filename: "{app}\Cornerplay.exe"; Parameters: "--tv"
Name: "{autodesktop}\Cornerplay"; Filename: "{app}\Cornerplay.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\nxm"; ValueType: string; ValueData: "URL:Nexus Mods download"; Flags: uninsdeletekey; Tasks: nxm
Root: HKCU; Subkey: "Software\Classes\nxm"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Tasks: nxm
Root: HKCU; Subkey: "Software\Classes\nxm\shell\open\command"; ValueType: string; ValueData: """{app}\Cornerplay.exe"" --nxm ""%1"""; Tasks: nxm
; "Start with the PC" (Settings) writes this value; remove it with the app.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Cornerplay"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\Cornerplay.exe"; Description: "{cm:LaunchProgram,Cornerplay}"; Flags: nowait postinstall skipifsilent
; An update from inside Cornerplay runs this installer silently with /relaunch=yes: open the new
; version after. Other silent installs (winget, scripts) leave it closed, so nothing waits on it.
Filename: "{app}\Cornerplay.exe"; Flags: nowait; Check: WizardSilent and Relaunch

[Code]
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|no}') = 'yes';
end;

[UninstallRun]
Filename: "taskkill"; Parameters: "/IM Cornerplay.exe /F"; Flags: runhidden; RunOnceId: "StopCornerplay"
