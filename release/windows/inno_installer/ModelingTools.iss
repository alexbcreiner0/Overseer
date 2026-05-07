[Setup]
AppName=Overseer
AppVersion=1.0.0
DefaultDirName={localappdata}\Overseer
DefaultGroupName=Overseer
AppPublisherURL=https://github.com/alexbcreiner0/Overseer
AppSupportURL=https://github.com/alexbcreiner0/Overseer
AppUpdatesURL=https://github.com/alexbcreiner0/Overseer
UninstallDisplayIcon={app}\src\overseer\assets\icon.ico
OutputDir=.
OutputBaseFilename=Overseer-Setup
CreateUninstallRegKey=yes

[Files]
Source: "install.ps1"; DestDir: "{app}";
Source: "launcher.ps1"; DestDir: "{app}"
Source: "uninstall.ps1"; DestDir: "{app}"
Source: "launcher.pyw"; DestDir: "{app}"
Source: "..\..\..\src\*"; DestDir: "{app}\src"; Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\..\..\README.md"; DestDir: "{app}"
Source: "..\..\..\pyproject.toml"; DestDir: "{app}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install.ps1"""; Flags: waituntilterminated

[Icons]
Name: "{group}\Overseer"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\src\overseer\assets\icon.ico"
Name: "{commondesktop}\Overseer"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\src\overseer\assets\icon.ico"

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\uninstall.ps1"""; Flags: waituntilterminated
