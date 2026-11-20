# Salud de mi equipo

Asistente de diagnóstico y prevención. Observa el hardware, aprende qué es
normal para *este* equipo y avisa en lenguaje simple cuando algo se sale de
lo habitual. No intenta reparar nada: ayuda a detectar a tiempo.

## Instalación

```powershell
python -m pip install -r requirements.txt
```

Las DLL de LibreHardwareMonitor viven en `empaquetado\sensores`. En desarrollo
el programa las busca ahí; al empaquetar se copian junto al ejecutable.

## Versión instalable (recomendada)

El instalador `dist_instalador\SaludPC-Setup-0.5.3.exe` deja todo funcionando:
programa en `C:\Program Files\SaludPC`, datos en `C:\ProgramData\SaludPC` y tres
tareas de Windows que arrancan solas al iniciar sesión (recolección, panel y
vigía). No hace falta abrir ventanas ni ejecutar nada a mano. Detalles en
`empaquetado\README.md`.

Para leer la temperatura del procesador el instalador agrega **PawnIO**, un
controlador firmado que Windows Defender no bloquea. Es un componente compartido:
si ya lo tenés instalado, el instalador no lo toca, y al desinstalar SaludPC se
deja instalado por si lo usa otro programa.

## Qué muestra el panel

- **Ahora**: estado general (Normal, Atención o Revisar) y una tarjeta por
  métrica con el valor actual, una barra de referencia y el límite considerado
  normal para este equipo. Las tarjetas actualizan las lecturas en vivo cada
  5 segundos; esta consulta no guarda muestras ni modifica el aprendizaje. El
  estado preventivo sigue evaluándose con las mediciones históricas. En la
  cabecera se muestra el consumo del agente (servicio + panel) como promedio de
  los últimos 5 minutos.
- **Historial**: lista en castellano de lo que pasó en los últimos 30 días
  (suspensiones, apagados, reinicios, avisos y picos). Se puede filtrar por
  Todos, Energía, Carga o Térmicas. Un pico se guarda como episodio solo si
  duró 5 minutos o más, con inicio, fin y duración.
- **Ver reporte de la semana**: abre en el navegador un resumen de los últimos
  7 días, listo para imprimir o guardar como PDF. También hay un acceso directo
  "Reporte de la semana" en el menú Inicio.

Cuando el equipo pasa a Atención o Revisar, el **servicio** muestra un aviso
flotante abajo a la derecha durante unos segundos, aunque el panel esté
cerrado. Se muestra una sola vez por empeoramiento, no cada minuto, y al hacer
clic abre el panel. Para comprobarlo sin esperar a un problema real:

```powershell
SaludPC.exe --aviso accion --mensaje "Prueba de aviso"
```

Mientras el equipo está en aprendizaje, el panel indica el día y la cantidad de
muestras que faltan para empezar a evaluar.

La ventana sigue el modo claro u oscuro configurado en Windows y se abre sola al
iniciar sesión.

## Cómo funciona por dentro

1. **Recolectar**: el servicio toma una lectura por minuto y la guarda en
   SQLite. Se conservan 90 días de detalle; los días más viejos se resumen en
   promedios diarios permanentes.
2. **Analizar**: al arrancar, al cambiar el día y cada 6 horas se recalcula el
   baseline con los datos de *este* equipo. Durante los primeros 3 días el
   estado es "Aprendiendo" y no alarma.
3. **Avisar**: el servicio compara la última lectura con el baseline y muestra
   el aviso cuando el estado empeora, sin depender de que el panel esté
   abierto. Si una métrica se mantiene fuera de lo normal 5 minutos o más, el
   pico queda guardado como episodio.
4. **Explicar**: las pausas largas entre mediciones se clasifican como
   suspensión (si Windows no se reinició) o apagado/reinicio (si cambió la hora
   de arranque).

## Uso en desarrollo

```powershell
python app.py --panel       # ventana
python app.py --servicio    # recolección en segundo plano
python app.py --cerebro     # recalcular el baseline una vez
python app.py --una-vez     # una sola lectura
python app.py --reporte     # generar y abrir el reporte semanal
python app.py --aviso accion --mensaje "Prueba"  # aviso flotante de prueba
python app.py --vigia       # reiniciar el servicio si dejó de guardar datos
```

Para probar sin tocar los datos reales, `SALUD_PC_DATOS` redirige la base, el
baseline, los logs y los reportes a otra carpeta:

```powershell
$env:SALUD_PC_DATOS = "$env:TEMP\prueba_salud"
python app.py --una-vez
```

## Privacidad

Todos los datos se guardan localmente en `salud.db`. No se envía nada a
Internet.

## Dependencias de terceros

- LibreHardwareMonitor 0.9.6: licencia MPL 2.0. Si se redistribuye este
  programa, hay que incluir el aviso de licencia y el código fuente de esa
  librería.
- PawnIO: controlador firmado de namazso, necesario para leer la temperatura
  del procesador y de la placa. Se instala aparte y queda disponible para otros
  programas.
- CustomTkinter: interfaz gráfica (licencia MIT).
