$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Empaquetando Servidor Central de SaludPC Enterprise..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --console `
    --onedir `
    --name SaludPC-Servidor `
    --icon ..\..\..\empaquetado\icono.ico `
    servidor_central.py

if (-not (Test-Path "dist\SaludPC-Servidor\SaludPC-Servidor.exe")) {
    throw "PyInstaller no genero SaludPC-Servidor.exe"
}

Write-Host "Listo: dist\SaludPC-Servidor\SaludPC-Servidor.exe"
