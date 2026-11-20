# Propuesta Técnica — SaludPC Enterprise

**Versión:** 1.0 (borrador de diseño)  
**Fecha:** 5 de noviembre de 2026  
**Producto:** Salud de mi equipo (SaludPC)  
**Ámbito:** Edición empresarial para hospitales, clínicas y organizaciones  
**Estado:** Diseño completado. Implementación pendiente (fase 2).  

---

## Tabla de contenidos

1. [Introducción y contexto](#1-introducción-y-contexto)  
2. [Estado actual: versión local 0.5.3](#2-estado-actual-versión-local-053)  
3. [Visión de la versión Enterprise](#3-visión-de-la-versión-enterprise)  
4. [Arquitectura del sistema](#4-arquitectura-del-sistema)  
5. [Componentes técnicos](#5-componentes-técnicos)  
6. [Protocolo de comunicación y seguridad](#6-protocolo-de-comunicación-y-seguridad)  
7. [Panel de TI (receptor central)](#7-panel-de-ti-receptor-central)  
8. [Flujo operativo paso a paso](#8-flujo-operativo-paso-a-paso)  
9. [Requisitos de infraestructura](#9-requisitos-de-infraestructura)  
10. [Privacidad y cumplimiento](#10-privacidad-y-cumplimiento)  
11. [Hoja de ruta de implementación](#11-hoja-de-ruta-de-implementación)  
12. [Ejemplos de uso y código](#12-ejemplos-de-uso-y-código)  
13. [Riesgos y mitigaciones](#13-riesgos-y-mitigaciones)  
14. [Conclusión](#14-conclusión)  

---

## 1. Introducción y contexto

SaludPC nace como una herramienta de diagnóstico y prevención para equipos de cómputo individuales. Su versión local (0.5.3) se instala en una PC, toma una muestra por minuto, aprende qué es normal para ese equipo específico durante 3 días y 300 muestras, y avisa al usuario cuando algo se sale de lo habitual. Todo funciona de forma local: no envía nada a Internet y no repara nada por sí solo.

La **versión Enterprise** extiende este modelo a organizaciones con múltiples computadoras. En lugar de que cada equipo funcione de forma aislada, los agentes envían sus reportes a un **servidor central** gestionado por el área de TI o Informática. Así, un solo responsable puede ver el estado de todas las máquinas, detectar equipos que dejaron de reportar y recibir avisos centralizados, sin que el usuario final tenga que hacer nada.

---

## 2. Estado actual: versión local 0.5.3

La versión instalada actualmente en las computadoras del piloto incluye:

| Función | Estado |
|---------|--------|
| Recolección de una muestra por minuto | ✅ Implementado |
| Baseline estadístico (3 días, 300 muestras) | ✅ Implementado |
| Detección de suspensiones y apagados | ✅ Implementado |
| Panel local con historial y filtros (Todos / Energía / Carga / Térmicas) | ✅ Implementado |
| Consumo del agente en cabecera (servicio + panel) | ✅ Implementado |
| Episodios de pico (5 minutos o más) | ✅ Implementado |
| Reporte semanal HTML | ✅ Implementado |
| Envío automático de datos a un servidor central | ❌ No implementado |
| Panel centralizado para TI | ❌ No implementado |
| Inscripción de equipos con token único | ❌ No implementado |

**Conclusión:** la base local está probada y funcionando. La versión Enterprise reutiliza todo ese código y agrega la capa de red, el servidor central y el panel de TI.

---

## 3. Visión de la versión Enterprise

### 3.1 Objetivo

Permitir que el área de TI monitoree la salud de decenas o cientos de computadoras desde un solo punto, sin intervención del usuario final y sin enviar datos personales ni de pacientes.

### 3.2 Principios de diseño

| Principio | Descripción |
|-----------|-------------|
| **Un solo ejecutable con dos modos** | El mismo instalador puede usarse en modo local (usuario final) o modo enterprise (agente reportando a TI). |
| **Datos locales primero** | Cada agente sigue guardando su propia base SQLite local. El envío al servidor es una copia, no un reemplazo. |
| **Sin datos personales ni de pacientes** | La lista cerrada de campos técnicos incluye solo CPU, memoria, disco, temperaturas y estado del agente. |
| **Seguridad por diseño** | HTTPS/TLS, token único por equipo y firma HMAC-SHA256 en cada reporte. |
| **On-premise** | Los datos quedan en la infraestructura de la organización (servidor propio). No hay nube pública obligatoria. |
| **Retransmisor local opcional** | Para redes con salida a Internet restringida, se puede instalar un servidor intermedio en la red local. |

---

## 4. Arquitectura del sistema

```
┌─────────────────┐      HTTPS/TLS + HMAC       ┌─────────────────────────┐
│  Equipo A       │ ──────────────────────────> │   Servidor Central      │
│  (Agente)       │                             │   (Receptor)            │
│  SaludPC        │                             │   - Base de datos       │
│  --servicio     │                             │   - Panel de TI         │
│  --vigia        │                             │   - Correo de aviso     │
└─────────────────┘                             └─────────────────────────┘
        ▲                                               ▲
        │                                               │
┌─────────────────┐      HTTPS/TLS + HMAC       ┌─────────────────────────┐
│  Equipo B       │ ──────────────────────────> │   (Opcional) Retransmisor│
│  (Agente)       │                             │   Local                 │
│  SaludPC        │                             │                         │
└─────────────────┘                             └─────────────────────────┘
```

### 4.1 Elementos

| Elemento | Ubicación | Función |
|----------|-----------|---------|
| **Agente local** | Cada PC de la organización | Recolecta muestras cada minuto, calcula baseline, detecta picos, envía reportes al servidor central. |
| **Servidor central** | Servidor de la organización (Windows Server o Linux) | Recibe reportes, valida firmas, almacena en base de datos, expone panel web para TI. |
| **Base de datos central** | En el servidor central | Almacena equipos inscritos, reportes históricos y avisos. |
| **Panel de TI** | Navegador web conectado al servidor | Muestra estado de todos los equipos, últimos reportes, equipos sin reportar y avisos. |
| **Retransmisor local** (opcional) | Red interna de la organización | Recibe reportes de agentes sin salida a Internet y los reenvía al servidor central. |

---

## 5. Componentes técnicos

### 5.1 Agente local (`SaludPC-Enterprise.exe`)

Reutiliza el código de la versión local 0.5.3 y agrega:

| Módulo | Función |
|--------|---------|
| `app_enterprise.py` | Punto de entrada con comandos `--servicio`, `--panel`, `--inscribir`, `--enviar-reporte`. |
| `cliente_enterprise.py` | Cliente HTTP que envía reportes firmados al servidor central. |
| `inscribir_equipo()` | Registra el equipo en el servidor y obtiene un token único. |
| `enviar_reporte()` | Envía métricas (CPU, RAM, disco, temperaturas, estado) con firma HMAC-SHA256. |
| `enviar_aviso()` | Notifica al servidor cuando el equipo entra en estado de Atención o Acción. |

### 5.2 Servidor central (`servidor_central.py`)

Servidor HTTP ligero (sin dependencias externas de Python) que expone:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/inscribir` | POST | Registra un equipo nuevo y devuelve su token único. |
| `/reporte` | POST | Recibe y valida un reporte de un agente (verifica firma HMAC). |
| `/aviso` | POST | Registra un aviso generado por un equipo. |
| `/` | GET | Panel web de TI con lista de equipos y estados. |
| `/equipos` | GET | API JSON con todos los equipos inscritos. |

### 5.3 Base de datos central

Tablas propuestas (SQLite, compatible con PostgreSQL para crecer):

```sql
CREATE TABLE equipos (
    id_equipo     TEXT PRIMARY KEY,
    token         TEXT NOT NULL,          -- Token único por equipo
    organizacion  TEXT NOT NULL,
    sede          TEXT,
    area          TEXT,
    fecha_inscripcion TEXT NOT NULL,
    ultima_conexion TEXT,
    estado        TEXT DEFAULT 'en_aprendizaje'
);

CREATE TABLE reportes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_equipo     TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    estado        TEXT,
    cpu_load      REAL,
    ram_load      REAL,
    disk_used_pct REAL,
    cpu_temp      REAL,
    firma_hmac    TEXT NOT NULL,
    datos_json    TEXT,
    FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
);

CREATE TABLE avisos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_equipo     TEXT NOT NULL,
    estado        TEXT NOT NULL,
    mensaje       TEXT,
    timestamp     TEXT NOT NULL,
    FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
);
```

---

## 6. Protocolo de comunicación y seguridad

### 6.1 Inscripción de equipos

Antes de enviar cualquier dato, cada equipo debe inscribirse en el servidor central:

1. El agente envía su `id_equipo`, `organizacion`, `sede` y `area`.
2. El servidor genera un **token único** basado en el ID del equipo y una clave organizacional secreta.
3. El servidor devuelve el token al agente, que lo guarda localmente.

### 6.2 Envío de reportes

Cada reporte incluye:

- `id_equipo`: identificador del equipo.
- `timestamp`: fecha y hora en UTC.
- `estado`: `ok`, `atencion`, `accion` o `aprendizaje`.
- Métricas: `cpu_load`, `ram_load`, `disk_used_pct`, `cpu_temp`, etc.
- `firma_hmac`: firma HMAC-SHA256 del cuerpo del reporte usando el token del equipo.

El servidor verifica la firma antes de aceptar el reporte. Si falla, lo rechaza.

### 6.3 Cifrado

- **En tránsito:** HTTPS/TLS entre agente y servidor.
- **En reposo:** la base de datos central puede cifrarse a nivel de disco (BitLocker, LUKS, etc.).

---

## 7. Panel de TI (receptor central)

El servidor expone una página web simple accesible desde el navegador del responsable de TI.

### 7.1 Vista principal

| Columna | Contenido |
|---------|-----------|
| ID Equipo | Identificador único de la computadora. |
| Organización | Clave de organización asignada. |
| Sede / Área | Ubicación física o departamento. |
| Estado | `ok`, `atencion`, `accion`, `aprendizaje`, `desconocido`. |
| Última conexión | Fecha y hora del último reporte recibido. |
| Último reporte | Resumen de métricas (CPU, RAM, disco, temperatura). |

### 7.2 Estados de equipo

| Estado | Significado |
|--------|-------------|
| `aprendizaje` | El equipo aún no completó 3 días y 300 muestras. |
| `ok` | Todas las métricas dentro de lo normal. |
| `atencion` | Al menos una métrica en amarillo (3 de 5 muestras fuera de lo normal). |
| `accion` | Al menos una métrica en rojo (2 de 5 muestras fuera de lo normal). |
| `desconocido` | El equipo dejó de reportar (posiblemente apagado o sin red). |

### 7.3 Correo de aviso

Cuando un equipo entra en `accion` o deja de reportar por más de X horas, el servidor envía un correo al área de TI informando que hay un resumen disponible, sin adjuntar detalles sensibles.

---

## 8. Flujo operativo paso a paso

### 8.1 Instalación en cada equipo (agente)

1. Instalar `SaludPC-Enterprise.exe` en modo silencioso o asistido.
2. El agente comienza a recolectar muestras localmente (igual que la versión 0.5.3).
3. El equipo se inscribe en el servidor central con su ID, organización, sede y área.
4. El servidor devuelve un token único, guardado localmente.

### 8.2 Operación diaria (sin intervención del usuario)

1. Cada minuto, el agente toma una muestra y actualiza su baseline local.
2. Cada cierto intervalo (configurable, ej. cada 15 minutos o al detectar un cambio de estado), el agente envía un reporte firmado al servidor central.
3. Si el equipo pasa a `atencion` o `accion`, se envía un aviso inmediato al servidor.
4. El servidor almacena el reporte y actualiza el estado del equipo en el panel de TI.

### 8.3 Monitoreo por parte de TI

1. El responsable de TI abre el panel web del servidor central.
2. Ve todos los equipos registrados y sus estados en tiempo real.
3. Si un equipo está en `accion` o lleva mucho tiempo sin reportar, puede tomar acciones (contactar al usuario, revisar el equipo, etc.).

---

## 9. Requisitos de infraestructura

### 9.1 Servidor central

| Componente | Requisito mínimo | Recomendado |
|------------|------------------|-------------|
| Sistema operativo | Windows Server 2016+ o Linux | Windows Server 2022 / Ubuntu Server 22.04+ |
| Python | 3.10+ | 3.11+ |
| Base de datos | SQLite (piloto) | PostgreSQL (producción) |
| Red | Puerto 8443 abierto | Puerto 443 con certificado SSL válido |
| Almacenamiento | 5 GB libre | 20 GB libre (para historial largo) |

### 9.2 Agentes (computadoras de la organización)

| Componente | Requisito |
|------------|-----------|
| Sistema operativo | Windows 10 o 11 |
| RAM | 1 GB mínimo recomendado (2 GB ideal) |
| Disco | 100 MB libres para el programa + base de datos local |
| Red | Acceso HTTP/HTTPS al servidor central |

### 9.3 Red

- Los agentes deben poder alcanzar al servidor central por la red.
- En redes sin salida a Internet, usar un **retransmisor local** en la misma subred.

---

## 10. Privacidad y cumplimiento

### 10.1 Lista cerrada de campos técnicos

Los únicos datos que se recogen y envían al servidor central son:

- Uso del procesador (`cpu_load`)
- Uso de memoria RAM (`ram_load`)
- Uso del disco (`disk_used_pct`)
- Temperatura del procesador (`cpu_temp`)
- Temperatura del disco (`disk_temp`)
- Temperatura de la GPU (`gpu_temp`)
- Estado del agente (`ok`, `atencion`, `accion`, `aprendizaje`)

### 10.2 Qué NO se recoge

- Nombres de procesos ni de usuarios.
- Archivos personales ni documentos.
- Historial de navegación ni actividad del usuario.
- Datos de pacientes ni información clínica.
- Ubicación geográfica precisa (solo sede/área opcional asignada por el administrador).

### 10.3 Propiedad de los datos

Los datos quedan en la infraestructura de la organización (on-premise). El proveedor del software no accede a ellos.

---

## 11. Hoja de ruta de implementación

| Fase | Actividad | Estado |
|------|-----------|--------|
| 1 | Versión local 0.5.3 instalada y probada en 5 equipos | ✅ Completado |
| 2 | Congelar protocolo v1 de comunicación | 🔲 Pendiente |
| 3 | Implementar servidor central (`servidor_central.py`) | 🔲 Pendiente |
| 4 | Implementar inscripción de equipos y token único | 🔲 Pendiente |
| 5 | Integrar cliente enterprise en el ejecutable de los agentes | 🔲 Pendiente |
| 6 | Construir panel de TI web | 🔲 Pendiente |
| 7 | Agregar correo de aviso a TI | 🔲 Pendiente |
| 8 | Piloto controlado con 5-10 equipos reales | 🔲 Pendiente |
| 9 | Revisión de seguridad, privacidad y auditoría | 🔲 Pendiente |
| 10 | Despliegue progresivo en la organización | 🔲 Pendiente |

---

## 12. Ejemplos de uso y código

### 12.1 Inscribir un equipo (desde el agente)

```python
from cliente_enterprise import ClienteEnterprise

cliente = ClienteEnterprise(
    id_equipo="PC-001",
    token="",  # vacío la primera vez
    url_servidor="http://192.168.1.100:8443"
)

resultado = cliente.inscribir(
    organizacion="Hospital Central",
    sede="Sede Norte",
    area="Area 3"
)
print(resultado)
# Salida esperada: {"ok": true, "id_equipo": "PC-001", "token": "a1b2c3d4...", ...}
```

### 12.2 Enviar un reporte (desde el agente)

```python
cliente.token = "TOKEN_OBTENIDO_DEL_SERVIDOR"

reporte = {
    "estado": "ok",
    "cpu_load": 32.5,
    "ram_load": 45.0,
    "disk_used_pct": 24.7,
    "cpu_temp": 54.0,
}

resultado = cliente.enviar_reporte(reporte)
print(resultado)
# Salida esperada: {"ok": true, "mensaje": "Reporte recibido"}
```

### 12.3 Ejecutar el servidor central

```cmd
python servidor_central.py
```

Luego abrir en el navegador: `http://<ip-del-servidor>:8443/`

---

## 13. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| El servidor central se cae | Los agentes no pueden enviar reportes | Los datos siguen guardándose localmente en cada equipo; al volver el servidor, se pueden reenviar. |
| Un equipo deja de reportar | TI no ve su estado | El panel marca al equipo como `desconocido` y puede enviar un aviso por correo. |
| Robo de token de un equipo | Un atacante podría enviar reportes falsos | Los tokens son únicos por equipo y se rotan periódicamente. La firma HMAC impide falsificaciones sin el token. |
| Datos sensibles en la base central | Violación de privacidad | La lista cerrada de campos impide guardar datos personales. La base puede cifrarse en reposo. |
| Red sin salida a Internet | Los agentes no alcanzan al servidor | Usar un retransmisor local en la red interna. |

---

## 14. Conclusión

La versión Enterprise de SaludPC toma la base local ya probada (versión 0.5.3) y le agrega una capa de gestión centralizada para TI. Permite monitorear múltiples computadoras desde un servidor propio, con seguridad criográfica (HMAC-SHA256 y HTTPS) y sin comprometer la privacidad de los usuarios ni de los pacientes.

El siguiente paso concreto es implementar el servidor central y el cliente de envío, y ejecutar un piloto controlado con las 5 computadoras que ya tienen la versión local instalada.

---

**Fin del documento**

*Generado como propuesta de diseño para la fase 2 de SaludPC. Este documento no describe funcionalidades implementadas salvo la versión local 0.5.3.*
