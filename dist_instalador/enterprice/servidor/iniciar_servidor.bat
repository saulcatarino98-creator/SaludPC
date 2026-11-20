@echo off
title SaludPC Servidor Central
echo ============================================
echo  SaludPC Servidor Central v1.0.3
echo  Iniciando servicio...
echo ============================================
echo.

cd /d "%~dp0"

echo Verificando dependencias...
if exist "saludPC-Servidor.exe" (
    echo [OK] Ejecutable encontrado
) else (
    echo [ERROR] No se encontró SaludPC-Servidor.exe
    pause
    exit /b 1
)

echo.
echo Iniciando servidor en puerto 8443...
echo (Presiona Ctrl+C para detener)
echo ============================================
echo.

SaludPC-Servidor.exe

echo.
echo El servidor se ha detenido.
pause
