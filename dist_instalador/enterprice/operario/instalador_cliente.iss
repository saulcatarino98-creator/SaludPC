#define MiApp "SaludPC Cliente Enterprise"
#define MiVersion "1.0.2"
#define MiExe "SaludPC-Cliente-Operario.exe"

[Setup]
AppId={{D2B3C4E5-F6A7-8901-BCDE-F23456789012}}
AppName={#MiApp}
AppVersion={#MiVersion}
AppPublisher=SaludPC Enterprise
DefaultDirName={pf}\SaludPC Cliente
DefaultGroupName={#MiApp}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\..\instaladores
OutputBaseFilename=SaludPC-Cliente-Operario-{#MiVersion}
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
Name: "{commonappdata}\SaludPC\Cliente"; Permissions: users-modify

[Files]
Source: "dist\SaludPC-Cliente-Operario\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "inicioautomatico"; Description: "Iniciar SaludPC automáticamente al iniciar sesión (la ventana puede quedar oculta)"; GroupDescription: "Opciones:"; Flags: checkedonce

[Icons]
Name: "{group}\{#MiApp}"; Filename: "{app}\{#MiExe}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MiApp}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MiApp}"; Filename: "{app}\{#MiExe}"; WorkingDir: "{app}"
Name: "{commonstartup}\{#MiApp}"; Filename: "{app}\{#MiExe}"; Parameters: "--auto"; WorkingDir: "{app}"; Tasks: inicioautomatico

[Run]
Filename: "{app}\{#MiExe}"; Description: "Ejecutar SaludPC Cliente Enterprise"; Flags: nowait postinstall skipifsilent

[Code]
procedure MatarClienteAnterior();
var
  CodigoResultado: Integer;
begin
  Exec(
    'taskkill.exe',
    '/F /IM SaludPC-Cliente-Operario.exe /T',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    CodigoResultado
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    MatarClienteAnterior();
end;
