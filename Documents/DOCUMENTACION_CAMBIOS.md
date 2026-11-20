# Documentación de cambios — SaludPC 0.4.0 a 0.5.3

Este documento explica qué cambió entre la versión **0.4.0** y la **0.5.1**,
por qué se hizo cada cambio, qué comportamiento se esperaba y qué cosas **no**
quedaron contempladas. También incluye el diagnóstico de por qué no apareció
el aviso flotante después de instalar la 0.5.0, y las actualizaciones 0.5.2 y
0.5.3 al final.

---

## 1. Diagnóstico: por qué no apareció el aviso flotante

No es un error de instalación. El programa está funcionando, pero se cumplen
dos condiciones que impiden el aviso:

### 1.1 El equipo todavía está «Aprendiendo»

El baseline actual (`C:\ProgramData\SaludPC\baseline_DESKTOP-BLPM687.json`)
dice:

```json
{
  "aprendiendo": true,
  "dias": 1,
  "muestras": 194,
  "metricas": {}
}
```

El programa necesita **3 días y al menos 300 muestras** para conocer lo que es
normal en este equipo (`MIN_DIAS = 3`, `MIN_MUESTRAS = 300`). Mientras
`aprendiendo` sea `true`, el estado es **«Aprendiendo»** y, por diseño, **no se
generan alertas**. Es correcto: avisar antes de conocer el equipo produciría
falsos positivos.

Con una muestra por minuto, 194 muestras equivalen a unas 3 horas y media de
equipo encendido. Faltan días de uso normal.

### 1.2 El aviso solo se dispara cuando el panel ve un empeoramiento

La lógica actual del panel es:

1. Al abrir, guarda el estado actual como referencia (`estado_previo = None`).
2. En cada actualización compara el estado nuevo con el anterior.
3. Solo muestra el aviso si **empeora** estando el panel abierto:
   - de Normal a Atención o Revisar, o
   - de Atención a Revisar.
4. Nunca avisa al abrir el panel si el equipo **ya** estaba en Amarillo o Rojo.
5. Si el panel está cerrado, el servicio registra el cambio en el historial,
   pero **no muestra ningún aviso**.

Por eso, aunque el equipo hubiera pasado a Amarillo, al abrir el panel no
aparecería el aviso: el primer estado observado se toma como referencia.

### 1.3 Qué sí está funcionando

- El servicio tomó muestras y registró pausas (suspensión de 16 y 11 minutos).
- El baseline se generó y se está actualizando.
- El panel abre solo al iniciar sesión.
- El historial y el reporte semanal están disponibles.

**Conclusión:** el comportamiento observado era el esperado para un equipo en
aprendizaje. A partir de la **0.5.1**, el aviso ya no depende de que el panel
esté abierto: lo dispara el servicio cuando el estado empeora. El aprendizaje
sigue siendo necesario para no dar falsos positivos, pero ahora el panel indica
cuánto falta.

---

## 2. Cambios de la 0.5.0

### 2.1 Aviso flotante propio

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | Ventana sin bordes, abajo a la derecha, 400 × 148 px, siempre encima, 9 segundos, clic para abrir el panel. Usa los mismos colores y tipografía del panel. |
| **Motivo** | Una notificación de Windows puede quedar silenciada, agrupada o no mostrarse según la configuración del equipo. Una ventana propia garantiza que el aviso se vea igual en todos los equipos. |
| **Qué se esperaba** | Que al pasar de Normal a Atención/Revisar apareciera una sola vez, sin repetirse cada minuto. |
| **Qué no se contempló** | En la 0.5.0 solo funcionaba con el panel abierto, no avisaba al abrir con un estado ya alterado y no había forma de probarlo. Todo eso se corrigió en la 0.5.1 (ver sección 7). |

### 2.2 Historial en el panel

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | Segunda pestaña «Historial» con los últimos 30 días: suspensiones, apagados, reinicios, avisos y vueltas a la normalidad, agrupados por día y en lenguaje simple. |
| **Motivo** | El usuario necesitaba entender qué pasó y cuándo, no solo el estado del momento. |
| **Qué se esperaba** | Que una pausa larga se explicara como suspensión o apagado, y que los avisos quedaran registrados aunque el panel estuviera cerrado. |
| **Qué no se contempló** | No se puede filtrar ni exportar; muestra 30 días aunque la base guarde 400; no distingue el motivo exacto de cada suspensión (tapa, botón, inactividad). |

### 2.3 Detección de suspensión y apagado

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | Si hay un hueco de más de 3 minutos entre muestras, se compara la última marca con `psutil.boot_time()`: si la marca es anterior al arranque de Windows fue apagado/reinicio; si no, suspensión. |
| **Motivo** | Un hueco sin explicación parece un fallo del programa. Distinguirlos evita falsas alarmas y da contexto al historial. |
| **Qué se esperaba** | Textos como «Estuvo 2 horas en reposo» o «Estuvo apagado 1 día». |
| **Qué no se contempló** | Cambios de hora manuales, hibernación frente a suspensión y cortes de energía no se distinguen con precisión. |

### 2.4 Reporte semanal

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | Reporte HTML autocontenido de 7 días, con interpretación en lenguaje simple, que se abre en el navegador y se puede imprimir o guardar como PDF. Se genera bajo demanda (`--reporte`), cada 24 h por el servicio y se conservan 8. |
| **Motivo** | Tener una vista periódica para revisar tendencias sin interpretar gráficos complejos. |
| **Qué se esperaba** | Un documento entendible para alguien sin conocimientos técnicos, con nombres amigables y unidades legibles. |
| **Qué no se contempló** | No se envía por correo; no se puede programar desde el panel; no incluye comparación entre semanas; el HTML no está firmado ni tiene control de acceso. |

### 2.5 Tema automático y mejoras visuales

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | Migración a CustomTkinter 6.0.0 + Pillow 13.0.0, tema claro/oscuro según `AppsUseLightTheme` de Windows, tarjetas por métrica, barras de referencia y ventana de 880 × 640 centrada. |
| **Motivo** | La interfaz anterior se veía anticuada y no acompañaba el tema del sistema; el usuario pidió una estética cuidada. |
| **Qué se esperaba** | Panel legible en pantallas de 1366 × 768, con área útil de 720 px, sin cortar contenido. |
| **Qué no se contempló** | No hay escalado manual de texto; en pantallas muy chicas o con escala de Windows al 150 % puede necesitar ajustes. |

### 2.6 Cambios internos

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | Tabla `eventos` con índice y retención de 400 días; funciones `registrar_evento()` y `leer_eventos()`; mutex configurable con `SALUD_PC_MUTEX`; tarea del panel con límite de ejecución de 3650 días; empaquetado con `--collect-all customtkinter`. |
| **Motivo** | Evitar que el panel se cierre solo por el límite de 3 días de las tareas de Windows, permitir pruebas en paralelo y conservar el historial. |
| **Qué se esperaba** | Panel estable durante semanas y pruebas sin interferir con la instalación real. |
| **Qué no se contempló** | Las tareas `SaludPC Servicio` y `SaludPC Panel` requieren elevación para consultarse; el instalador no está firmado y SmartScreen puede advertir. |

---

## 3. Comparación rápida 0.4.0 → 0.5.0

| Área | 0.4.0 | 0.5.0 |
|---|---|---|
| Interfaz | Tkinter clásico | CustomTkinter, tema automático, tarjetas y barras |
| Historial | No disponible en el panel | Pestaña con 30 días en lenguaje simple |
| Suspensión / apagado | No se distinguían | Se clasifican y se explican |
| Aviso al usuario | Notificación básica | Ventana propia, abajo a la derecha, 9 s |
| Reporte | No existía | HTML semanal, bajo demanda y diario |
| Retención de eventos | No existía tabla de eventos | 400 días |
| Panel al iniciar sesión | Podía cerrarse a los 3 días | Límite de 3650 días |
| Pruebas en paralelo | Mutex fijo | `SALUD_PC_MUTEX` configurable |

---

## 4. Vacíos detectados y mejoras propuestas

### 4.1 Aviso independiente del panel (implementado en 0.5.1)

**Problema:** si el panel está cerrado, el usuario no se entera de nada hasta
que lo abre; y al abrirlo con un estado ya alterado tampoco ve el aviso.

**Solución aplicada:**
- El servicio dispara un proceso `--aviso` cuando el estado empeora.
- Un archivo local (`ultimo_estado_aviso.json`) recuerda el último estado
  avisado para no repetir el aviso en cada arranque.
- Si el equipo ya está en Atención o Revisar al iniciar, avisa una vez.
- Al mejorar, se actualiza la referencia sin mostrar nada; si vuelve a
  empeorar, avisa de nuevo.

### 4.2 Modo de prueba del aviso (implementado en 0.5.1)

`SaludPC.exe --aviso accion --mensaje "Prueba"` muestra el aviso y termina.
No altera datos ni estado.

### 4.3 Mostrar el aprendizaje en el panel (implementado en 0.5.1)

**Problema:** «Aprendiendo» no decía cuánto faltaba ni por qué no hay avisos.

**Solución aplicada:** el panel muestra «Estamos conociendo tu equipo (1 de 3
días, 194 de 300 muestras)».

### 4.4 Notificaciones al usuario final

**Problema:** el aviso dependía de que el panel estuviera abierto.

**Solución aplicada:** el servicio es el que detecta y dispara el aviso; el
panel ya no muestra avisos por su cuenta. Así no hay duplicados y funciona
aunque la ventana esté cerrada.

### 4.5 Otros vacíos

- No hay firma de código: SmartScreen puede advertir al instalar.
- No hay actualización automática.
- No hay forma de silenciar los avisos desde el panel.
- El reporte no se puede enviar por correo desde la edición local.
- El instalador no borra los datos al desinstalar (decisión deliberada).
- No hay diagnóstico de por qué un equipo dejó de reportar (solo se ve el
  hueco en el historial).

---

## 5. Cómo verificar el estado actual

```powershell
# Estado del baseline
Get-Content "C:\ProgramData\SaludPC\baseline_DESKTOP-BLPM687.json" -Raw

# Últimas líneas del servicio
Get-Content "C:\ProgramData\SaludPC\salud-servicio.log" -Tail 30

# Eventos registrados (requiere Python y el proyecto)
python ver_estado.py
```

El baseline debe mostrar `"aprendiendo": false` y `"metricas"` con valores para
que el equipo empiece a evaluar estados. A partir de ahí, un cambio sostenido
(3 de 5 muestras para Amarillo, 2 de 5 para Rojo) genera el evento y, con la
mejora 4.1, el aviso.

---

## 6. Nota sobre la edición empresarial

La 0.5.0 es la **edición para usuario final**: local, sin envío a Internet y sin
reparaciones. La edición empresarial (hospitales) no está implementada todavía
y requiere decisiones de arquitectura, seguridad y alcance antes de escribir
código. Ver `VISION_EDICIONES.md` y `PROTOCOLO_EMPRESARIAL.md`.

---

## 7. Actualización 0.5.1 — aviso independiente del panel

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | El servicio dispara el aviso flotante cuando el estado empeora, aunque el panel esté cerrado. Se agregó `--aviso <atencion|accion> --mensaje "..."` para probarlo. El panel ya no muestra avisos por su cuenta, así no se duplican. |
| **Motivo** | En la 0.5.0 el aviso dependía de que el panel estuviera abierto y de que viera el cambio; si el usuario no estaba mirando, el aviso se perdía. |
| **Qué se esperaba** | Que el usuario se entere del cambio en el momento, sin tener que abrir la ventana. |
| **Cómo se evita repetir** | Se guarda el último estado avisado en `C:\ProgramData\SaludPC\ultimo_estado_aviso.json`. Si el equipo arranca ya en Atención o Revisar, avisa una vez; al mejorar, actualiza la referencia sin avisar. |
| **Qué no se contempló** | No hay botón para silenciar los avisos; si el servicio no está corriendo, no hay aviso (el panel tampoco lo muestra); no hay historial de avisos mostrados, solo el último estado. |
| **Cómo probarlo** | `SaludPC.exe --aviso accion --mensaje "Prueba de aviso"`. Debe aparecer abajo a la derecha durante 9 segundos y abrir el panel al hacer clic. |

También se mejoró el texto de aprendizaje: ahora muestra
«Estamos conociendo tu equipo (1 de 3 días, 194 de 300 muestras)», para que se
entienda por qué todavía no hay alertas.

## 8. Actualización 0.5.2 — el baseline se refresca solo

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | El baseline se recalcula al arrancar (después de la primera muestra), al cambiar el día local y cada 6 horas. Si falla, reintenta a los 10 minutos. `almacen.contar_dias_muestras()` usa `date(ts, 'localtime')` y `COUNT(DISTINCT ts)`. |
| **Motivo** | El contador podía quedar hasta seis horas atrasado si el baseline se guardaba antes de la primera muestra del día. |
| **Qué se esperaba** | Que el aprendizaje termine solo cuando hay 3 fechas locales y 300 muestras, sin esperar el siguiente ciclo. |
| **Cómo se evita repetir** | El refresco se dispara por tres caminos: arranque, cambio de día y seis horas. Un fallo no bloquea el contador seis horas. |
| **Qué no se contempló** | No cambia la interfaz ni la regla de 3 días y 300 muestras. |

## 9. Actualización 0.5.3 — consumo, filtros y episodios

| Aspecto | Detalle |
|---|---|
| **Qué se hizo** | El servicio publica CPU y memoria en `consumo_servicio.json` una vez por minuto; el panel mide su proceso cada 5 s, suma ambos y muestra un promedio móvil de 5 minutos. El historial se filtra por Todos / Energía / Carga / Térmicas. Los picos de 5 minutos o más se guardan como evento `pico` con inicio, fin, máximo y duración. |
| **Motivo** | Faltaba saber cuánto consume el agente, ordenar el historial y conservar los picos como episodios en vez de fotos sueltas. |
| **Qué se esperaba** | Una cabecera discreta, filtros simples y un historial que no se llene de eventos de un minuto. |
| **Cómo se evita repetir** | El servicio no necesita leer el proceso elevado del panel ni al revés. Un pico solo se guarda si duró 5 minutos o más; un episodio abierto se descarta si el servicio estuvo detenido más de 15 minutos. La firma del historial usa `MAX(id)`. |
| **Qué no se contempló** | No hay atribución de procesos ni índice de estrés. El historial no se exporta. Si el panel queda abierto durante una actualización, el instalador puede pedir «Reintentar» por un archivo bloqueado. |
| **Cómo probarlo** | `python tests/test_agente.py` y `python tests/test_episodios.py`; en el panel, abrir Historial y cambiar el filtro. |
