$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Empaquetando Cliente Operario Enterprise (GUI)..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name SaludPC-Cliente-Operario `
    --icon ..\..\..\empaquetado\icono.ico `
    cliente_gui.py

if (-not (Test-Path "dist\SaludPC-Cliente-Operario\SaludPC-Cliente-Operario.exe")) {
    throw "PyInstaller no generó SaludPC-Cliente-Operario.exe"
}

Write-Host "Listo: dist\SaludPC-Cliente-Operario\SaludPC-Cliente-Operario.exe"
