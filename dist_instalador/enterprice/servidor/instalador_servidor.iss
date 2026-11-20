#define MiApp "SaludPC Servidor Central"
#define MiVersion "1.0.3"
#define MiExe "SaludPC-Servidor.exe"

[Setup]
AppId={{C1A2B3D4-E5F6-7890-ABCD-EF1234567891}}
AppName={#MiApp}
AppVersion={#MiVersion}
AppPublisher=SaludPC Enterprise
DefaultDirName={pf}\SaludPC Servidor
DefaultGroupName={#MiApp}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\..\instaladores
OutputBaseFilename=SaludPC-Servidor-Central-{#MiVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\..\..\empaquetado\icono.ico
UninstallDisplayIcon={app}\{#MiExe}
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{commonappdata}\SaludPC\Servidor"; Permissions: users-modify

[Files]
Source: "dist\SaludPC-Servidor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "iniciar_servidor.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MiApp}"; Filename: "{app}\{#MiExe}"
Name: "{group}\Desinstalar {#MiApp}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MiApp}"; Filename: "{app}\{#MiExe}"

[Run]
Filename: "{app}\iniciar_servidor.bat"; Description: "Iniciar SaludPC Servidor Central"; Flags: runascurrentuser nowait skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure MatarServidorAnterior();
var
  CodigoResultado: Integer;
begin
  Exec(
    'taskkill.exe',
    '/F /IM SaludPC-Servidor.exe /T',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    CodigoResultado
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    MatarServidorAnterior();
end;
