#define MiApp "Salud de mi equipo Lite"
#define MiVersion "0.5.3 Lite"
#define MiExe "SaludPC-Lite.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}
AppName={#MiApp}
AppVersion={#MiVersion}
AppPublisher=SaludPC
DefaultDirName={pf}\SaludPC Lite
DefaultGroupName={#MiApp}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\dist_instalador
OutputBaseFilename=SaludPC-Setup-0.5.3-Lite
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\{#MiExe}
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Dirs]
Name: "{commonappdata}\SaludPC"; Permissions: users-modify

[Files]
Source: "..\dist\SaludPC-Lite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MiApp}"; Filename: "{app}\{#MiExe}"; Parameters: "--panel"
Name: "{group}\Desinstalar {#MiApp}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MiApp}"; Filename: "{app}\{#MiExe}"; Parameters: "--panel"

[Run]
; Crear tareas programadas con schtasks (sin depender de PowerShell)
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /TN ""SaludPC Lite Servicio"" /TR ""{app}\{#MiExe} --servicio"" /SC ONLOGON /RU ""{username}"" /RL HIGHEST /F"; Flags: runhidden waituntilterminated
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /TN ""SaludPC Lite Panel"" /TR ""{app}\{#MiExe} --panel"" /SC ONLOGON /DELAY 0000:20 /RU ""{username}"" /F"; Flags: runhidden waituntilterminated
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /TN ""SaludPC Lite Vigia"" /TR ""{app}\{#MiExe} --vigia"" /SC MINUTE /MO 5 /RU ""{username}"" /RL HIGHEST /F"; Flags: runhidden waituntilterminated

; Arrancar el servicio justo después de instalar
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN ""SaludPC Lite Servicio"""; Flags: runhidden nowait

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SaludPC Lite Servicio"" /F"; Flags: runhidden
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SaludPC Lite Panel"" /F"; Flags: runhidden
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SaludPC Lite Vigia"" /F"; Flags: runhidden
