# Protocolo empresarial — versión 1 (borrador)

Define cómo se inscribe un equipo, cómo envía sus reportes y cómo los recibe el
servidor del hospital. Es la base para implementar el agente y el receptor sin
mejorar improvisando.

> **Estado de implementación (9-nov-2026):** el piloto 1.0.2 usa HTTP en el
> puerto 8443 con token único y firma HMAC-SHA256. TLS/HTTPS está especificado
> aquí como objetivo y todavía no está implementado. Las opciones y la
> recomendación están en `BITACORA.md`, sección 12.10.

---

## 1. Decisiones de esta versión

- **Credencial híbrida**: una clave de organización solo sirve para inscribir;
  después cada equipo usa su propio token.
- **Receptor en el hospital**: HTTPS contra un servidor de la red interna.
- **Base de datos del piloto**: SQLite. El diseño evita SQL específico para
  poder migrar a PostgreSQL sin cambiar el protocolo.
- **Sistema operativo**: el receptor se entrega para Windows Server y Linux.
  El agente sigue siendo exclusivo de Windows.
- **Transporte**: HTTPS con TLS 1.2 o superior. En producción, certificado
  emitido por la organización; en piloto se admite uno interno documentado.
- **Contenido**: solo métricas técnicas agregadas. Lista cerrada de campos.

---

## 2. Flujo general

```
TI crea organización, sede, área y equipo
        │
        ▼
Equipo se inscribe con la clave de organización
        │
        ▼
Servidor valida que el equipo exista y devuelve token + clave de firma
        │
        ▼
El agente guarda la identidad y borra la clave de inscripción
        │
        ▼
Cada día (o según horario) envía un reporte firmado
        │
        ▼
Servidor valida, guarda y actualiza el estado del equipo
        │
        ▼
Panel de TI y correo de resumen
```

---

## 3. Inscripción

### 3.1 Requisito previo

TI debe crear el equipo en el panel con:

- `device_id` (identificador legible y único, por ejemplo
  `HOSP-CENTRAL-LAB-014`);
- organización, sede y área;
- intervalo esperado y margen de gracia.

Un equipo no registrado **no puede inscribirse**, aunque tenga la clave de la
organización. Así se evita que cualquier máquina con la clave aparezca en el
panel.

### 3.2 Pedido

```http
POST /api/v1/enroll
Content-Type: application/json
X-Org-Key: <clave de inscripción de la organización>
```

```json
{
  "device_id": "HOSP-CENTRAL-LAB-014",
  "agent_version": "0.6.0",
  "hostname": "PC-LAB-014",
  "os": "Windows 11 Pro 23H2",
  "fingerprint": "aea8d75abeed260e"
}
```

`hostname`, `os` y `fingerprint` son opcionales y sirven para que TI reconozca
el equipo. No se usan para autenticar.

### 3.3 Respuesta correcta

```http
201 Created
```

```json
{
  "device_id": "HOSP-CENTRAL-LAB-014",
  "token": "base64url-32-bytes",
  "signing_key": "base64url-32-bytes",
  "server_time": "2026-11-03T20:04:57-06:00",
  "schedule": {
    "mode": "daily",
    "time": "20:00",
    "jitter_minutes": 30,
    "timezone": "America/Mexico_City",
    "catch_up_minutes": 720
  },
  "limits": {
    "max_report_bytes": 262144,
    "max_queue_days": 14
  }
}
```

- `token`: se envía en `Authorization: Bearer ...` en cada reporte.
- `signing_key`: se usa para firmar el cuerpo del reporte. Permite que un
  retransmisor reenvíe sin poder alterar el contenido.
- Ambos se muestran **una sola vez**. El servidor guarda el hash del token y la
  clave de firma cifrada con una clave maestra del servidor.
- El agente guarda los datos en `identidad_equipo.json`, con permisos solo para
  administradores y SYSTEM, y elimina la clave de inscripción de la
  configuración.

### 3.4 Errores de inscripción

| Código | Situación | Acción del agente |
|---|---|---|
| 400 | Datos incompletos o inválidos | No reintentar; registrar error. |
| 401 | Clave de organización incorrecta | No reintentar; avisar a TI. |
| 403 | Equipo no registrado o revocado | No reintentar; avisar a TI. |
| 409 | El equipo ya estaba inscripto | Usar la identidad existente. |
| 429 | Demasiados intentos | Reintentar después de `Retry-After`. |
| 503 | Servidor no disponible | Reintentar con espera creciente. |

---

## 4. Reporte

### 4.1 Pedido

```http
POST /api/v1/reports
Authorization: Bearer <token>
Content-Type: application/json
X-Timestamp: 2026-11-03T20:05:00-06:00
X-Signature: hmac-sha256=<hex>
```

El cuerpo es el JSON del reporte. La firma se calcula sobre:

```
HMAC-SHA256(signing_key, X-Timestamp + "." + cuerpo_crudo)
```

El servidor:

1. Verifica el token.
2. Verifica que el `device_id` del cuerpo coincida con el del token.
3. Rechaza si el `X-Timestamp` difiere más de 5 minutos del reloj del servidor.
4. Recalcula la firma y la compara en tiempo constante.
5. Valida el esquema y rechaza campos desconocidos.
6. Guarda el reporte y actualiza `last_seen_at`.

### 4.2 Cuerpo

```json
{
  "report_id": "3f1c9a7e-5b2d-4c8a-9f10-2e7d6b1a4c55",
  "device_id": "HOSP-CENTRAL-LAB-014",
  "generated_at": "2026-11-03T20:00:00-06:00",
  "agent_version": "0.6.0",
  "window": {
    "from": "2026-11-02T20:00:00-06:00",
    "to": "2026-11-03T20:00:00-06:00"
  },
  "summary": {
    "cpu_load":      {"min": 4.0,  "avg": 18.2, "max": 71.0, "n": 1440},
    "cpu_temp":      {"min": 38.0, "avg": 52.4, "max": 78.0, "n": 1440},
    "ram_load":      {"min": 31.0, "avg": 54.1, "max": 82.0, "n": 1440},
    "disk_used_pct": {"min": 61.0, "avg": 61.0, "max": 61.0, "n": 1440},
    "disk_temp":     {"min": 30.0, "avg": 36.1, "max": 44.0, "n": 1440},
    "gpu_temp":      {"min": 35.0, "avg": 41.0, "max": 55.0, "n": 1440}
  },
  "hourly": [
    {"hour": "2026-11-03T08:00:00-06:00", "cpu_load": 22.1, "cpu_temp": 55.0}
  ],
  "state": "atencion",
  "baseline": {
    "learning": false,
    "days": 14,
    "samples": 20160
  },
  "alerts": [
    {
      "ts": "2026-11-03T17:42:00-06:00",
      "metric": "cpu_temp",
      "level": "atencion",
      "value": 84.0
    }
  ],
  "system": {
    "uptime_hours": 52.0,
    "last_boot": "2026-11-01T16:00:00-06:00",
    "disk_free_gb": 120.4
  }
}
```

### 4.3 Reglas del contenido

- `summary` incluye solo métricas de `metricas.UNIDADES`.
- `hourly` tiene como máximo 24 entradas, una por hora con datos.
- `alerts` incluye como máximo las 50 alertas de la ventana.
- `n` es la cantidad de muestras usadas para el resumen.
- No se envían muestras minuto a minuto.
- No se envían nombres de usuario, procesos, ventanas, archivos ni datos de
  pacientes.
- El servidor rechaza cualquier campo que no esté en el esquema.

### 4.4 Respuestas

```http
201 Created
```

```json
{"status": "accepted", "report_id": "...", "received_at": "..."}
```

| Código | Situación | Acción del agente |
|---|---|---|
| 200 | Reporte duplicado, ya estaba guardado | Quitarlo de la cola. |
| 201 | Guardado | Quitarlo de la cola. |
| 400 | Esquema inválido | No reintentar; registrar el error. |
| 401 | Token inválido | No reintentar; requerir nueva inscripción. |
| 403 | Equipo revocado | No reintentar; detener envíos. |
| 409 | `device_id` no coincide | No reintentar; avisar a TI. |
| 413 | Reporte demasiado grande | Reducir y reintentar una vez. |
| 422 | Valores fuera de rango | No reintentar; registrar. |
| 429 | Límite de frecuencia | Reintentar después de `Retry-After`. |
| 500/503 | Error del servidor | Reintentar con espera creciente. |

---

## 5. Idempotencia y reintentos

- `report_id` es un UUID v4 generado por el agente.
- El servidor tiene un índice único por `report_id`. Si llega dos veces, no
  duplica: responde 200.
- La cola local guarda el reporte completo antes de intentar enviarlo.
- Espera entre reintentos: 1 min, 5 min, 15 min, 1 h, 6 h, 12 h.
- Se conserva hasta 14 días. Al superar ese plazo, se descarta y se registra
  el motivo.
- Si el equipo estuvo apagado en el horario, envía al arrancar dentro de
  `catch_up_minutes`.
- La ventana del reporte se calcula desde el último envío exitoso, no desde la
  hora actual, para no perder el período.

---

## 6. Programación

Configuración inicial:

```json
{
  "mode": "daily",
  "time": "20:00",
  "jitter_minutes": 30,
  "timezone": "America/Mexico_City",
  "catch_up_minutes": 720
}
```

- `mode`: `daily` o `twice_daily`.
- `jitter_minutes`: dispersa los envíos para que 200 equipos no golpeen el
  servidor a la misma hora.
- `timezone`: zona IANA. En Windows se incluye `tzdata` para `zoneinfo`.
- `catch_up_minutes`: cuánto tiempo después del horario se acepta un envío
  tardío sin marcarlo como atrasado.

El agente revisa cada minuto si le toca enviar. No usa el Programador de
Windows para el envío: la cola y la ventana las controla el propio agente.

---

## 7. Estado del equipo en el servidor

El servidor calcula el estado con `last_seen_at`, el intervalo esperado y la
gracia configurada:

```
esperado = intervalo_minutos
gracia   = gracia_minutos

si nunca_reporto:                 "nunca"
si ahora <= last_seen + esperado + gracia:   "al_dia"
si ahora <= last_seen + 2*(esperado+gracia): "atrasado"
si no:                                        "sin_reportar"
```

Además:

- `requiere_revision` si el último reporte trae `state` `atencion` o `accion`.
- `en_aprendizaje` si el reporte trae `baseline.learning = true`.
- Un equipo `sin_reportar` **nunca** se muestra en verde, aunque su último
  reporte haya sido saludable.

Para horarios con fines de semana u horarios especiales, el servidor usa el
calendario de la sede. Si no hay calendario, usa el intervalo simple.

---

## 8. Modelo de datos del piloto (SQLite)

```sql
CREATE TABLE organizaciones (
    id            TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL,
    clave_hash    TEXT NOT NULL,
    activa        INTEGER NOT NULL DEFAULT 1,
    creada_en     TEXT NOT NULL
);

CREATE TABLE sedes (
    id            TEXT PRIMARY KEY,
    organizacion  TEXT NOT NULL REFERENCES organizaciones(id),
    nombre        TEXT NOT NULL,
    zona_horaria  TEXT NOT NULL,
    calendario    TEXT,
    creada_en     TEXT NOT NULL
);

CREATE TABLE areas (
    id       TEXT PRIMARY KEY,
    sede     TEXT NOT NULL REFERENCES sedes(id),
    nombre   TEXT NOT NULL
);

CREATE TABLE equipos (
    id                 TEXT PRIMARY KEY,          -- device_id
    organizacion       TEXT NOT NULL REFERENCES organizaciones(id),
    sede               TEXT NOT NULL REFERENCES sedes(id),
    area               TEXT REFERENCES areas(id),
    etiqueta           TEXT,
    token_hash         TEXT,
    firma_cifrada      TEXT,
    inscrito_en        TEXT,
    ultimo_reporte_en  TEXT,
    ultimo_reporte_id  TEXT,
    intervalo_min      INTEGER NOT NULL DEFAULT 1440,
    gracia_min         INTEGER NOT NULL DEFAULT 360,
    revocado_en        TEXT,
    creado_en          TEXT NOT NULL
);

CREATE TABLE reportes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id      TEXT NOT NULL UNIQUE,
    equipo         TEXT NOT NULL REFERENCES equipos(id),
    generado_en    TEXT NOT NULL,
    recibido_en    TEXT NOT NULL,
    ventana_desde  TEXT NOT NULL,
    ventana_hasta  TEXT NOT NULL,
    estado         TEXT NOT NULL,
    version_agente TEXT NOT NULL,
    firma_ok       INTEGER NOT NULL,
    cuerpo_json    TEXT NOT NULL
);

CREATE TABLE metricas (
    reporte  INTEGER NOT NULL REFERENCES reportes(id),
    metrica  TEXT NOT NULL,
    minimo   REAL,
    promedio REAL,
    maximo   REAL,
    n        INTEGER NOT NULL,
    PRIMARY KEY (reporte, metrica)
);

CREATE TABLE alertas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo         TEXT NOT NULL REFERENCES equipos(id),
    reporte        INTEGER NOT NULL REFERENCES reportes(id),
    momento        TEXT NOT NULL,
    metrica        TEXT NOT NULL,
    nivel          TEXT NOT NULL,
    valor          REAL,
    reconocida_en  TEXT,
    reconocida_por TEXT
);

CREATE TABLE usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario       TEXT NOT NULL UNIQUE,
    clave_hash    TEXT NOT NULL,
    rol           TEXT NOT NULL,   -- admin, supervisor, consulta
    organizacion  TEXT REFERENCES organizaciones(id),
    sede          TEXT REFERENCES sedes(id),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT NOT NULL
);

CREATE TABLE sesiones (
    id        TEXT PRIMARY KEY,
    usuario   INTEGER NOT NULL REFERENCES usuarios(id),
    expira_en TEXT NOT NULL,
    creada_en TEXT NOT NULL
);

CREATE TABLE auditoria (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    momento  TEXT NOT NULL,
    usuario  INTEGER REFERENCES usuarios(id),
    accion   TEXT NOT NULL,
    objetivo TEXT,
    detalle  TEXT
);

CREATE INDEX idx_reportes_equipo ON reportes (equipo, recibido_en);
CREATE INDEX idx_alertas_equipo ON alertas (equipo, momento);
CREATE INDEX idx_equipos_ultimo ON equipos (ultimo_reporte_en);
```

La clave de organización se guarda hasheada. La clave de firma de cada equipo
se guarda cifrada con una clave maestra del servidor
(`SALUD_PC_MASTER_KEY`), que no vive en la base.

---

## 9. Configuración del agente

`empresa.json`, en `C:\ProgramData\SaludPC`, con permisos de escritura solo
para administradores:

```json
{
  "version": 1,
  "enabled": true,
  "device_id": "HOSP-CENTRAL-LAB-014",
  "server_url": "https://salud.hospital.local",
  "enrollment_key": "se-borra-despues-de-inscribir",
  "schedule": {
    "mode": "daily",
    "time": "20:00",
    "jitter_minutes": 30,
    "timezone": "America/Mexico_City",
    "catch_up_minutes": 720
  },
  "tls": {
    "verify": true,
    "ca_file": null
  },
  "limits": {
    "max_queue_days": 14,
    "timeout_seconds": 20
  }
}
```

Después de inscribir, el agente escribe `identidad_equipo.json` y elimina
`enrollment_key` del archivo. Si la identidad no existe y no hay clave, el modo
empresarial queda inactivo y lo registra en el log.

---

## 10. Retransmisor de sede

- Se activa con `--relay` en el mismo servidor.
- Los equipos apuntan `server_url` al retransmisor de su sede.
- El retransmisor recibe el reporte, lo guarda en una cola local y lo reenvía
  al central cuando hay conexión.
- El central verifica la firma del equipo de punta a punta; el retransmisor no
  conoce las claves de los equipos.
- El retransmisor se autentica contra el central con un token de sede.
- Si el retransmisor no tiene conexión, los equipos siguen enviando a él y la
  cola local del retransmisor crece. El panel muestra los equipos como
  «atrasados» hasta que el central reciba los reportes.

Para el piloto se implementa primero el envío directo. El retransmisor queda
para la etapa de sedes con conectividad limitada.

---

## 11. Correo de resumen

- Salida por SMTP configurado por TI.
- Se envía una vez al día, después de la hora de reporte.
- Asunto: «SaludPC — N equipos requieren revisión, M sin reportar».
- Cuerpo con el enlace al panel y los totales. Sin adjuntos detallados.
- Si el correo falla, se reintenta y queda en auditoría.
- Nunca se envía información de pacientes ni datos personales.

---

## 12. Privacidad y seguridad

- Lista cerrada de campos; el servidor rechaza lo que no conoce.
- Sin datos personales, de pacientes, de navegación ni de documentos.
- TLS en tránsito; clave maestra fuera de la base; tokens hasheados.
- Acceso al panel con usuario y contraseña, sesión con caducidad y roles.
- Registro de auditoría de accesos y cambios.
- Retención: reportes 400 días; agregados diarios permanentes; alertas 400
  días. Configurable por el hospital.
- Copias de seguridad de la base y de la clave maestra.
- El equipo muestra que la supervisión está activa y el usuario puede ver su
  propio historial.
- El despliegue debe estar autorizado por la organización y comunicado al
  personal.

---

## 13. Plan de pruebas

1. **Inscripción**: equipo registrado, clave correcta → 201; equipo no
   registrado → 403; clave incorrecta → 401; repetida → 409.
2. **Firma**: cuerpo alterado → 401; timestamp viejo → 401; token revocado →
   403.
3. **Idempotencia**: mismo `report_id` dos veces → 201 y 200, un solo registro.
4. **Esquema**: campo desconocido → 400; métrica fuera de rango → 422.
5. **Sin conexión**: el agente guarda en cola y envía al recuperar; no pierde
   la ventana.
6. **Equipo apagado en el horario**: envía al arrancar dentro de la gracia.
7. **Sin reportes**: el panel muestra «sin reportar», nunca verde.
8. **Relay**: el central acepta el reporte reenviado y verifica la firma del
   equipo.
9. **Carga**: 200 equipos con envío diario y jitter; el servidor responde en
   menos de 1 segundo por reporte.
10. **Recuperación**: copia de seguridad y restauración sin perder equipos ni
    reportes.

---

## 14. Pendientes antes de implementar

- Confirmar el formato final de `empresa.json` y quién lo genera (instalador,
  GPO o script de TI).
- Definir si el servidor se publica con IIS, nginx o TLS directo en la
  aplicación.
- Definir la política de retención y copias de seguridad con el hospital.
- Confirmar si se envían número de serie y modelo de disco (hoy desactivados).
- Definir el calendario de sedes (fines de semana, feriados, turnos).
- Definir el procedimiento de revocación y reinstalación de un equipo.
