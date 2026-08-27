; Inno Setup script — build after PyInstaller produces dist\AEGIS_Capture.exe
#define MyAppName "AEGIS Capture"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "LeverageFx / Honeydewnuts"
#define MyAppURL "https://leveragefx.co"

[Setup]
AppId={{AEGIS-CAPTURE-2026}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\AEGIS Capture
DefaultGroupName=AEGIS
OutputBaseFilename=AEGIS_Capture_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\aegis_capture\dist\AEGIS_Capture.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\mq5\AEGIS_Executor.mq5"; DestDir: "{app}\mq5"; Flags: ignoreversion

[Icons]
Name: "{group}\AEGIS Capture"; Filename: "{app}\AEGIS_Capture.exe"
Name: "{autodesktop}\AEGIS Capture"; Filename: "{app}\AEGIS_Capture.exe"

[Run]
Filename: "{app}\AEGIS_Capture.exe"; Description: "Launch AEGIS Capture"; Flags: nowait postinstall skipifsilent
