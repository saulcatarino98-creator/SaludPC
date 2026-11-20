@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
    echo No se encontro Python en esta PC.
    echo Abrir el panel desde el menu Inicio para ver el estado.
    echo.
    pause
    exit /b 1
)
python "%~dp0ver_estado.py"
echo.
pause
