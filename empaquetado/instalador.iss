#define MiApp "Salud de mi equipo"
#define MiVersion "0.5.3"
#define MiExe "SaludPC.exe"

[Setup]
AppId={{B6C1B9A4-7D2E-4F6B-9C31-8A5D2E7F1042}
AppName={#MiApp}
AppVersion={#MiVersion}
AppPublisher=SaludPC
DefaultDirName={autopf}\SaludPC
DefaultGroupName={#MiApp}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\dist_instalador
OutputBaseFilename=SaludPC-Setup-{#MiVersion}
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
Source: "..\dist\SaludPC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "instalar_tareas.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "PawnIO_setup.exe"; DestDir: "{tmp}"; Flags: ignoreversion deleteafterinstall

[InstallDelete]
; La versión anterior usaba el driver WinRing0, que Defender elimina.
Type: files; Name: "{app}\SaludPC.sys"

[Icons]
Name: "{group}\{#MiApp}"; Filename: "{app}\{#MiExe}"; Parameters: "--panel"
Name: "{group}\Reporte de la semana"; Filename: "{app}\{#MiExe}"; Parameters: "--reporte"
Name: "{group}\Desinstalar {#MiApp}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MiApp}"; Filename: "{app}\{#MiExe}"; Parameters: "--panel"

[Run]
; PawnIO es el driver firmado que usa la librería de sensores nueva para leer
; la temperatura del procesador y de la placa. Si ya está instalado, se saltea.
Filename: "{tmp}\PawnIO_setup.exe"; Parameters: "-install -silent"; StatusMsg: "Preparando los sensores de temperatura..."; Flags: runhidden waituntilterminated; Check: not PawnIoInstalado
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\instalar_tareas.ps1"" -Exe ""{app}\{#MiExe}"""; Flags: runhidden waituntilterminated
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN ""SaludPC Servicio"""; Flags: runhidden nowait
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN ""SaludPC Panel"""; Flags: runhidden nowait

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""SaludPC Vigia"""; Flags: runhidden; RunOnceId: "FinVigia"
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""SaludPC Servicio"""; Flags: runhidden; RunOnceId: "FinServicio"
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""SaludPC Panel"""; Flags: runhidden; RunOnceId: "FinPanel"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SaludPC Vigia"" /F"; Flags: runhidden; RunOnceId: "BorrarVigia"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SaludPC Servicio"" /F"; Flags: runhidden; RunOnceId: "BorrarServicio"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SaludPC Panel"" /F"; Flags: runhidden; RunOnceId: "BorrarPanel"

[Code]
function PawnIoInstalado(): Boolean;
begin
  { PawnIO se registra en la vista de 32 o de 64 bits según cómo se instaló. }
  Result := RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO')
         or RegKeyExists(HKLM32, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  { Detiene las tareas viejas antes de reemplazar el ejecutable. Primero el
    vigía, para que no vuelva a levantar el servicio viejo a mitad de la
    actualización. }
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "SaludPC Vigia"', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "SaludPC Servicio"', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "SaludPC Panel"', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;
