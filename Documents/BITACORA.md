# Bitácora de SaludPC

**Última actualización:** 9 de noviembre de 2026
**Estado:** versión 0.5.3 instalada; versión lite compilada; edición empresarial 1.0.3 (servidor con búsqueda, filtros e informes) y cliente operario 1.0.2, probados en banco y pendientes de instalar en el equipo real
**Ámbito:** edición para usuario final y edición empresarial (piloto)

---

## 1. Para qué sirve este documento

Esta bitácora cuenta, en orden, qué se construyó, qué se probó y qué se aprendió
en cada etapa de SaludPC. No es un manual de uso ni una lista de tareas: es el
registro de por qué el programa llegó a ser como es, qué funcionaba en cada
versión, qué no funcionaba y qué queda por delante.

La carpeta del proyecto **no es un repositorio Git**, así que no existe un
historial de commits. Esta reconstrucción se basa en los archivos que quedaron
en el disco, sus fechas, los documentos técnicos y las pruebas que se ejecutaron.
Cuando algo no se pudo comprobar, se dice explícitamente.

---

## 2. Resumen en una página

SaludPC nació como un conjunto de scripts que leían los sensores de la PC y
guardaban un CSV. Con el tiempo se convirtió en un producto instalable: un
servicio que toma una muestra por minuto, aprende qué es normal en ese equipo,
avisa cuando algo se sale de lo habitual y muestra un panel e historial en
lenguaje simple.

Las versiones fueron estas:

| Etapa | Qué era | Lo más importante |
|---|---|---|
| **Alpha inicial** (fines de octubre) | Scripts de Python y CSV | Se comprobó que era posible leer hardware real y compararlo con un baseline |
| **0.4.0** | Primera versión instalable | Instalador, servicio, tareas automáticas, datos en `ProgramData` |
| **0.5.0** | Versión cuidada | Panel nuevo, historial, reporte semanal, tema automático, aviso flotante |
| **0.5.1** | Corrección del aviso | El aviso lo dispara el servicio, no el panel; modo de prueba; texto de aprendizaje |
| **0.5.2** | Contador de días confiable | El baseline se refresca al arrancar, al cambiar el día y cada 6 horas; el aprendizaje termina solo |
| **0.5.3** | Consumo, filtros y picos | El agente muestra su consumo, el historial se filtra por categoría y los picos de 5 minutos o más quedan como episodios |
| **0.5.3 Lite** | Versión de bajos recursos | Sin .NET Framework, sin sensores de temperatura, solo CPU/RAM/disco; ejecutable aparte `SaludPC-Lite.exe` |
| **Enterprise 1.0.0** | Servidor central y cliente operario | Servidor central con panel de TI, cliente con interfaz gráfica para inscripción y envío de reportes; lista cerrada de campos técnicos |
| **Enterprise 1.0.1** | Panel de aprendizaje en el operario | El cliente ya no se cierra al inscribir; muestra el avance real de aprendizaje (muestras y días) y confirma que el sistema está funcionando |
| **Enterprise 1.0.2** | APRENDIENDO, inicio oculto e instancia única | El panel del cliente muestra APRENDIENDO hasta completar la línea base; se puede ocultar la ventana al iniciar sesión sin detener el envío; una segunda apertura reabre la instancia existente |
| **Enterprise 1.0.3** | Búsqueda, filtros e informes en el panel de TI | Buscador por ID u organización/sede/área, filtro por estado, botón Actualizar a la derecha y generación de informes generales y por equipo en HTML o CSV; incluye manual de uso |

El gran tropiezo de la 0.5.0 fue el **aviso flotante que no aparecía**. No era un
fallo de instalación: el equipo todavía estaba en aprendizaje (1 de 3 días,
194 de 300 muestras) y, además, el aviso solo se mostraba si el panel estaba
abierto y veía el empeoramiento en ese momento. La 0.5.1 corrigió lo segundo.
Lo primero se resuelve solo con días de uso normal.

Hoy la edición local está funcional e instalada (0.5.3). El aprendizaje terminó
solo el 5 de noviembre: el baseline llegó a 3 días y 1.127 muestras, y el panel
muestra «Todo se ve dentro de lo normal para tu equipo». La cabecera informa el
consumo del agente y el historial se puede filtrar por energía, carga y
térmicas. Existe una versión lite (sin .NET, sin sensores de temperatura) para
equipos de bajos recursos. La edición empresarial está implementada y probada:
servidor central con panel de TI y cliente operario con interfaz gráfica para
inscripción y envío de reportes firmados con HMAC-SHA256.

---

## 3. Línea de tiempo

| Fecha aproximada | Hecho |
|---|---|
| 26 de octubre de 2026 | Primeros scripts: colector, cerebro, vigilante, CSV de hardware |
| 29 de octubre de 2026 | Respaldo de la alpha; separación de métricas y baseline |
| 30 de octubre de 2026 | Primer empaquetado con PyInstaller (`app.spec`, carpeta `build`) |
| 3 de noviembre de 2026 | Trabajo grande: 0.4.0, 0.5.0, 0.5.1, documentación y diseño empresarial |
| 4 de noviembre de 2026 | 0.5.2: arreglo del contador de días; instalación sobre la 0.5.0 y primeras 2 fechas locales |
| 5 de noviembre de 2026 | El aprendizaje termina solo a las 00:00:44; primer estado «Normal» con datos reales |
| 5 de noviembre de 2026 | 0.5.3: consumo del agente, filtros del historial y episodios de pico; instalación validada |
| 7 de noviembre de 2026 | Versión lite compilada (sin .NET, sin sensores); casilla «No mostrar ventana al iniciar sesión» agregada al panel |
| 8 de noviembre de 2026 | Edición empresarial implementada y probada: servidor central con panel de TI y cliente operario con interfaz gráfica |
| 9 de noviembre de 2026 | Enterprise 1.0.1: el cliente conserva la ventana al inscribir y muestra un panel de aprendizaje con el avance real del servidor |
| 9 de noviembre de 2026 | Enterprise 1.0.2: APRENDIENDO, inicio oculto e instancia única; Enterprise 1.0.3: búsqueda, filtros, informes generales y por equipo; manual de uso |

Las fechas son las que dejaron los archivos. Algunas decisiones pudieron
tomarse antes o después de la fecha visible; lo que importa es el orden.

---

## 4. Etapa alpha: la prueba de concepto

### 4.1 Qué se construyó

Los archivos de esa época siguen en `respaldo_alpha_20261029`:

- `colector.py`: abría LibreHardwareMonitor y leía sensores de CPU, memoria,
  disco y temperatura.
- `cerebro.py`: calculaba un baseline, es decir, un retrato de lo que era
  normal para ese equipo.
- `vigilante.py`: comparaba las lecturas con el baseline y decidía si había
  algo raro.
- `historial_hardware.csv`: guardaba las lecturas en un archivo de texto.
- `ver_estado.py` y `ver_estado.bat`: mostraban por consola si el programa
  estaba funcionando y cuándo fue la última muestra.

En esa etapa también apareció `metricas.py`, que con el tiempo se convirtió en
el único lugar donde se definen las métricas válidas. Esa decisión evitó que
cada módulo inventara su propia lista de sensores.

### 4.2 Qué funcionaba

- Leer hardware real, incluida la temperatura, mediante LibreHardwareMonitor.
- Guardar un histórico en CSV.
- Calcular un baseline y comparar contra él.
- Ejecutar todo a mano, desde consola, sin instalar nada.

### 4.3 Qué no funcionaba

- **No había producto**: había que abrir una consola y ejecutar scripts.
- **No había instalación**: dependía de tener Python y las librerías instaladas.
- **No había arranque automático**: si el usuario no ejecutaba nada, no había
  datos.
- **No había panel**: todo se leía por consola o abriendo el CSV.
- **No había historial interpretado**: el CSV no explicaba suspensiones,
  apagados ni cambios de estado.
- **No había aprendizaje sólido**: el baseline era un archivo vacío
  (`"version": 1`, `"metricas": {}`) y no resistía reinicios ni cambios de
  versión. El código actual rechaza ese formato y genera uno nuevo
  (`"version": 2`), lo que obliga a volver a aprender.
- **No había alertas útiles**: sin baseline consolidado, cualquier comparación
  podía dar falsos positivos.

La alpha cumplió su función: demostró que la idea era viable. Pero no era algo
que se pudiera entregar a una persona sin conocimientos técnicos.

---

## 5. Versión 0.4.0: la primera instalable

### 5.1 Qué se hizo

Se empaquetó con PyInstaller en modo `onedir` y ventana sin consola, y se armó
un instalador con Inno Setup. El objetivo era que la instalación fuera
«siguiente, siguiente, siguiente», con un solo pedido de permisos de
administrador.

La instalación dejó este esquema:

- Programa en `C:\Program Files\SaludPC`.
- Datos en `C:\ProgramData\SaludPC`, con permisos para que el usuario pueda
  escribir sin ser administrador.
- Tres tareas de Windows:
  - **SaludPC Servicio**: arranca al iniciar sesión, con permisos elevados.
  - **SaludPC Panel**: arranca al iniciar sesión, unos 20 segundos después.
  - **SaludPC Vigia**: arranca al iniciar sesión y se repite cada 5 minutos;
    reinicia el servicio si dejó de guardar datos.

El panel era la interfaz clásica de Tkinter. El aviso al usuario era una
notificación básica.

### 5.2 Qué funcionaba

- Instalar sin conocimientos técnicos y con un solo UAC.
- Arrancar solo al iniciar sesión, sin botón «iniciar».
- Tomar una muestra por minuto y guardarla en SQLite.
- Conservar 90 días de detalle y resumir los días viejos.
- Mantener los datos en el equipo, sin enviar nada a Internet.
- Abrir el panel automáticamente.

### 5.3 Qué no funcionaba

- **La interfaz se veía anticuada** y no acompañaba el tema claro u oscuro de
  Windows.
- **No había pestaña de historial**: el usuario veía el estado actual, pero no
  qué había pasado.
- **No se distinguían suspensiones y apagados**: un hueco de horas parecía un
  fallo del programa.
- **No había reporte semanal**: no había forma de mirar tendencias sin abrir
  la base.
- **El aviso era básico y poco confiable**: una notificación de Windows puede
  quedar silenciada o agrupada.
- **El panel podía cerrarse solo a los 3 días**: las tareas de Windows tienen
  un límite de ejecución predeterminado.
- **No se podían hacer pruebas en paralelo**: el mutex del servicio era fijo y
  bloqueaba una segunda instancia.
- **La temperatura dependía de un controlador**: sin el componente firmado,
  algunos sensores no estaban disponibles.

La 0.4.0 demostró que el producto se podía instalar y dejar funcionando solo.
El problema ya no era la viabilidad, sino la experiencia de uso.

---

## 6. Versión 0.5.0: el salto de calidad

### 6.1 Qué se hizo

Se migró la interfaz a CustomTkinter 6.0.0 y Pillow 13.0.0. El panel pasó a
tener dos pestañas y un diseño de tarjetas:

- **Ahora**: estado general (Normal, Atención o Revisar) y una tarjeta por
  métrica, con valor actual, barra de referencia y límite normal del equipo.
- **Historial**: últimos 30 días en lenguaje simple, agrupados por día.

Además se agregó:

- **Detección de suspensión y apagado.** Si hay un hueco de más de 3 minutos
  entre muestras, se compara la última marca con la hora de arranque de
  Windows. Si la marca es anterior al arranque, hubo apagado o reinicio; si no,
  fue suspensión.
- **Reporte semanal HTML** autocontenido, de 7 días, con interpretación simple,
  que se abre en el navegador y se puede imprimir o guardar como PDF. Se genera
  bajo demanda (`--reporte`), cada 24 horas por el servicio, y se conservan 8.
- **Tabla de eventos** con índice y retención de 400 días, para que el historial
  sobreviva aunque las muestras detalladas se resuman.
- **Aviso flotante propio**: ventana sin bordes, abajo a la derecha,
  400 × 148 px, siempre encima, 9 segundos, clic para abrir el panel.
- **Tema automático** según la preferencia de Windows.
- **Límite de ejecución del panel de 3650 días**, para que no se cierre solo.
- **Mutex configurable** con `SALUD_PC_MUTEX`, para poder probar sin chocar con
  la instalación real.

También se incorporó el controlador firmado **PawnIO 2.2.0** para leer
temperaturas sin que Windows Defender lo bloquee, junto con
**LibreHardwareMonitor 0.9.6**. PawnIO es un componente compartido: si ya está
instalado, el instalador no lo toca, y al desinstalar SaludPC se deja instalado.

### 6.2 Qué funcionaba

- Panel legible en 1366 × 768, con estética cuidada y tema automático.
- Historial comprensible: «Estuvo 2 horas en reposo», «Estuvo apagado 1 día».
- Reporte semanal útil para imprimir o guardar.
- Detección correcta de pausas largas.
- Panel que ya no se cierra solo por el límite de las tareas.
- Instalación y arranque automático estables.

### 6.3 Qué no funcionaba

- **El aviso flotante casi nunca aparecía.** Este fue el problema central de la
  versión.
- **No había forma de probar el aviso** sin esperar un problema real.
- **El aviso no se mostraba al abrir el panel** si el equipo ya estaba en
  Amarillo o Rojo: el primer estado observado se tomaba como referencia.
- **No había botón para silenciar avisos.**
- **El historial no se podía filtrar ni exportar**, y mostraba 30 días aunque la
  base guardara 400.
- **El reporte no se enviaba por correo** ni se podía programar desde el panel.
- **El instalador no estaba firmado**: SmartScreen podía advertir.
- **No había actualización automática.**

---

## 7. El caso del aviso que no aparecía

Este es el episodio más importante de la historia reciente, porque mezcló un
comportamiento esperado con un defecto real.

Después de instalar la 0.5.0, el usuario observó que el programa arrancaba solo,
pero no mostraba el aviso flotante. El diagnóstico encontró dos causas
independientes.

### 7.1 Causa uno: el equipo estaba aprendiendo

El baseline real decía:

```json
{
  "aprendiendo": true,
  "dias": 1,
  "muestras": 194,
  "metricas": {}
}
```

El programa necesita **3 días y al menos 300 muestras** para saber qué es normal
en ese equipo. Mientras `aprendiendo` sea `true`, el estado es «Aprendiendo» y,
por diseño, no se generan alertas. Es correcto: avisar antes de conocer el
equipo produciría falsos positivos.

Con una muestra por minuto, 194 muestras son unas tres horas y media de equipo
encendido. Faltaban días de uso normal.

### 7.2 Causa dos: el aviso dependía del panel

En la 0.5.0 la lógica era esta:

1. Al abrir, el panel guardaba el estado actual como referencia.
2. En cada actualización comparaba el estado nuevo con el anterior.
3. Solo avisaba si el estado **empeoraba** con el panel abierto.
4. Nunca avisaba al abrir si el equipo ya estaba en Amarillo o Rojo.
5. Si el panel estaba cerrado, el servicio registraba el cambio en el historial,
   pero no mostraba nada.

Por eso, aunque el equipo hubiera pasado a Amarillo, al abrir el panel el aviso
no aparecía: el primer estado se tomaba como referencia.

### 7.3 Qué sí estaba funcionando

- El servicio tomaba muestras y registraba pausas (se vieron suspensiones de 16
  y 11 minutos).
- El baseline se generaba y se actualizaba.
- El panel abría solo al iniciar sesión.
- El historial y el reporte semanal estaban disponibles.

La conclusión fue que el comportamiento observado era el esperado para un
equipo en aprendizaje, pero el diseño del aviso era frágil. Se corrigió en la
0.5.1.

---

## 8. Versión 0.5.1: el aviso independiente del panel

### 8.1 Qué se cambió

- **El servicio dispara el aviso.** Cuando detecta que el estado empeora, lanza
  un proceso `--aviso` aunque el panel esté cerrado.
- **Se recuerda el último estado avisado** en
  `C:\ProgramData\SaludPC\ultimo_estado_aviso.json`. Si el equipo arranca ya en
  Atención o Revisar, avisa una vez; al mejorar, actualiza la referencia sin
  mostrar nada; si vuelve a empeorar, avisa de nuevo.
- **El panel ya no avisa por su cuenta**, para evitar duplicados.
- **Modo de prueba**: `SaludPC.exe --aviso accion --mensaje "Prueba"` muestra el
  aviso y termina, sin alterar datos ni estado.
- **Texto de aprendizaje mejorado**: «Estamos conociendo tu equipo (1 de 3 días,
  194 de 300 muestras)…», para que se entienda por qué todavía no hay alertas.

### 8.2 Qué se probó

| Prueba | Resultado |
|---|---|
| `python app.py --aviso` | Mostró el aviso durante 9,6 segundos |
| Ejecutable empaquetado `--aviso` | Mostró el aviso durante 10,2 segundos, código de salida 0 |
| Servicio simulado con estado de Atención | Detectó el cambio, registró «Aviso flotante mostrado» y creó `ultimo_estado_aviso.json` |
| Segunda ejecución con el mismo estado | No repitió el aviso |
| Servicio empaquetado | También mostró el aviso |

Estas pruebas confirman que el aviso ya no depende de que el panel esté abierto.

### 8.3 Qué sigue sin estar contemplado

- No hay botón para silenciar los avisos.
- Si el servicio no está corriendo, no hay aviso; el panel tampoco lo muestra.
- No hay historial de avisos mostrados, solo el último estado.
- El instalador no está firmado.
- No hay actualización automática.
- El aviso no se puede personalizar desde el panel.

### 8.4 Estado de la instalación

El instalador `dist_instalador\SaludPC-Setup-0.5.1.exe` está compilado:

- Tamaño: 39.217.851 bytes.
- SHA-256: `61B398CDAB5CBDB3D799610A650C3AE5839507F411E2AB8E0EB80A4959E72492`.
- Windows Defender no reportó amenazas.

**La 0.5.1 no llegó a instalarse.** Se compiló y se probó, pero antes de
instalarla se preparó la 0.5.2 con el arreglo del contador de días. El 4 de
noviembre se instaló directamente la 0.5.2 sobre la 0.5.0.

---

## 9. Versión 0.5.2: el baseline se refresca solo

### 9.1 El síntoma

El 4 de noviembre, a media mañana, el panel mostraba «1 de 3 días» aunque la
base ya tenía dos fechas locales (3 y 4 de noviembre) y 555 muestras distintas.
No era un error de cálculo: el baseline se había guardado a las 11:15:25, antes
de la primera muestra del día 4 (11:16:34), y el siguiente recálculo estaba
previsto recién seis horas después, a las 17:15.

El archivo del baseline seguía diciendo:

```json
{
  "aprendiendo": true,
  "dias": 1,
  "muestras": 555,
  "metricas": {}
}
```

Mientras tanto, la base tenía dos fechas. El contador podía quedar hasta seis
horas atrasado y el usuario no tenía forma de saber si el programa estaba
avanzando o se había trabado.

### 9.2 Qué se cambió

- **`almacen.contar_dias_muestras()`**: consulta agregada con
  `date(ts, 'localtime')` y `COUNT(DISTINCT ts)`. Cuenta fechas locales
  distintas y fotos distintas del equipo sin cargar el historial en memoria.
- **`cerebro.main()`**: mientras aprende usa esos conteos; cuando completa, carga
  el historial con pandas y calcula las métricas.
- **`app.py`**: recalcula el baseline en tres momentos: al arrancar (después de
  la primera muestra), al cambiar el día local y cada 6 horas. Si el recálculo
  falla, reintenta a los 10 minutos en vez de esperar 6 horas.
- El conteo usa la fecha local, no UTC. `date(ts, 'localtime')` de SQLite
  coincide exactamente con `tz_convert(local)` de pandas.

La regla no cambió: siguen siendo **3 fechas locales distintas y 300 muestras
distintas**. Lo que cambió es cuándo se refresca el conteo.

### 9.3 Qué se probó

| Prueba | Resultado |
|---|---|
| 2 fechas sintéticas, 360 muestras | `dias: 2`, `aprendiendo: true`, sin métricas |
| 3 fechas sintéticas, 540 muestras | `dias: 3`, `aprendiendo: false`, métricas de CPU, disco y memoria |
| Conteo SQL contra pandas | Coinciden: 2 fechas y 561 muestras; luego 3 fechas y 540 |
| Ejecutable compilado con base de 3 días | `aprendiendo: false`, `dias: 3`, `muestras: 540`, salida 0 |
| Servicio real | Recalculó al arrancar (21:12), por cambio de día (00:00:44) y cada 6 horas |

No se falsearon fechas ni datos: las pruebas sintéticas usaron una carpeta
temporal y la validación final se hizo con la base real.

### 9.4 Instalación y primera validación real

- Instalador: `dist_instalador\SaludPC-Setup-0.5.2.exe`, 39.388.839 bytes.
- Instalado el 4 de noviembre a las 11:53, con un solo UAC. Conservó datos y
  baseline.
- El ejecutable instalado coincide con el compilado: 12.542.511 bytes, 4 de
  noviembre, 11:31:38.
- La 0.5.1 no se instaló: se pasó directamente de la 0.5.0 a la 0.5.2.

El 5 de noviembre el log del servicio mostró la secuencia esperada:

```
00:00:37 primera muestra del día 5
00:00:44 Baseline v2 guardado
00:00:44 Días con datos: 3 | Fotos del equipo: 1127 | Aprendiendo: False
00:00:44 cpu_load: aviso=87.74% rojo=98.0%
00:00:44 ...
00:00:44 Baseline recalculado
```

Siete segundos después de la primera muestra del día, el baseline pasó a 3 días
y dejó de estar en aprendizaje. Las 1.127 muestras de ese momento eran las 555
del día 3, las 571 del día 4 y la primera del día 5.

Al momento de esta validación (00:37 del 5 de noviembre), la base tenía 1.163
muestras distintas en 3 fechas. El estado era `ok` y las seis métricas estaban
dentro de su límite: procesador 32 %, temperatura del procesador 54 °C,
temperatura del disco 36 °C, disco 24,7 %, temperatura de la GPU 47 °C y
memoria 36,5 %. El reporte `reporte_2026-11-05.html` se actualizó a las 00:34.
El aviso de prueba con el ejecutable instalado mostró la ventana durante 9
segundos y cerró con código 0, sin alterar el historial.

---

## 10. Versión 0.5.3: consumo, filtros y episodios de pico

### 10.1 Qué se buscaba

La 0.5.3 cierra tres huecos que quedaban en el panel sin agregar más tarjetas:
saber cuánto consume el propio agente, poder mirar el historial por tipo de
evento y guardar los picos como episodios con inicio, fin y duración.

La atribución de procesos y el índice de estrés quedaron fuera a propósito. No
se implementaron, no se simularon y no se presentan como si existieran.

### 10.2 Consumo del agente

El servicio corre siempre y el panel solo cuando se abre. Cada proceso mide lo
suyo:

- El servicio mide su propio proceso una vez por minuto y publica CPU y memoria
  en `C:\ProgramData\SaludPC\consumo_servicio.json`.
- El panel mide su proceso cada 5 segundos, lee el archivo del servicio y suma
  las dos mediciones.
- El archivo se considera fresco durante 180 segundos. Si el servicio no
  publicó nada, la línea agrega «servicio sin datos» en vez de inventar un cero.

El promedio es móvil sobre los últimos 5 minutos y se calcula por tiempo, no por
cantidad de muestras: las lecturas de sensores no siempre tardan lo mismo. La
CPU de `psutil` se divide por la cantidad de núcleos lógicos para que el número
sea comparable con el uso total del equipo.

La línea de la cabecera no usa la palabra «Optimizado». Solo agrega «consumo
bajo» cuando el promedio de CPU es menor a 0.95 %. Si el número no alcanza, no
se afirma nada.

### 10.3 Filtros del historial

El historial tiene un selector con cuatro opciones: **Todos**, **Energía**,
**Carga** y **Térmicas**.

- **Energía**: suspensiones y apagados.
- **Térmicas**: eventos de `cpu_temp`, `gpu_temp` y `disk_temp`.
- **Carga**: procesador, memoria, disco, GPU y cualquier evento genérico.

Un aviso o un pico hereda la categoría de su métrica. La firma que decide si hay
que repintar el historial usa `MAX(id)` de la tabla de eventos, no solo la fecha
más nueva: un pico se guarda con la hora en que empezó y puede quedar debajo de
eventos más recientes.

### 10.4 Episodios de pico

Un episodio empieza cuando una métrica entra en atención o acción con la misma
regla de 3 de 5 muestras para amarillo y 2 de 5 para rojo que usa el vigilante.
Termina cuando la métrica vuelve a estar normal.

Solo se guarda como evento `pico` si duró **5 minutos o más**. El detalle es un
JSON con la métrica, el inicio, el fin, el máximo, la duración, los límites de
aviso y rojo, y el estado final. El evento se guarda con `ts=inicio` para que el
historial muestre el pico donde empezó, no donde terminó.

Los episodios abiertos se persisten en
`C:\ProgramData\SaludPC\episodios_abiertos.json`. Si el servicio estuvo detenido
más de 15 minutos, el episodio se descarta: no se puede afirmar que duró todo
ese tiempo.

### 10.5 Qué se probó

| Prueba | Resultado |
|---|---|
| `tests/test_agente.py` | Medición del proceso, archivo publicado, frescura de 180 s y umbral de consumo bajo |
| `tests/test_episodios.py` | Categorías, pico de 4 minutos descartado, pico de carga de 6 minutos, pico térmico rojo de 8 minutos y episodio abandonado descartado |
| `tests/test_contador_dias.py` | 2 y 3 fechas siguen dando el mismo resultado |
| `tests/test_modelo_simulado.py` | El modelo completo sigue pasando |
| Panel de desarrollo con datos reales | Cabecera con consumo combinado y filtros Todos / Energía / Carga / Térmicas |
| Panel instalado | Abre sin errores y el servicio publica su consumo |

No se falsearon fechas ni datos. Las pruebas de episodios usaron una carpeta
temporal con `SALUD_PC_DATOS`; la validación final se hizo con la base real.

### 10.6 Instalación y validación real

- Instalador: `dist_instalador\SaludPC-Setup-0.5.3.exe`, 39.401.717 bytes.
- SHA-256: `622FAACB3F3D5E52348BA76C903F3FD884F6A8BE9AA7164C4FAF5CDBEF852385`.
- Compilado el 5 de noviembre a las 01:23 e instalado alrededor de las 01:50,
  con un solo UAC.
- Windows registra `DisplayVersion 0.5.3`; el servicio se reinició a las 01:50:30
  y recalculó el baseline con 3 días y 1.227 muestras.
- El servicio publica su consumo cada minuto; en régimen normal ronda 0,1-0,2 %
  de CPU y decenas de MB de RAM.

La instalación se topó con un archivo bloqueado, `DiskInfoToolkit.dll`, porque
el panel seguía abierto. El instalador detiene las tareas, pero en este caso el
proceso del panel sobrevivió; hubo que cerrarlo y pulsar «Reintentar». No hizo
falta un segundo UAC. Queda como mejora para la próxima versión forzar el cierre
de cualquier `SaludPC.exe` antes de copiar los archivos.

Validación con datos reales:

- La base tenía 8 eventos, todos de energía (6 suspensiones y 2 apagados). Por
  eso Todos y Energía muestran contenido; Carga y Térmicas muestran el mensaje
  de que no hay eventos de ese tipo en los últimos 30 días.
- El panel de desarrollo mostró en la cabecera el consumo combinado del servicio
  y del panel, sin «servicio sin datos».
- La medición externa del panel ya estabilizado quedó entre 0,3 % y 0,85 % del
  equipo; los picos de alrededor de 4 % corresponden a la lectura de sensores.
- El panel instalado abrió sin errores.
- Todavía no se registró un pico real. No se forzó la base para fabricarlo; la
  lógica quedó cubierta por las pruebas en carpeta temporal.

---

## 11. Casilla «No mostrar ventana al iniciar sesión»

### 11.1 Qué se buscaba

El panel se abría automáticamente al iniciar sesión mediante la tarea
programada `SaludPC Panel`. Algunos usuarios necesitaban evitar esa ventana
automática y abrir el panel solo cuando lo decidieran.

### 11.2 Qué se cambió

- Se agregó el módulo `config_usuario.py` que guarda preferencias en
  `C:\ProgramData\SaludPC\config_usuario.json`.
- Se agregó la casilla **«No mostrar esta ventana al iniciar sesión»** en el
  pie del panel.
- Se agregó el argumento `--panel-auto` en `app.py`: al iniciar sesión, la tarea
  programada usa este argumento y revisa la preferencia antes de abrir la
  ventana. Si el usuario marcó la casilla, el panel no se abre solo.
- El acceso directo del menú Inicio sigue usando `--panel` (abre siempre,
  ignora la preferencia).
- El instalador (`instalar_tareas.ps1`) actualizó la tarea del panel para usar
  `--panel-auto`.

### 11.3 Qué se probó

- `config_usuario.py` lee y escribe correctamente la preferencia.
- Por defecto, `mostrar_ventana_inicio` es `True`.
- Al marcar la casilla, se guarda `false` y el panel no se abre automáticamente.

---

## 12. Edición empresarial: servidor central y cliente operario

### 12.1 Qué se buscaba

La edición local funciona por equipo, pero el área de TI necesita ver el estado
de todas las computadoras desde un solo lugar. Se necesitaba un servidor
central que reciba reportes de los agentes y un panel web para TI.

### 12.2 Arquitectura implementada

| Componente | Archivo | Función |
|------------|---------|---------|
| Servidor central | `servidor_central.py` | Recibe reportes por HTTP, valida firma HMAC-SHA256, almacena en SQLite, expone panel web |
| Cliente operario | `cliente_gui.py` | Interfaz gráfica para inscribir equipo y enviar reportes de prueba |
| Librería cliente | `cliente_enterprise.py` | Inscripción con token único, envío de reportes firmados, envío de avisos |

### 12.3 Flujo validado

1. **Servidor central**: se instala con `SaludPC-Servidor-Central-1.0.1.exe`, escucha en el puerto 8443.
2. **Inscripción**: el cliente operario envía ID del equipo, organización, sede y área; el servidor devuelve un token único.
3. **Envío de reporte**: el cliente envía métricas (CPU, RAM, disco, temperatura) con firma HMAC-SHA256.
4. **Panel de TI**: el servidor muestra una tabla con todos los equipos, sus estados (ok, atencion, accion, aprendizaje, desconocido) y sus últimas métricas.

### 12.4 Prueba de flujo completo

Se validó el ciclo completo en localhost:

| Paso | Acción | Resultado |
|------|--------|-----------|
| 1 | Inscripción de `OPERARIO-001` | Token generado: `159991b985e9fd5db81b5adc98d1096e` |
| 2 | Envío de reporte (CPU 32.5%, RAM 45.0%, Disco 24.7%, Temp 54.0°C) | `Reporte recibido` |
| 3 | Envío de aviso (atencion) | `Aviso recibido` |
| 4 | Consulta panel de TI | Equipo visible con estado `ok` y métricas |

### 12.5 Seguridad

- Token único por equipo basado en ID + clave organizacional.
- Firma HMAC-SHA256 en cada reporte; el servidor rechaza firmas inválidas con `403 Forbidden`.
- Lista cerrada de campos técnicos: CPU, memoria, disco, temperaturas, estado del agente. Sin datos personales ni de pacientes.

### 12.6 Instaladores generados

| Instalador | Ruta | Tamaño |
|------------|------|--------|
| Servidor Central 1.0.0 | `dist_instalador\instaladores\SaludPC-Servidor-Central-1.0.0.exe` | 9.65 MB |
| Cliente Operario 1.0.0 | `dist_instalador\instaladores\SaludPC-Cliente-Operario-1.0.0.exe` | 24.16 MB |
| Servidor Central 1.0.1 | `dist_instalador\instaladores\SaludPC-Servidor-Central-1.0.1.exe` | 9.62 MB |
| Cliente Operario 1.0.1 | `dist_instalador\instaladores\SaludPC-Cliente-Operario-1.0.1.exe` | 23.05 MB |
| Servidor Central 1.0.2 | `dist_instalador\instaladores\SaludPC-Servidor-Central-1.0.2.exe` | 9.62 MB |
| Cliente Operario 1.0.2 | `dist_instalador\instaladores\SaludPC-Cliente-Operario-1.0.2.exe` | 23.06 MB |

Los instaladores 1.0.1 cierran la instancia anterior antes de copiar los
archivos: `taskkill /F /IM SaludPC-Servidor.exe /T` en el servidor y
`taskkill /F /IM SaludPC-Cliente-Operario.exe /T` en el operario. Así se evita
el error de «archivo en uso» al actualizar sobre una versión abierta.

### 12.7 Mejora 1.0.1: el cliente no se cierra y muestra el aprendizaje

La versión 1.0.0 tenía dos defectos que solo aparecían en el equipo del
operario:

1. **La ventana desaparecía al inscribir.** El cliente creaba una segunda
   ventana (`CTk`) para el panel, ocultaba la de configuración y el panel fallaba
   al construirse. El origen exacto era `PanelUsuario._log()`, que usaba
   `self.area_log`, un atributo que nunca se creaba. La excepción ocurría después
   de ocultar la configuración, por eso el usuario veía «desaparecer» todo.
2. **El token no se guardaba.** `cliente_enterprise.py` importaba un módulo
   `rutas` que no estaba incluido en el paquete de PyInstaller; el error se
   silenciaba y el equipo volvía a pedir inscripción en cada arranque.

La 1.0.1 reescribe el cliente como **una sola ventana** que alterna entre la
inscripción y el panel, sin crear una segunda raíz de Tk. La comunicación del
hilo de monitoreo con la interfaz pasa por una `queue.Queue` que se vacía con
`after(150)`, de modo que nunca se llama a Tk desde un hilo de trabajo.

Al completar la inscripción, el mismo programa pasa al panel de aprendizaje y
confirma explícitamente que el sistema está funcionando. El panel muestra:

- Encabezado con «● Sistema activo» cuando el servidor acepta el reporte.
- Tarjeta «Aprendizaje del equipo» con barra de progreso y porcentaje.
- Contador de muestras (`de 300`) y de días locales (`de 3`).
- Estado actual (OK / ATENCIÓN / ACCIÓN) y el último envío.
- Actividad reciente y cuenta regresiva del próximo envío (60 s).

El avance no se inventa en el cliente: lo calcula el servidor central con
`GET /progreso`, protegido con el token del equipo. El endpoint cuenta muestras
y fechas locales distintas y devuelve `aprendizaje_completo`. El cliente guarda
`token_equipo.json` con ID, token, organización, sede, área y URL; al reabrir
entra directo al panel. Si el equipo ya estaba inscrito, el servidor responde
`409` con el token y el cliente lo recupera sin obligar a borrar nada.

La base de datos central se migra sola: si la tabla `reportes` no tiene la
columna `fecha_local`, se agrega con `ALTER TABLE` sin perder las filas
anteriores y el progreso usa `COALESCE(fecha_local, substr(timestamp,1,10))`.

**Pruebas ejecutadas**

| Prueba | Resultado |
|--------|-----------|
| Inscripción, reporte y `/progreso` con servidor Python | Token, reportes aceptados, 2 muestras / 1 día, token falso rechazado con 403 |
| Inscripción desde la GUI y apertura del panel | `vista=panel`, «● Sistema activo», «Muestras: 1 de 300», «Días: 1 de 3» |
| Reapertura del cliente con token guardado | Entra directo al panel con el equipo y la conexión activa |
| Cliente `.exe` compilado contra servidor de prueba | Envió reporte y consultó `/progreso` (`HTTP 200`) |
| `/progreso` desde el `.exe` del servidor | 2 muestras, 1 día, 1 %, `aprendizaje_completo=false`; token falso → 403 |
| Migración de base antigua | Columna `fecha_local` agregada y fila anterior conservada |

El límite sigue siendo el mismo: el panel dice «Aprendiendo» hasta reunir 300
muestras y 3 fechas locales. No se aceleró el proceso ni se falsearon fechas;
el operario ve el avance real y sabe que el sistema está trabajando.

### 12.8 Mejora 1.0.2: estado APRENDIENDO, inicio oculto e instancia única

La 1.0.1 ya no se cerraba al inscribir, pero el panel mostraba de inmediato el
estado calculado por el cliente (OK / ATENCIÓN / ACCIÓN) aunque el servidor
todavía estuviera contando muestras. La 1.0.2 separa esas dos cosas:

- Mientras el servidor no confirme `aprendizaje_completo`, el panel muestra
  **APRENDIENDO** y explica que aún no hay diagnóstico. El cambio a OK,
  ATENCIÓN o ACCIÓN ocurre solo cuando `/progreso` devuelve 300 muestras y 3
  fechas locales.
- El servidor guarda el estado real que envió el equipo en la tabla `reportes`,
  pero el estado visible del equipo (`equipos.estado`) se fuerza a
  `en_aprendizaje` hasta completar la línea base. Así el panel de TI no presenta
  como «OK» un equipo que todavía no tiene historia suficiente.
- El listado y el panel calculan el estado visible en cada consulta, no solo al
  recibir un reporte. Un equipo que ya tenía `ok` guardado pasa a «En
  aprendizaje» apenas se actualiza el servidor, aunque todavía no haya enviado
  una muestra nueva.
- El panel de TI cuenta y muestra la tarjeta y el badge «En aprendizaje».

**Inicio oculto sin detener el envío**

El pie del panel tiene la casilla «No mostrar esta ventana al iniciar sesión
(el cliente sigue enviando reportes en segundo plano)». La preferencia se guarda
en `%PROGRAMDATA%\SaludPC\Cliente\config_cliente.json` con la clave
`mostrar_ventana_inicio`.

El instalador crea un acceso directo en `{commonstartup}` con el argumento
`--auto`. Al iniciar sesión, el cliente arranca solo y:

- si `mostrar_ventana_inicio` es `true`, muestra la ventana;
- si es `false`, se queda oculto y sigue enviando cada 60 segundos.

El acceso directo del escritorio y el del menú Inicio no llevan `--auto`, por lo
que una apertura manual siempre muestra la ventana. `--oculto` fuerza el inicio
oculto aunque la preferencia diga lo contrario.

**Cerrar, ocultar y salir**

- La X de la ventana ya no termina el programa: oculta la ventana y el cliente
  sigue enviando. La primera vez avisa que SaludPC continúa activo.
- El botón «Ocultar» hace lo mismo sin diálogo.
- El botón «Salir» pide confirmación y detiene el monitoreo.

**Una sola instancia**

El cliente usa el mutex `Local\SaludPC-Cliente-Operario` y un socket de control
en `127.0.0.1:8457`. Si el usuario abre el acceso directo mientras la instancia
oculta sigue trabajando, la segunda apertura no crea otra ventana ni otro hilo:
envía la orden `SHOW` a la instancia existente, que se muestra, y termina sola.

**Pruebas ejecutadas**

| Prueba | Resultado |
|--------|-----------|
| Lógica `estado_equipo_visible` | 1/1 y 299/3 → `en_aprendizaje`; 300/3 → estado del reporte; sin reporte → `desconocido` |
| Un reporte con estado `accion` | `equipos.estado = en_aprendizaje`, el reporte conserva `accion` |
| 300 muestras en 3 fechas | `aprendizaje_completo=true` y el equipo visible pasa al estado real |
| Cliente Python con `--auto` y preferencia oculta | Proceso vivo, ventana no visible, 1 reporte recibido |
| Segunda apertura del cliente | Termina sola y muestra la ventana de la primera instancia |
| Servidor y cliente `.exe` 1.0.2 | Portada v1.0.2, inscripción, reporte, estado `en_aprendizaje`, oculto y reapertura con `SHOW` |
| Copia de la base real (`Pc-002`, 16 reportes, estado guardado `ok`) | El listado y la portada muestran `en_aprendizaje`; el detalle conserva los 16 reportes |

Los instaladores 1.0.2 se generaron con Inno Setup 7.1.1 y se probaron los
ejecutables empaquetados en una carpeta temporal, sin tocar la base real.

### 12.9 Alertas después del aprendizaje: qué hace hoy y qué falta

Hoy la edición empresarial **no tiene un modelo estadístico de anomalías** como
la edición local 0.5.3. El «aprendizaje» empresarial es un conteo: 300 muestras y
3 fechas locales. Mientras ese conteo no se completa, el equipo se muestra como
«En aprendizaje». Cuando se completa, el estado que llega en cada reporte es el
que calcula el cliente con umbrales fijos:

| Condición | Estado |
|---|---|
| CPU > 90 % o RAM > 95 % | `accion` (Requiere acción) |
| CPU > 80 % o RAM > 85 % | `atencion` (Atención) |
| Resto | `ok` (Normal) |

Con esos umbrales, después del aprendizaje **sí se muestra la anomalía en el
panel**: el reporte lleva el estado, el servidor lo guarda y la portada del panel
de TI cambia el badge y las tarjetas de resumen (se refresca cada 30 segundos).
El detalle del equipo conserva el estado real de cada reporte aunque el equipo
todavía esté en aprendizaje.

Lo que **no** existe todavía:

- No hay alerta push, correo ni notificación al operario o al personal de TI.
- No hay una bandeja de alertas ni un historial de «avisos» visible en el panel.
  La tabla `avisos` y el endpoint `/aviso` existen, pero el cliente gráfico no
  los usa y el panel no los muestra.
- No hay detección de tendencia ni comparación contra el baseline del propio
  equipo; solo umbrales fijos.
- Si el equipo supera un umbral durante el aprendizaje, el panel de TI sigue
  mostrando «En aprendizaje» (el estado real queda en la tabla de reportes),
  porque todavía no hay línea base para decidir si es normal para ese equipo.

La fase siguiente natural es portar a la edición empresarial el baseline
estadístico de la 0.5.3 (p95/p99, pisos y techos, 3 de 5 muestras para amarillo
y 2 de 5 para rojo) y agregar una bandeja de alertas con confirmación y correo
opcional. Eso responde a la pregunta «¿manda alerta?»: hoy avisa en el panel;
todavía no manda un aviso activo.

### 12.10 Conexión segura HTTPS: opciones y recomendación

Hoy el servidor escucha HTTP en el puerto 8443. La firma HMAC-SHA256 garantiza
que un reporte no fue alterado y que lo envió un equipo con token, pero **no
cifra** el tráfico: en la red local, alguien con acceso podría leer las métricas
(CPU, RAM, disco) y el token. No hay datos de pacientes, pero el token permite
enviar reportes falsos si se captura.

Opciones, de menor a mayor esfuerzo:

1. **Certificado autofirmado con pinning (recomendado para el piloto).** El
   servidor usa un certificado propio; el cliente incluye la huella o el
   certificado y rechaza cualquier otro. No requiere dominio público ni CA. Es
   el menor cambio: envolver el socket con `ssl.SSLContext` y validar la huella
   en `cliente_enterprise.py`.
2. **CA interna del hospital (AD CS).** Si el hospital ya tiene una CA interna,
   se emite un certificado para el servidor y los equipos confían en la CA. Es
   la opción más ordenada para producción, pero depende de TI.
3. **Proxy inverso con Caddy o nginx.** El servidor sigue en HTTP local y el
   proxy termina TLS. Caddy puede usar un certificado interno; nginx requiere
   configurar los certificados. Útil si se quiere separar TLS del programa.
4. **Let's Encrypt.** Solo funciona con un nombre DNS público y el servidor
   expuesto; no encaja con un servidor on-premise en red privada.
5. **mTLS (certificado de cliente).** Además del token, cada equipo presenta un
   certificado. Es lo más fuerte, pero complica el despliegue y la renovación.
6. **VPN o red segmentada.** No cambia el programa, pero aísla el tráfico. Sirve
   como complemento, no como sustituto de TLS.

Recomendación para el piloto: **HTTPS con certificado autofirmado y pinning**
(huella SHA-256 del certificado en el cliente), manteniendo el token y la firma
HMAC. Para producción, migrar a **CA interna** y, si se requiere, mTLS. El
cambio se puede hacer sin tocar el formato de los reportes: solo el transporte.

### 12.11 Mejora 1.0.3: búsqueda, filtros, informes y manual

La 1.0.2 dejó el panel de TI con tarjetas y tabla, pero sin forma de encontrar un
equipo entre muchos ni de entregar un informe. La 1.0.3 se concentra en el
trabajo diario del personal de TI:

- **Búsqueda:** filtro por ID de equipo, organización, sede o área, con
  coincidencias parciales. La consulta se hace en el servidor y también está
  disponible en la API (`/equipos?buscar=`).
- **Filtro por estado:** Todos, Normal, Atención, Requiere acción, En
  aprendizaje y Sin reportar. Se combina con la búsqueda (`/equipos?estado=`).
- **Barra de acciones:** el botón **↻ Actualizar** pasó a la derecha, junto al
  buscador, el filtro, **Buscar** y **Limpiar**. Las tarjetas de resumen siguen
  mostrando el panorama general; la tabla muestra solo lo filtrado y el texto
  «Mostrando: N» indica cuántos equipos quedaron visibles.
- **Generación de informes:** un modal pregunta qué informe necesita el usuario
  (todas las máquinas o un equipo específico) y en qué formato (HTML imprimible
  o CSV para Excel). El informe general incluye todos los equipos inscritos
  aunque la tabla esté filtrada. El informe por equipo incluye ficha, totales,
  promedios, máximos y el historial: hasta 500 reportes en HTML y todos en CSV.
- **Detalle con informe:** la pantalla de detalle tiene un botón directo para
  generar el informe de ese equipo.
- **Manual de uso:** se creó `MANUAL_DE_USO.md` y su versión DOCX/PDF, con
  instalación, operación local, servidor, cliente, búsqueda, informes,
  privacidad, solución de problemas, preguntas frecuentes y glosario.

**Pruebas ejecutadas**

| Prueba | Resultado |
|--------|-----------|
| Portada 1.0.3 | Campo de búsqueda, filtro de estado, botón Actualizar a la derecha y botón de informe presentes |
| Búsqueda por ID, organización, sede y área | Devuelve solo los equipos que coinciden; sin coincidencias muestra un mensaje claro |
| Filtro por estado y combinación con búsqueda | `ok`, `atencion`, `en_aprendizaje` y combinaciones responden como se espera en la portada y en la API |
| Informe general HTML | Incluye todos los equipos, resumen por estado y enlaces a impresión y CSV |
| Informe general CSV | BOM de UTF-8, separador `;` y una fila por equipo |
| Informe por equipo HTML | Ficha, totales, promedios, máximos e historial; hasta 500 reportes |
| Informe por equipo CSV | Detalle completo, sin el límite de 500 |
| Escape de HTML | Organización y área con `<script>` se muestran escapadas, sin inyección |
| Errores | `/informe?tipo=equipo` sin ID devuelve 400; un ID inexistente devuelve 404 |
| Copia de la base real | `Pc-002` y `PC 003` aparecen en el informe general; el informe de `Pc-002` incluye sus 32 reportes y el CSV conserva las 33 líneas con cabecera |
| Manual | DOCX de 15 páginas y 3.332 palabras, con índice, encabezado y pie; PDF generado desde Word |

El cliente 1.0.2 sigue siendo compatible: el protocolo de inscripción, reportes y
progreso no cambió. Las novedades de la 1.0.3 son del panel del servidor.

---

## 13. Comparación rápida entre versiones

| Área | Alpha | 0.4.0 | 0.5.0 | 0.5.1 |
|---|---|---|---|---|
| Instalación | No | Sí, Inno Setup | Sí | Sí |
| Arranque automático | No | Sí, 3 tareas | Sí | Sí |
| Panel | No | Tkinter clásico | CustomTkinter, tema automático | Igual |
| Historial | No | No | Sí, 30 días | Igual |
| Suspensión / apagado | No | No | Sí | Igual |
| Reporte semanal | No | No | Sí, HTML | Igual |
| Aviso flotante | No | Notificación básica | Solo con panel abierto | Desde el servicio, con panel cerrado |
| Prueba del aviso | No | No | No | `--aviso` |
| Aprendizaje explicado | No | Parcial | «Aprendiendo» | Días y muestras restantes |
| Retención de eventos | CSV | Sin tabla de eventos | 400 días | 400 días |
| Límite del panel | — | 3 días | 3650 días | 3650 días |
| Pruebas en paralelo | — | Mutex fijo | `SALUD_PC_MUTEX` | `SALUD_PC_MUTEX` |

La 0.5.2 no cambió la interfaz: corrigió el momento en que se recalcula el
baseline. Antes, el contador de aprendizaje podía quedar hasta seis horas
atrasado; ahora se actualiza al arrancar (después de la primera muestra), al
cambiar el día local y cada seis horas. En el equipo real el aprendizaje terminó
a las 00:00:44 del 5 de noviembre, siete segundos después de la primera muestra
del día.

### 13.1 Qué agregaron la 0.5.2 y la 0.5.3

| Área | 0.5.2 | 0.5.3 |
|---|---|---|
| Baseline | Se refresca al arrancar, al cambiar el día y cada 6 h | Igual |
| Consumo del agente | — | Cabecera cada 5 s, promedio de 5 min, servicio + panel |
| Filtros del historial | — | Todos / Energía / Carga / Térmicas |
| Episodios de pico | — | Evento `pico` desde 5 min, con inicio, fin y duración |
| Atribución de procesos | — | Fuera de alcance |
| Índice de estrés | — | Fuera de alcance |

---

## 14. Qué funciona hoy con certeza y qué no

### 14.1 Comprobado

- La instalación 0.5.3 dejó el servicio, el panel, los datos y las tareas
  funcionando; Windows registra `DisplayVersion 0.5.3`.
- El servicio toma muestras y registra pausas (suspensiones y apagados).
- El baseline se genera solo y se refresca al arrancar, al cambiar el día y
  cada 6 horas.
- El aprendizaje terminó solo: 3 fechas locales y 1.127 muestras a las 00:00:44
  del 5 de noviembre; el baseline se refrescó después con 1.227 muestras.
- El baseline real tiene `aprendiendo: false` y seis métricas con valores.
- El panel abre solo y muestra estado, tarjetas, historial y filtros.
- El estado real es `ok` y las seis métricas están dentro de su límite.
- El servicio publica su consumo cada minuto y el panel lo suma al propio cada
  5 segundos; la cabecera no muestra «servicio sin datos».
- Los filtros Todos / Energía / Carga / Térmicas responden con los eventos
  reales; con solo eventos de energía, Carga y Térmicas muestran el mensaje
  vacío.
- El reporte semanal se genera; el del 5 de noviembre se actualizó a las 00:34.
- El aviso de prueba con el ejecutable instalado mostró la ventana durante 9
  segundos y cerró con código 0.
- El cliente operario 1.0.1 no se cierra al inscribir: pasa al panel de
  aprendizaje en la misma ventana, muestra «Sistema activo», el último envío y
  el avance real de muestras y días.
- El token del cliente se guarda en `%PROGRAMDATA%\SaludPC\Cliente\token_equipo.json`
  y, al reabrir, el programa entra directo al panel.
- El servidor 1.0.1 responde `/progreso` con el token correcto y rechaza un
  token falso con `403`.
- El ejecutable instalado 1.0.1 se probó en el equipo servidor: abrió la
  pantalla de inscripción sin token y, con un token de demostración, mostró el
  panel con «Sistema activo», «1 de 300», «1 de 3» y «Aprendiendo · faltan 299
  muestras y 2 día(s). El sistema está funcionando». El servidor registró el
  reporte y respondió `/progreso`.
- El cliente 1.0.2 muestra **APRENDIENDO** en «Estado actual» hasta que
  `/progreso` confirma las 300 muestras y las 3 fechas locales; recién entonces
  pinta OK / ATENCIÓN / ACCIÓN.
- La casilla «No mostrar esta ventana al iniciar sesión» guarda
  `mostrar_ventana_inicio` y el acceso directo de Inicio arranca con `--auto`.
  Con la preferencia en falso, el cliente quedó oculto y siguió enviando; una
  segunda apertura mostró la ventana de la instancia oculta y terminó sola.
- Cerrar con la X oculta la ventana; «Salir» detiene el monitoreo. El cliente
  oculto mantiene el envío cada 60 segundos.
- El servidor 1.0.2 fuerza `equipos.estado = en_aprendizaje` hasta completar
  300 muestras y 3 fechas locales. Un reporte con estado `accion` quedó como
  `en_aprendizaje` en el equipo y conservó `accion` en la tabla de reportes.
- Con 300 muestras en 3 fechas, `/progreso` devolvió `aprendizaje_completo=true`
  y el estado visible pasó al estado real del reporte.
- Sobre una copia de la base real (`Pc-002`, 16 reportes y estado guardado
  `ok`), el servidor 1.0.2 mostró `en_aprendizaje` en `/equipos` y en la
  portada, y el detalle conservó los 16 reportes. No fue necesario esperar un
  reporte nuevo ni modificar la base original.
- Los `.exe` empaquetados 1.0.2 (servidor y cliente) pasaron la prueba integral
  en una carpeta temporal: portada v1.0.2, inscripción, reporte, estado
  `en_aprendizaje`, inicio oculto y reapertura por segunda instancia.
- El servidor 1.0.3 busca por ID, organización, sede y área, y filtra por estado
  en la portada y en `/equipos`; el botón Actualizar quedó a la derecha junto al
  buscador.
- Los informes de la 1.0.3 se generan para todas las máquinas y para un equipo
  individual, en HTML imprimible y en CSV. El informe general no depende del
  filtro de la tabla; el informe por equipo incluye el historial completo en CSV.
- Las pruebas de la 1.0.3 incluyen escape de HTML, errores 400/404 y una copia de
  la base real con `Pc-002` (32 reportes) y `PC 003` (3 reportes).
- El manual de uso quedó en `MANUAL_DE_USO_SaludPC.docx` y
  `MANUAL_DE_USO_SaludPC.pdf`, generados desde `MANUAL_DE_USO.md`.
- Los datos quedan en el equipo; la edición local no envía nada a Internet.

### 14.2 Pendiente de comprobar en el equipo real

- Que aparezca un pico real y que el episodio guarde bien inicio, fin y
  duración. La lógica está probada en carpeta temporal, no con un pico real.
- Que los primeros avisos reales tengan sentido y no sean falsos positivos.
- El comportamiento durante una semana completa de uso normal.
- Revisar el reporte semanal y el historial cuando haya más eventos variados.
- Decidir si las tareas automáticas se registran para todos los usuarios o solo
  para el usuario que instala.
- Confirmar las tres tareas (Servicio, Panel y Vigia); su consulta requiere
  elevación.

### 14.3 Limitaciones conocidas

- El instalador no está firmado; SmartScreen puede advertir.
- No hay actualización automática.
- No hay forma de silenciar los avisos.
- El reporte no se envía por correo en la edición local.
- El historial se puede filtrar por categoría, pero no exportar.
- El historial no atribuye un pico a un proceso; esa función queda para una
  etapa posterior.
- No hay índice de estrés; el diagnóstico sigue siendo un baseline estadístico.
- Si el panel queda abierto durante una actualización, el instalador puede pedir
  «Reintentar» por un archivo bloqueado. Se resolvió cerrando el panel; forzar
  el cierre automático queda como mejora.
- El instalador no borra los datos al desinstalar (decisión deliberada, para no
  perder el historial por accidente).
- No hay diagnóstico de por qué un equipo dejó de reportar; solo se ve el hueco.
- Las tareas `SaludPC Servicio` y `SaludPC Panel` no se pueden consultar sin
  elevación; `SaludPC Vigia` sí aparece.
- El panel de aprendizaje del cliente 1.0.1 necesita el servidor 1.0.1 para
  mostrar el avance real; contra un servidor 1.0.0 el cliente sigue enviando
  reportes, pero informa que el avance no está disponible.
- El «aprendizaje» empresarial es un conteo de 300 muestras y 3 fechas locales,
  no un baseline estadístico como el de la edición local. El cliente empresarial
  usa umbrales fijos (CPU > 90 / RAM > 95 para acción; CPU > 80 / RAM > 85 para
  atención).
- No hay alerta push, correo ni bandeja de alertas. El panel de TI muestra el
  último estado del equipo y se refresca cada 30 segundos; la tabla `avisos`
  existe pero no se usa desde el cliente gráfico.
- El transporte es HTTP sin cifrar. HMAC-SHA256 protege la integridad y la
  autenticidad del reporte, pero no impide que alguien lea el token o las
  métricas en la red local.
- La versión 1.0.3 del servidor está probada en código y contra una copia de la
  base real, pero todavía no se recompiló con PyInstaller ni se generó su
  instalador; el equipo servidor sigue con la 1.0.1 en el puerto 8443.
- El informe por equipo en HTML muestra hasta 500 reportes para que sea
  imprimible; el detalle completo solo está en el CSV.
- El manual de uso describe la 1.0.3; si se instala una versión anterior del
  servidor, el panel no tendrá buscador ni generador de informes.
- El arranque automático del cliente es al iniciar sesión (acceso directo en
  `{commonstartup}`), no antes del login. No hay un servicio Windows real que
  recoja muestras con la sesión cerrada.
- El cliente operario envía `cpu_temp: null` porque no usa sensores de
  temperatura; el resto de métricas son CPU, RAM y disco.
- Los logs están en UTF-8 y PowerShell 5.1 los muestra con caracteres raros; no
  es un fallo del programa.

---

## 15. Decisiones que explican el diseño actual

Estas decisiones no son detalles internos: son la razón por la que el producto
se comporta como se comporta.

1. **Solo diagnóstico y prevención, nunca reparación.** El programa no cambia
   configuraciones, no borra archivos, no reinicia servicios ajenos y no
   “arregla” nada. Avisa para que una persona decida.
2. **Trabajar dentro de la sesión del usuario, sin botón “iniciar”.** La
   instalación deja todo funcionando; el usuario no tiene que acordarse de abrir
   nada.
3. **Una muestra por minuto, 90 días de detalle y resumen diario permanente.**
   Es suficiente para ver tendencias sin llenar el disco.
4. **Aprender antes de avisar.** Tres días y 300 muestras como mínimo. Evita
   falsos positivos y explica por qué al principio no hay alertas.
5. **Umbrales con pisos sanos y techos absolutos.** El baseline no puede
   declarar “normal” un valor peligroso. Tres de cinco muestras para Amarillo,
   dos de cinco para Rojo.
6. **Un solo lugar para las métricas: `metricas.py`.** Evita que cada módulo
   invente sensores o unidades distintas.
7. **Datos bajo control del usuario.** Todo local, sin envío a Internet sin una
   acción explícita.
8. **Aviso propio en vez de notificación del sistema.** Una ventana de la
   aplicación se ve igual en todos los equipos y no depende de que Windows
   silencie o agrupe notificaciones.
9. **El servicio avisa, el panel muestra.** Separar responsabilidades evita
   duplicados y permite avisar con la ventana cerrada.
10. **No borrar datos al desinstalar.** Es preferible dejar el historial a que
    una desinstalación accidental lo destruya.
11. **Cada proceso mide su propio consumo.** El servicio no intenta leer el
    panel ni el panel el servicio elevado: el servicio publica un JSON chico y
    el panel lo suma. Evita permisos y acoplamiento.
12. **Un pico es un episodio, no una foto.** Se guarda solo si duró 5 minutos o
    más; un episodio abierto que quedó huérfano más de 15 minutos se descarta
    para no inventar una duración.
13. **El historial se filtra por categorías cerradas.** Energía, carga y
    térmicas; un evento sin métrica reconocible cae en carga y no se pierde.

---

## 16. Edición empresarial: servidor central y cliente operario

La edición empresarial **está implementada y probada**. Estas son las decisiones tomadas y lo que se construyó.

### 16.1 Alcance

- **Un solo ejecutable con dos modos**: edición local y edición empresarial.
- **Panel de TI completo desde el inicio**, no una versión mínima.
- **Receptor on-premise**: los datos quedan en la infraestructura del hospital.
- **Receptor para Windows Server y Linux.**
- **SQLite para el piloto**, con diseño compatible con PostgreSQL para crecer.
- **Credencial híbrida**: una clave de organización para inscribir equipos y un
  token único por equipo.
- **HTTPS/TLS**, token por equipo y firma HMAC-SHA256.
- **Lista cerrada de campos técnicos**: CPU, memoria, disco, temperaturas y
  estado del agente. Sin actividad personal, datos de pacientes ni nombres de
  procesos.
- **Retransmisor local opcional** para redes con salida restringida.
- **Correo de aviso** que solo informa que hay un resumen disponible; no adjunta
  detalles.
- **Estados de equipo**: al día, atrasado, sin reportar, nunca reportó, en
  aprendizaje y requiere revisión. La distinción entre «sin datos» y
  «saludable» es obligatoria: un equipo que dejó de reportar no es un equipo
  sano.

### 16.2 Lo que el hospital puede hacer

- Registrar un equipo con ID y organización, sede y área.
- Definir horarios de recolección y envío.
- Ver tendencias, alertas, último reporte y equipos que dejaron de reportar.
- Autorizar el despliegue de forma transparente.
- Saber qué datos se recogen y cuáles no.

### 16.3 Lo que la edición empresarial no promete

- No garantiza evitar fallas.
- No reemplaza los procedimientos técnicos ni clínicos del hospital.
- No diagnostica pacientes ni procesa datos clínicos.
- No funciona como herramienta de vigilancia de personas.

### 16.4 Documentos de referencia

- `VISION_EDICIONES.md`: arquitectura y alcance de las dos ediciones.
- `PROTOCOLO_EMPRESARIAL.md`: inscripción, reportes, firma, estados, modelo de
  datos, configuración, retransmisor, correo y pruebas.

---

## 17. Qué sigue después de la mejora

El orden importa: la edición local está cerrada y funcionando; la empresarial está implementada y en piloto.

### 17.1 Inmediato: cerrar el ciclo básico

Estado al 5 de noviembre:

1. **Instalar la 0.5.3** y aceptar el UAC una sola vez. Hecho el 5 de noviembre
   alrededor de las 01:50; conservó datos y baseline.
2. **Comprobar que el servicio publica su consumo** en
   `consumo_servicio.json`. Hecho; el archivo se actualiza cada minuto.
3. **Comprobar que el panel suma servicio y panel** y actualiza la cabecera cada
   5 segundos. Hecho en el panel de desarrollo con datos reales.
4. **Probar los filtros** Todos / Energía / Carga / Térmicas. Hecho; con los
   eventos actuales solo Energía tiene contenido.
5. **Observar un pico real**. Pendiente; todavía no hubo uno. La lógica se
   probó en una carpeta temporal, sin tocar la base real.
6. **Confirmar que las tres tareas siguen activas** (Servicio, Panel y Vigia).
   Pendiente: las tareas Servicio y Panel requieren elevación para consultarlas.
7. **Revisar los primeros avisos reales** y ajustar umbrales si aparecen falsos
   positivos. Próximo paso; todavía no hubo un aviso real.

### 17.2 Corto plazo: pulir la edición local

- Evaluar la firma de código para reducir las advertencias de SmartScreen.
- Agregar un botón para silenciar avisos.
- Permitir exportar el historial (los filtros ya están).
- Forzar el cierre de cualquier `SaludPC.exe` durante la instalación para evitar
  el archivo bloqueado que obligó a pulsar «Reintentar».
- Evaluar actualización automática.
- Hacer una prueba de una semana completa y registrar los resultados en esta
  bitácora.
- Atribuir picos a procesos y evaluar un índice de estrés en una etapa
  posterior, sin incluirlos en la 0.5.3.

### 17.3 Después: consolidar la edición empresarial

La edición empresarial ya está implementada y probada. Los próximos pasos son:

1. **Instalar la 1.0.2** en el servidor central y en el equipo operario;
   comprobar que el panel muestra «APRENDIENDO», que la casilla de inicio oculto
   persiste y que el cliente sigue enviando con la ventana cerrada.
2. **Portar el baseline estadístico** de la edición local 0.5.3 al servidor
   empresarial (p95/p99, pisos y techos, 3 de 5 muestras para amarillo y 2 de 5
   para rojo), en lugar de los umbrales fijos actuales.
3. **Agregar una bandeja de alertas** con estados, confirmación y correo
   opcional; usar la tabla `avisos` que ya existe.
4. **Implementar HTTPS** con certificado autofirmado y pinning para el piloto;
   migrar a CA interna del hospital para producción.
5. **Evaluar mTLS y el retransmisor local** para redes con salida restringida.
6. **Piloto controlado** con pocos equipos de un área, y luego un hospital.
7. **Revisión de seguridad, privacidad, retención y auditoría** antes de escalar.
8. **Evaluar actualización automática** para los agentes.

### 17.4 Decisión tomada para el receptor

Se eligió **HTTP directo en la aplicación** sin proxy intermedio para la fase piloto. El servidor escucha en el puerto 8443 y se puede acceder desde cualquier equipo de la red local. Para producción se puede agregar TLS/SSL y un proxy inverso (nginx) si la infraestructura lo requiere.

---

## 18. Riesgos y cosas a vigilar

- **Falsos positivos al terminar el aprendizaje.** Los primeros días de alertas
  reales son los más importantes para calibrar.
- **Equipos que dejan de reportar.** En la edición empresarial hay que
  distinguir «sin datos» de «saludable»; en la local, el hueco se ve en el
  historial pero no se diagnostica.
- **Servicio detenido.** Sin servicio no hay muestras ni avisos.
- **Advertencia de SmartScreen.** Es esperable mientras el instalador no esté
  firmado.
- **Datos sensibles en el hospital.** La lista cerrada de campos técnicos y la
  ausencia de datos de pacientes son requisitos, no recomendaciones.
- **Crecimiento de la base.** SQLite alcanza para el piloto; PostgreSQL debe
  estar previsto antes de escalar.
- **Pruebas en el equipo real.** El servicio regenera el baseline al arrancar,
  así que no se puede inyectar un baseline falso para probar estados. Las
  pruebas válidas requieren datos reales o un entorno separado con
  `SALUD_PC_DATOS`.
- **Consumo del agente no es consumo del equipo.** La línea informa CPU y
  memoria del servicio y del panel; no atribuye el consumo a otros procesos.
- **Episodios descartados.** Si el servicio estuvo detenido más de 15 minutos,
  un episodio abierto se descarta para no inventar una duración.
- **Filtros por categoría.** Un evento sin métrica reconocible cae en Carga; no
  se pierde, pero puede no ser el filtro que el usuario espera.

---

## 19. Archivos importantes

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Servicio, argumentos, aviso, reporte, vigía |
| `main.py` | Panel, pestañas, filtros, aviso flotante |
| `agente.py` | Medición y publicación del consumo del servicio y del panel |
| `almacen.py` | SQLite, muestras, resumen diario, eventos |
| `eventos.py` | Pausas, categorías, episodios de pico y estado de aviso |
| `vigilante.py` | Diagnóstico y mensaje de aprendizaje |
| `reportes.py` | Reporte semanal HTML |
| `metricas.py` | Definición única de métricas y umbrales |
| `rutas.py` | Rutas de datos y recursos |
| `empaquetado/instalador.iss` | Instalador Inno Setup |
| `empaquetado/construir.ps1` | Compilación completa |
| `empaquetado/instalar_tareas.ps1` | Tareas programadas |
| `DOCUMENTACION_CAMBIOS.md` | Cambios 0.4.0 → 0.5.3, motivos y vacíos |
| `VISION_EDICIONES.md` | Arquitectura de las dos ediciones |
| `PROTOCOLO_EMPRESARIAL.md` | Protocolo de inscripción y reportes |
| `README.md` | Uso, privacidad y comandos |
| `tests/test_agente.py` | Prueba del consumo y frescura del JSON |
| `tests/test_episodios.py` | Prueba de categorías y episodios de pico |
| `tests/test_contador_dias.py` | Prueba del contador con 2 y 3 fechas |
| `tests/test_modelo_simulado.py` | Prueba aislada del modelo completo |
| `config_usuario.py` | Preferencias del usuario (mostrar/ocultar ventana al iniciar) |
| `servidor_central.py` | Servidor central de SaludPC Enterprise (receptor de reportes) |
| `cliente_enterprise.py` | Librería cliente (inscripción, envío de reportes, firma HMAC) |
| `cliente_gui.py` | Interfaz gráfica del cliente operario |
| `construir_servidor.ps1` | Script de compilación del servidor central |
| `construir_cliente.ps1` | Script de compilación del cliente operario |
| `instalador_servidor.iss` | Script Inno Setup del instalador del servidor |
| `instalador_cliente.iss` | Script Inno Setup del instalador del cliente |
---

## 20. Cierre

La edición local pasó de ser una prueba de concepto a un producto que se instala,
aprende y avisa. Tiene límites conocidos y cosas por pulir, pero el camino
recorrido está claro: primero se demostró que se podían leer los sensores;
después se hizo instalable; luego se volvió comprensible; se corrigió el aviso
para que no dependiera de que el usuario estuviera mirando la pantalla; se
corrigió el contador para que el aprendizaje termine solo; y ahora el panel
informa el consumo del agente, filtra el historial y guarda los picos como
episodios. Además, la edición empresarial está implementada: un servidor
central con panel de TI y un cliente operario con interfaz gráfica permiten
inscribir equipos y enviar reportes firmados desde cualquier computadora de la
red. La versión 1.0.1 corrigió el cierre inesperado del cliente al inscribir y
agregó un panel de aprendizaje que muestra, con datos reales del servidor, que
el equipo está aprendiendo y reportando. La versión 1.0.2 completó ese panel:
muestra APRENDIENDO hasta que la línea base está lista, permite ocultar la
ventana al iniciar sesión sin detener el envío, reabre la ventana con una
segunda instancia y hace que el servidor no marque OK a un equipo que todavía
está aprendiendo. La versión 1.0.3 llevó el panel de TI al trabajo diario:
buscador por equipo, organización, sede o área; filtro por estado; botón
Actualizar junto al buscador; e informes generales y por equipo en HTML o CSV.
El manual de uso reúne todo lo necesario para instalar, operar e interpretar el
programa.

Lo que sigue no es rehacer lo hecho, sino consolidarlo: recompilar e instalar el
servidor 1.0.3 y el cliente 1.0.2 en los equipos reales, revisar los primeros
avisos reales, observar un pico real y completar una semana de uso normal. Con
esa base estable, la siguiente fase es portar el baseline estadístico de la
0.5.3 a la edición empresarial, agregar una bandeja de alertas con correo
opcional e implementar HTTPS con certificado autofirmado y pinning.
