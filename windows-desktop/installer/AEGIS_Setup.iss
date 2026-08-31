; AEGIS Capture Windows Installer — Inno Setup 6
#define MyAppName "AEGIS Capture"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "LeverageFx / Honeydewnuts"
#define MyAppURL "https://leveragefx.co"

[Setup]
AppId={{AEGIS-CAPTURE-WIN-2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=AEGIS_Capture_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; One-file PyInstaller output
Source: "dist\AEGIS_Capture.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "mq5\AEGIS_Executor.mq5"; DestDir: "{app}\mq5"; Flags: ignoreversion
Source: "assets\mt5_color_match_guide.jpg"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "guides\mt5_color_match_guide.jpg"; DestDir: "{app}\guides"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\AEGIS_Capture.exe"
Name: "{group}\MT5 Color Guide"; Filename: "{app}\assets\mt5_color_match_guide.jpg"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\AEGIS_Capture.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AEGIS_Capture.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
