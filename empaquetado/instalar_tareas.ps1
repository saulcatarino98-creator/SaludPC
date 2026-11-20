param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$Usuario
)

$ErrorActionPreference = "Stop"

# Si el instalador no indica el usuario, se usa el que tiene la sesión abierta.
# Así funciona aunque la instalación se haga con otra cuenta de administrador.
if (-not $Usuario) {
    $explorador = Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" |
        Select-Object -First 1
    if ($explorador) {
        $dueno = Invoke-CimMethod -InputObject $explorador -MethodName GetOwner
        if ($dueno.User) {
            $Usuario = if ($dueno.Domain) {
                "$($dueno.Domain)\$($dueno.User)"
            } else {
                $dueno.User
            }
        }
    }
    if (-not $Usuario) {
        $Usuario = "$env:USERDOMAIN\$env:USERNAME"
    }
}

# Servicio de recolección: arranca al iniciar sesión con permisos de
# administrador (necesarios para leer la temperatura del procesador).
$accion = New-ScheduledTaskAction -Execute $Exe -Argument "--servicio"
$disparador = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $Usuario -RunLevel Highest -LogonType Interactive
$ajustes = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Register-ScheduledTask `
    -TaskName "SaludPC Servicio" `
    -Action $accion `
    -Trigger $disparador `
    -Principal $principal `
    -Settings $ajustes `
    -Force | Out-Null

# Panel: se abre solo 20 segundos después de iniciar sesión.
# Usa --panel-auto para respetar la preferencia del usuario de no mostrarla.
$accionPanel = New-ScheduledTaskAction -Execute $Exe -Argument "--panel-auto"
$disparadorPanel = New-ScheduledTaskTrigger -AtLogOn
$disparadorPanel.Delay = "PT20S"
$principalPanel = New-ScheduledTaskPrincipal -UserId $Usuario -RunLevel Limited -LogonType Interactive
$ajustesPanel = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Register-ScheduledTask `
    -TaskName "SaludPC Panel" `
    -Action $accionPanel `
    -Trigger $disparadorPanel `
    -Principal $principalPanel `
    -Settings $ajustesPanel `
    -Force | Out-Null

# Vigía: cada 5 minutos revisa que el servicio siga guardando datos y lo
# reinicia si se quedó colgado. Corre con privilegios para poder manejarlo.
$accionVigia = New-ScheduledTaskAction -Execute $Exe -Argument "--vigia"
$disparadorVigia = New-ScheduledTaskTrigger -AtLogOn
$repetir = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$disparadorVigia.Repetition = $repetir.Repetition
$principalVigia = New-ScheduledTaskPrincipal -UserId $Usuario -RunLevel Highest -LogonType Interactive
$ajustesVigia = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName "SaludPC Vigia" `
    -Action $accionVigia `
    -Trigger $disparadorVigia `
    -Principal $principalVigia `
    -Settings $ajustesVigia `
    -Force | Out-Null

Write-Output "Tareas programadas creadas para $Usuario"
