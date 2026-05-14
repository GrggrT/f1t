; Inno Setup script for the packaged F1 League Agent launcher.
; Build prerequisites:
;   1. C:\f1t\agent\dist\F1LeagueAgent.exe must exist
;   2. The build script copies it to ..\backend\static\F1LeagueAgent.exe

#define MyAppName "F1 League Agent"
#define MyAppVersion "1.1"
#define MyAppPublisher "F1 League"
#define MyAppExeName "F1LeagueAgent.exe"

[Setup]
AppId={{B3F1A2E7-4C8D-4F6A-9E2B-1A3C5D7E9F0B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=Setup_F1LeagueAgent
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
WizardSizePercent=120
SetupLogging=yes
VersionInfoVersion=1.1.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=F1 League Agent launcher and telemetry collector
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce
Name: "startupicon"; Description: "Launch when Windows starts"; GroupDescription: "Autostart:"; Flags: unchecked

[Files]
Source: "..\backend\static\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{userappdata}\f1league_agent"

[Code]
function IsWebView2Installed(): Boolean;
var
  RegKey: String;
begin
  RegKey := 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := RegKeyExists(HKLM, RegKey) or RegKeyExists(HKCU, RegKey);
  if not Result then begin
    RegKey := 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
    Result := RegKeyExists(HKLM, RegKey) or RegKeyExists(HKCU, RegKey);
  end;
end;

function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if not IsWebView2Installed() then begin
    if MsgBox(
      'F1 League Agent needs Microsoft Edge WebView2 Runtime to render the launcher UI.' + #13#10 +
      'Windows 11 usually includes it already. On Windows 10 it may need a manual install.' + #13#10#13#10 +
      'Open the official WebView2 installer page now?',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open',
        'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
        '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then begin
    Exec('netsh', 'advfirewall firewall delete rule name="F1 League Agent UDP"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('netsh', 'advfirewall firewall add rule name="F1 League Agent UDP" dir=in action=allow protocol=UDP localport=20777 program="' + ExpandConstant('{app}\{#MyAppExeName}') + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then begin
    Exec('netsh', 'advfirewall firewall delete rule name="F1 League Agent UDP"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
