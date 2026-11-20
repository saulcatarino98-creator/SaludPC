$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "1/3 Generando icono..."
python empaquetado\crear_icono.py

Write-Host "2/3 Empaquetando versión lite (sin .NET, sin sensores de temperatura)..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name SaludPC-Lite `
    --icon empaquetado\icono.ico `
    --collect-all customtkinter `
    app.py

if (-not (Test-Path "dist\SaludPC-Lite\SaludPC-Lite.exe")) {
    throw "PyInstaller no generó dist\SaludPC-Lite\SaludPC-Lite.exe"
}

Write-Host "3/3 Copiando DLL de sensores (opcional, no se requieren en modo lite)..."
# No se copian las DLL de LibreHardwareMonitor ni DiskInfoToolkit.
# El modo lite no usa pythonnet ni .NET Framework.

Write-Host "4/4 Compilando instalador lite..."
$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
}
if (-not (Test-Path $iscc)) {
    throw "No se encontró Inno Setup (ISCC.exe)."
}
& $iscc /Q "empaquetado\instalador_lite.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup devolvió un error."
}

Write-Host "Listo: dist_instalador\SaludPC-Setup-0.5.3-Lite.exe"
