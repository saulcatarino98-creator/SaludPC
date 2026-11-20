# Construir el instalador

Desde la carpeta del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File empaquetado\construir.ps1
```

El resultado queda en `dist_instalador\SaludPC-Setup-0.5.3.exe`.

## Qué hace el instalador

1. Copia el programa a `C:\Program Files\SaludPC`.
2. Instala **PawnIO** en silencio (solo si no estaba). Es el controlador firmado
   que lee la temperatura del procesador y de la placa. Sin él, el programa
   sigue funcionando pero solo con la temperatura de la placa de video.
3. Crea `C:\ProgramData\SaludPC` con permisos para todos los usuarios
   (ahí viven la base `salud.db`, el baseline, los logs y los reportes).
4. Registra tres tareas de Windows:
   - **SaludPC Servicio**: al iniciar sesión, con permisos de administrador.
     Recolecta cada minuto, registra suspensiones y avisos, recalcula el
     análisis cada 6 horas y actualiza el reporte semanal una vez al día.
   - **SaludPC Panel**: al iniciar sesión, 20 segundos después, abre el
     semáforo.
   - **SaludPC Vigia**: al iniciar sesión y cada 5 minutos. Si el servicio dejó
     de guardar datos, lo reinicia.
5. Crea accesos directos en el menú Inicio (panel y reporte de la semana) y en
   el escritorio (panel), para todos los usuarios.

## Datos y registros

| Archivo | Contenido |
|---|---|
| `C:\ProgramData\SaludPC\salud.db` | Mediciones y eventos (SQLite). |
| `C:\ProgramData\SaludPC\baseline_<EQUIPO>.json` | Lo que se considera normal en este equipo. |
| `C:\ProgramData\SaludPC\reportes\*.html` | Últimos 8 reportes semanales. |
| `C:\ProgramData\SaludPC\salud-servicio.log` | Actividad del servicio. |
| `C:\ProgramData\SaludPC\salud-panel.log` | Errores del panel. |
| `C:\ProgramData\SaludPC\salud-vigia.log` | Reinicios hechos por el vigía. |
| `C:\ProgramData\SaludPC\salud-reporte.log` | Errores al generar el reporte. |

El detalle se conserva 90 días; después queda un resumen diario permanente. El
historial de eventos se conserva 400 días.

El desinstalador borra el programa y las tareas, pero **no** borra
`C:\ProgramData\SaludPC` (así no se pierde el aprendizaje si se reinstala) ni
desinstala PawnIO (puede estar en uso por otros programas). Para empezar de
cero, cerrar sesión, borrar esa carpeta y volver a entrar.

## Cómo probar el ejecutable sin instalar

```powershell
$env:SALUD_PC_DATOS = "$env:TEMP\prueba_salud"
.\dist\SaludPC\SaludPC.exe --una-vez
.\dist\SaludPC\SaludPC.exe --cerebro
.\dist\SaludPC\SaludPC.exe --panel
.\dist\SaludPC\SaludPC.exe --reporte
```

`SALUD_PC_DATOS` redirige la base, el baseline, los logs y los reportes a otra
carpeta. Si ya hay un servicio real funcionando, usar además un mutex distinto
para probar el servicio en paralelo:

```powershell
$env:SALUD_PC_MUTEX = "Local\SaludPC_Prueba"
```

## Requisitos para compilar

- Python con las dependencias de `requirements.txt`, `pyinstaller` y `pillow`.
- Inno Setup 7 (ISCC.exe). El script lo busca en
  `%LOCALAPPDATA%\Programs\Inno\ISCC.exe`.
