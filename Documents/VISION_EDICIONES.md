# Visión y arquitectura — Edición empresarial

Documento de trabajo. No describe código implementado: fija el alcance acordado
y las decisiones que faltan antes de construir.

---

## 1. Principio general

Una sola base de código, dos modos de funcionamiento:

- **Modo local** (edición para usuario final): lo que ya existe en la 0.5.0.
  No envía nada a Internet.
- **Modo empresarial**: el mismo agente, activado por un archivo de
  configuración instalado por TI, que envía reportes técnicos a un receptor
  central del hospital.

El modo local no debe degradarse ni volverse más pesado por la existencia del
modo empresarial. Si no hay configuración empresarial, el comportamiento es
exactamente el actual.

---

## 2. Qué comparten y qué cambia

| Pieza | Local | Empresarial |
|---|---|---|
| Recolección de métricas | Sí | Sí, igual |
| Baseline y diagnóstico | Sí | Sí, igual |
| Panel del usuario | Sí | Sí, igual (transparente) |
| Historial local | Sí | Sí |
| Reporte HTML local | Sí | Sí |
| Identificador de equipo | No | Sí, asignado por TI |
| Organización / sede / área | No | Sí, definidos por TI |
| Horario de envío | No | Configurado por TI |
| Envío a receptor central | No | Sí, cifrado y autenticado |
| Cola de reintentos | No | Sí |
| Panel de TI | No | Sí, web |
| Correo de resumen | No | Sí, solo aviso |
| Retransmisor de sede | No | Opcional |

---

## 3. Arquitectura

```
┌──────────────────────────┐        HTTPS + HMAC        ┌─────────────────────────┐
│ Equipo del hospital      │  ───────────────────────►  │ Receptor central        │
│                          │                            │ (servidor del hospital) │
│  Servicio SaludPC        │                            │                         │
│  ├─ colector             │                            │  ├─ API de ingesta      │
│  ├─ baseline             │                            │  ├─ base de datos       │
│  ├─ diagnóstico          │                            │  ├─ panel web de TI     │
│  ├─ cola local (outbox)  │                            │  ├─ consolidador        │
│  └─ programador de envío │                            │  └─ correo de resumen   │
│                          │                            │                         │
│  Panel local (usuario)   │                            │  Panel TI (navegador)   │
└──────────────────────────┘                            └─────────────────────────┘
          │                                                          ▲
          │  opcional: sede con conectividad limitada                │
          ▼                                                          │
┌──────────────────────────┐        HTTPS + HMAC                    │
│ Retransmisor de sede     │  ──────────────────────────────────────┘
│  ├─ recibe de equipos    │
│  ├─ guarda en cola       │
│  └─ reenvía al central   │
└──────────────────────────┘
```

### 3.1 Agente (equipo)

- Reutiliza `colector`, `almacen`, `cerebro`, `vigilante`, `eventos` y
  `reportes`.
- Agrega un módulo `empresa.py` con:
  - lectura y validación de la configuración;
  - identidad del equipo (ID + secreto);
  - cola local de envíos;
  - programador con ventana horaria, jitter y reintentos;
  - firma del payload.
- La recolección sigue siendo cada minuto. El **envío** es periódico, no cada
  minuto: se manda un resumen agregado.
- Si el equipo está apagado en el horario configurado, el envío se hace al
  arrancar, dentro de una ventana de gracia. No se pierde el reporte.

### 3.2 Receptor central

- API HTTP(S) para inscripción y recepción de reportes.
- Base de datos con organización, sede, área, equipo, reportes, métricas
  agregadas, alertas, usuarios y auditoría.
- Consolidador que calcula el estado de cada equipo y detecta los que dejaron
  de reportar.
- Panel web para TI.
- Servicio de correo con el resumen.
- Retención configurable: reportes detallados 400 días; agregados diarios
  permanentes.

### 3.3 Retransmisor de sede

- Misma aplicación, modo `--relay`.
- Recibe reportes de los equipos de su red, los guarda y los reenvía.
- La firma del equipo se conserva de punta a punta, para que el central pueda
  verificar que el reporte no fue alterado por el retransmisor.
- Se implementa después del piloto directo; no bloquea la primera versión.

---

## 4. Identidad y seguridad

### 4.1 Decisión tomada

Se acordó la **credencial híbrida**: una clave compartida por organización se
usa una sola vez para inscribir el equipo; el servidor devuelve un token único
por equipo y el agente borra la clave de inscripción. Para TI sigue siendo una
sola clave de despliegue, pero una filtración no obliga a cambiar todos los
equipos y permite revocar uno solo.

### 4.2 Controles mínimos

- TLS 1.2 o superior con certificado del hospital. Sin certificados
  autofirmados en producción (sí en piloto, documentado).
- Token por equipo guardado hasheado en el servidor; el agente lo guarda en un
  archivo con permisos solo para administradores.
- Firma HMAC-SHA256 del payload con el secreto del equipo. El retransmisor
  puede reenviar sin poder alterar el contenido.
- `report_id` único y marca de tiempo: el servidor rechaza duplicados y
  reportes con más de 7 días de antigüedad.
- Límite de tamaño y de frecuencia por equipo.
- Registro de auditoría: inscripciones, revocaciones, accesos al panel y
  cambios de configuración.
- El panel de TI no se expone a Internet; solo red interna o VPN.

---

## 5. Qué se envía (lista cerrada)

Solo datos técnicos. El servidor **rechaza** campos desconocidos.

```json
{
  "report_id": "uuid",
  "device_id": "HOSP-CENTRAL-AREA-014",
  "generated_at": "2026-11-03T20:00:00-06:00",
  "agent_version": "0.6.0",
  "window": {"from": "...", "to": "..."},
  "summary": {
    "cpu_load":      {"min": 4.0,  "avg": 18.2, "max": 71.0, "n": 1440},
    "cpu_temp":      {"min": 38.0, "avg": 52.4, "max": 78.0, "n": 1440},
    "ram_load":      {"min": 31.0, "avg": 54.1, "max": 82.0, "n": 1440},
    "disk_used_pct": {"min": 61.0, "avg": 61.0, "max": 61.0, "n": 1440},
    "disk_temp":     {"min": 30.0, "avg": 36.1, "max": 44.0, "n": 1440},
    "gpu_temp":      {"min": 35.0, "avg": 41.0, "max": 55.0, "n": 1440}
  },
  "hourly": [{"hour": "2026-11-03T08:00:00-06:00", "cpu_load": 22.1, "cpu_temp": 55.0}],
  "state": "ok",
  "baseline": {"learning": false, "days": 14},
  "alerts": [{"ts": "...", "metric": "cpu_temp", "level": "atencion", "value": 84.0}],
  "system": {"uptime_hours": 52.0, "last_boot": "...", "disk_free_gb": 120.4},
  "signature": "hmac-sha256..."
}
```

**No se envía:** nombres de usuario, actividad personal, ventanas abiertas,
archivos, historial de navegación, datos de pacientes, contenido de documentos,
credenciales ni capturas de pantalla.

**Opcional y desactivado por defecto:** número de serie del equipo, modelo de
disco y versión exacta de Windows. Sirven para soporte, pero identifican más al
equipo. Se decide con el hospital.

---

## 6. Estados de un equipo en el panel de TI

La regla más importante: **«sin datos» nunca se muestra como «saludable».**

| Estado | Significado | Color |
|---|---|---|
| Al día | Reportó dentro del intervalo esperado + gracia. | Verde |
| Atrasado | Pasó la gracia, pero aún no el doble del intervalo. | Amarillo |
| Sin reportar | Pasó más del doble del intervalo esperado. | Rojo |
| Nunca reportó | Está inscripto pero no envió el primer reporte. | Gris oscuro |
| En aprendizaje | Reporta, pero su baseline aún no está listo. | Azul/gris |
| Requiere revisión | Reportó un estado Amarillo o Rojo. | Naranja/rojo |

El intervalo esperado sale del horario configurado por TI, no de una constante.
Si un equipo se apaga todos los fines de semana, TI puede configurar un
calendario para no marcarlo como caído.

---

## 7. Panel de TI (primer alcance completo)

### 7.1 Pantallas

1. **Ingreso**: usuario y contraseña; sesión con caducidad.
2. **Resumen**: total de equipos, al día, atrasados, sin reportar, nunca
   reportaron, equipos que requieren revisión y últimos reportes recibidos.
3. **Equipos**: tabla con ID, organización, sede, área, estado, último reporte,
   versión del agente y alerta más reciente. Filtros por organización, sede,
   área y estado. Búsqueda por ID.
4. **Detalle del equipo**: tendencia de 30 días de las métricas principales,
   alertas, historial de reportes, último reporte completo y estado del
   baseline.
5. **Alertas**: lista priorizada por severidad y antigüedad, con equipo, métrica
   y valor.
6. **Administración**: organizaciones, sedes, áreas, equipos, usuarios y
   permisos; revocación de equipos; auditoría.

### 7.2 Roles

- **Administrador**: todo, incluida la gestión de usuarios y la revocación.
- **Supervisor**: ve y filtra todas las sedes, pero no administra usuarios.
- **Consulta**: solo lectura, limitada a una sede o área.

Para el piloto se pueden usar cuentas locales. La integración con Active
Directory / LDAP queda para una etapa posterior.

### 7.3 Requisitos de operación

- Copias de seguridad de la base y de la configuración.
- Registro de accesos y cambios.
- Actualización del servidor sin perder datos.
- El panel no depende de Internet: todos los recursos (gráficos, estilos) se
  sirven localmente.

---

## 8. Correo

- Se envía un resumen diario a TI, a una o varias casillas configuradas.
- Formato preferido: **aviso con enlace al panel**, sin adjuntos detallados.
- Ejemplo de asunto: «SaludPC — 3 equipos requieren revisión, 1 sin reportar».
- Si el envío falla, se reintenta y queda registrado; no se pierde el reporte.
- El correo no reemplaza al panel: es un recordatorio, no el canal principal.

---

## 9. Despliegue

- **Agente**: instalador silencioso con un archivo de configuración
  (`empresa.json`) provisto por TI, o parámetros de línea de comandos. Se puede
  desplegar por GPO/Intune o manualmente.
- **Receptor**: servicio del servidor del hospital, con TLS y base de datos.
  Se entrega con un instalador y una guía de puesta en marcha.
- **Transparencia**: el equipo muestra que la supervisión está activa; el
  usuario puede ver su propio panel e historial. El despliegue debe estar
  autorizado por la organización y comunicado al personal.
- **Desinstalación**: el agente se puede quitar; la configuración empresarial y
  los datos locales se eliminan según la política del hospital.

---

## 10. Fases propuestas

Aunque el panel se quiere completo desde el inicio, conviene construirlo en
entregables verificables:

1. **Protocolo e ingesta**: inscripción, token por equipo, recepción de
   reportes, modelo de datos, validación y auditoría.
2. **Agente empresarial**: configuración, cola, programador, firma y envío.
3. **Panel de TI**: ingreso, resumen, equipos, detalle, alertas, filtros,
   administración y roles.
4. **Correo y operación**: resumen diario, reintentos, copias de seguridad y
   guía de despliegue.
5. **Retransmisor de sede**: modo `--relay` y reenvío con firma de punta a punta.
6. **Piloto**: 10 a 20 equipos en una sede, con datos reales y ajuste de
   umbrales y horarios.

---

## 11. Decisiones tomadas y pendientes

### Tomadas

- Un solo ejecutable con dos modos.
- Panel de TI completo desde el inicio, por entregables verificables.
- Receptor en un servidor del hospital (on-premise).
- Credencial híbrida: clave de inscripción + token por equipo.
- El receptor se entrega para Windows Server y Linux.
- SQLite para el piloto, con diseño compatible con PostgreSQL.
- Primer paso: corregir el aviso de la 0.5.0 y escribir el protocolo
  (`PROTOCOLO_EMPRESARIAL.md`).

### Pendientes

1. **Publicación del servidor**: IIS, nginx o TLS directo en la aplicación.
2. **Credencial maestra**: dónde se guarda y cómo se rota.
3. **Frecuencia por defecto**: un envío diario al final de la jornada, por
   ejemplo 20:00 con hasta 30 minutos de dispersión, o dos envíos diarios.
4. **Datos opcionales**: ¿se envía número de serie y modelo de disco, o solo
   métricas?
5. **Alcance del piloto**: cuántos equipos, cuántas sedes y quién administra
   el servidor.
6. **Calendario de sedes**: fines de semana, feriados y turnos.
7. **Retención y copias de seguridad**: política del hospital.

---

## 12. Lo que esta edición no promete

- No garantiza que un equipo no vaya a fallar.
- No repara nada ni cambia configuraciones.
- No reemplaza los procedimientos técnicos ni clínicos del hospital.
- No recopila actividad personal ni datos de pacientes.
- No funciona como sistema de historia clínica ni de gestión de activos.
- No reemplaza el monitoreo de red, el antivirus ni el mantenimiento
  preventivo que ya tenga el hospital.
