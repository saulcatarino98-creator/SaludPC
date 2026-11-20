$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "1/4 Generando icono..."
python empaquetado\crear_icono.py

Write-Host "2/4 Empaquetando con PyInstaller..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name SaludPC `
    --icon empaquetado\icono.ico `
    --hidden-import clr `
    --collect-all pythonnet `
    --collect-all customtkinter `
    app.py

if (-not (Test-Path "dist\SaludPC\SaludPC.exe")) {
    throw "PyInstaller no generó dist\SaludPC\SaludPC.exe"
}

Write-Host "3/4 Copiando DLL de sensores..."
Copy-Item "empaquetado\sensores\*.dll" "dist\SaludPC\" -Force
if (Test-Path "dist\SaludPC\SaludPC.sys") {
    Remove-Item "dist\SaludPC\SaludPC.sys" -Force
}

Write-Host "4/4 Compilando instalador..."
$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
}
if (-not (Test-Path $iscc)) {
    throw "No se encontró Inno Setup (ISCC.exe)."
}

& $iscc empaquetado\instalador.iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup devolvió un error."
}

Write-Host "Listo: dist_instalador\SaludPC-Setup-0.5.3.exe"


