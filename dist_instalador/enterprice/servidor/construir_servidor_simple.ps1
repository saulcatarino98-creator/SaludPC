$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Empaquetando Servidor Central de SaludPC (versión simplificada)..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name SaludPC-Servidor `
    --icon ..\..\..\empaquetado\icono.ico `
    servidor_central_simple.py

if (-not (Test-Path "dist\SaludPC-Servidor\SaludPC-Servidor.exe")) {
    throw "PyInstaller no generó SaludPC-Servidor.exe"
}

Write-Host "Listo: dist\SaludPC-Servidor\SaludPC-Servidor.exe"
