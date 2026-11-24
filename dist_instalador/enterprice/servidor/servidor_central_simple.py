"""Servidor central de SaludPC Enterprise.

Recibe reportes de los agentes, valida firma HMAC-SHA256 y los almacena
en una base de datos SQLite central. Incluye un panel web para TI.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import ssl
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

PUERTO = 8443

# Usar ProgramData para la base de datos (permisos de escritura)
RUTA_DATOS = Path(os.environ.get("SALUD_PC_DATOS", os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "SaludPC")))
RUTA_DB = str(RUTA_DATOS / "SaludPC" / "servidor_central.db")

# Clave HMAC organizacional: obligatoria por variable de entorno.
# Si no se define, se genera una aleatoria y se advierte que no persiste.
CLAVE_HMAC_ORG = os.environ.get("SALUDP_ORG_KEY")
if not CLAVE_HMAC_ORG:
    CLAVE_HMAC_ORG = secrets.token_hex(32)
    log.warning(
        "SALUDP_ORG_KEY no definida. Se generó una clave temporal aleatoria. "
        "Defina SALUDP_ORG_KEY para producción."
    )

# Token de administración para operaciones de escritura (inscripción/eliminación).
# Obligatorio por variable de entorno en producción.
TOKEN_ADMIN = os.environ.get("SALUDP_ADMIN_TOKEN")
if not TOKEN_ADMIN:
    TOKEN_ADMIN = secrets.token_hex(32)
    log.warning(
        "SALUDP_ADMIN_TOKEN no definida. Se generó un token temporal aleatorio. "
        "Defina SALUDP_ADMIN_TOKEN para producción."
    )

# Orígenes permitidos para CORS. En producción, restringir a dominios conocidos.
CORS_ORIGIN_PERMITIDO = os.environ.get("SALUDP_CORS_ORIGIN", "*")

# Edad máxima aceptada de un reporte (minutos) para evitar ataques de repetición.
REPORTE_EDAD_MAX_MINUTOS = 60

# Nonces recibidos recientemente para evitar repetición (replay attacks).
_NONCES_RECIENTES: set = set()
_NONCES_LIMITE = 10000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("salud.servidor")

# ---------------------------------------------------------------------------
# Base de datos central
# ---------------------------------------------------------------------------

def crear_base():
    """Crea tablas de equipos y reportes si no existen."""
    # Asegurar que el directorio exista
    os.makedirs(os.path.dirname(RUTA_DB), exist_ok=True)
    conexion = sqlite3.connect(RUTA_DB)
    try:
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS equipos (
                id_equipo     TEXT PRIMARY KEY,
                token         TEXT NOT NULL,
                organizacion  TEXT NOT NULL,
                sede          TEXT,
                area          TEXT,
                fecha_inscripcion TEXT NOT NULL,
                ultima_conexion TEXT,
                estado        TEXT DEFAULT 'en_aprendizaje'
            );

            CREATE TABLE IF NOT EXISTS reportes (
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

            CREATE TABLE IF NOT EXISTS avisos (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                id_equipo     TEXT NOT NULL,
                estado        TEXT NOT NULL,
                mensaje       TEXT,
                timestamp     TEXT NOT NULL,
                FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
            );

            CREATE TABLE IF NOT EXISTS admins (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre        TEXT NOT NULL,
                token_hash    TEXT NOT NULL,
                fecha_creacion TEXT NOT NULL,
                activo        INTEGER DEFAULT 1
            );
            """
        )
        conexion.commit()

        # Insertar admin por defecto si no existe ninguno.
        fila = conexion.execute("SELECT COUNT(*) FROM admins").fetchone()
        if fila and fila[0] == 0:
            ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            token_hash = hashlib.sha256(TOKEN_ADMIN.encode("utf-8")).hexdigest()
            conexion.execute(
                """
                INSERT INTO admins (nombre, token_hash, fecha_creacion, activo)
                VALUES (?, ?, ?, 1)
                """,
                ("admin", token_hash, ahora),
            )
            conexion.commit()
            log.info("Administrador por defecto creado (token en SALUDP_ADMIN_TOKEN).")
    finally:
        conexion.close()


def generar_token(id_equipo):
    """Genera un token único por equipo basado en su ID y la clave organizacional."""
    material = f"{id_equipo}|{CLAVE_HMAC_ORG}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def registrar_equipo(id_equipo, organizacion, sede, area):
    """Inscribe un equipo y devuelve su token único."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        token = generar_token(id_equipo)
        ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conexion.execute(
            """
            INSERT OR REPLACE INTO equipos
                (id_equipo, token, organizacion, sede, area, fecha_inscripcion, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'en_aprendizaje')
            """,
            (id_equipo, token, organizacion, sede, area, ahora),
        )
        conexion.commit()
        return token
    finally:
        conexion.close()


def obtener_token(id_equipo):
    """Devuelve el token de un equipo inscrito, o None."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute(
            "SELECT token FROM equipos WHERE id_equipo = ?", (id_equipo,)
        ).fetchone()
        return fila[0] if fila else None
    finally:
        conexion.close()


def verificar_firma(datos_json, firma_recibida, token_equipo):
    """Verifica que la firma HMAC-SHA256 coincida con el token del equipo."""
    esperado = hmac.new(
        token_equipo.encode("utf-8"),
        datos_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(esperado, firma_recibida)


def guardar_reporte(id_equipo, datos, firma_hmac):
    """Guarda un reporte válido en la base central."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conexion.execute(
            """
            INSERT INTO reportes
                (id_equipo, timestamp, estado, cpu_load, ram_load, disk_used_pct,
                 cpu_temp, firma_hmac, datos_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_equipo,
                ahora,
                datos.get("estado"),
                datos.get("cpu_load"),
                datos.get("ram_load"),
                datos.get("disk_used_pct"),
                datos.get("cpu_temp"),
                firma_hmac,
                json.dumps(datos, ensure_ascii=False),
            ),
        )
        conexion.execute(
            "UPDATE equipos SET ultima_conexion = ?, estado = ? WHERE id_equipo = ?",
            (ahora, datos.get("estado", "desconocido"), id_equipo),
        )
        conexion.commit()
        return True
    except sqlite3.Error as error:
        log.error("Error guardando reporte: %s", error)
        return False
    finally:
        conexion.close()


def listar_equipos(filtro_busqueda=None):
    """Devuelve todos los equipos con su último estado."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        if filtro_busqueda:
            filtro = f"%{filtro_busqueda}%"
            filas = conexion.execute(
                """
                SELECT id_equipo, organizacion, sede, area, fecha_inscripcion,
                       ultima_conexion, estado
                FROM equipos
                WHERE id_equipo LIKE ? OR organizacion LIKE ? OR sede LIKE ? OR area LIKE ?
                ORDER BY fecha_inscripcion DESC
                """,
                (filtro, filtro, filtro, filtro),
            ).fetchall()
        else:
            filas = conexion.execute(
                """
                SELECT id_equipo, organizacion, sede, area, fecha_inscripcion,
                       ultima_conexion, estado
                FROM equipos
                ORDER BY fecha_inscripcion DESC
                """
            ).fetchall()
        return filas
    finally:
        conexion.close()


def obtener_ultimo_reporte(id_equipo):
    """Devuelve el reporte más reciente de un equipo."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute(
            """
            SELECT timestamp, estado, cpu_load, ram_load, disk_used_pct, cpu_temp
            FROM reportes
            WHERE id_equipo = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (id_equipo,),
        ).fetchone()
        return fila
    finally:
        conexion.close()


def obtener_historial_equipo(id_equipo, limite=50):
    """Devuelve el historial de reportes de un equipo."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        filas = conexion.execute(
            """
            SELECT timestamp, estado, cpu_load, ram_load, disk_used_pct, cpu_temp
            FROM reportes
            WHERE id_equipo = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (id_equipo, limite),
        ).fetchall()
        return filas
    finally:
        conexion.close()


def eliminar_equipo(id_equipo):
    """Elimina un equipo y todos sus reportes/avisos asociados."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute(
            "SELECT id_equipo FROM equipos WHERE id_equipo = ?", (id_equipo,)
        ).fetchone()
        if fila is None:
            return False, "no_encontrado"
        conexion.execute("DELETE FROM reportes WHERE id_equipo = ?", (id_equipo,))
        conexion.execute("DELETE FROM avisos WHERE id_equipo = ?", (id_equipo,))
        conexion.execute("DELETE FROM equipos WHERE id_equipo = ?", (id_equipo,))
        conexion.commit()
        return True, "ok"
    except sqlite3.Error as error:
        log.error("Error eliminando equipo: %s", error)
        return False, "error_db"
    finally:
        conexion.close()


# ---------------------------------------------------------------------------
# Manejador HTTP
# ---------------------------------------------------------------------------

class ManejadorSaludPC(BaseHTTPRequestHandler):
    """Maneja peticiones de los agentes y del panel web de TI."""

    def log_message(self, formato, *args):
        log.info("%s - %s" % (self.address_string(), formato % args))

    def _enviar_json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN_PERMITIDO)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(cuerpo)
        self.wfile.flush()

    def _enviar_respuesta(self, codigo, contenido, tipo="text/html; charset=utf-8"):
        cuerpo = contenido if isinstance(contenido, bytes) else contenido.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN_PERMITIDO)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _obtener_token_autorizacion(self):
        """Extrae el token del header Authorization: Bearer <token>."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return None

    def _verificar_admin(self):
        """Valida que la petición incluya un token de administrador válido."""
        token = self._obtener_token_autorizacion()
        if not token:
            return False
        esperado_hash = hashlib.sha256(TOKEN_ADMIN.encode("utf-8")).hexdigest()
        recibido_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(esperado_hash, recibido_hash)

    def _validar_nonce_y_edad(self, datos):
        """Valida que el reporte no sea una repetición y que sea reciente.

        Devuelve (ok, mensaje_error).
        """
        ahora = datetime.now(timezone.utc)

        # Nonce único para evitar repetición.
        nonce = datos.get("nonce")
        if not nonce:
            return False, "nonce requerido"
        if nonce in _NONCES_RECIENTES:
            return False, "nonce duplicado (reporte repetido)"
        if len(_NONCES_RECIENTES) >= _NONCES_LIMITE:
            _NONCES_RECIENTES.clear()
        _NONCES_RECIENTES.add(nonce)

        # Edad del reporte: no aceptar reportes más viejos del umbral.
        ts_reporte = datos.get("timestamp")
        if ts_reporte:
            try:
                momento = datetime.fromisoformat(ts_reporte)
                if momento.tzinfo is None:
                    momento = momento.replace(tzinfo=timezone.utc)
                edad_minutos = (ahora - momento).total_seconds() / 60.0
                if abs(edad_minutos) > REPORTE_EDAD_MAX_MINUTOS:
                    return False, f"reporte demasiado antiguo ({edad_minutos:.0f} min)"
            except (ValueError, TypeError):
                return False, "timestamp inválido"

        return True, None

    def _leer_cuerpo(self):
        largo = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(largo).decode("utf-8") if largo > 0 else ""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN_PERMITIDO)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        ruta = urlparse(self.path).path
        cuerpo = self._leer_cuerpo()

        if ruta == "/inscribir":
            if not self._verificar_admin():
                self._enviar_json(401, {"error": "Token de administrador requerido"})
                return
            self._ruta_inscribir(cuerpo)
        elif ruta == "/reporte":
            self._ruta_reporte(cuerpo)
        elif ruta == "/aviso":
            self._ruta_aviso(cuerpo)
        elif ruta == "/eliminar":
            if not self._verificar_admin():
                self._enviar_json(401, {"error": "Token de administrador requerido"})
                return
            self._ruta_eliminar_equipo(cuerpo)
        else:
            self._enviar_json(404, {"error": "ruta no encontrada"})

    def do_DELETE(self):
        ruta = urlparse(self.path).path
        cuerpo = self._leer_cuerpo()

        if ruta == "/eliminar":
            if not self._verificar_admin():
                self._enviar_json(401, {"error": "Token de administrador requerido"})
                return
            self._ruta_eliminar_equipo(cuerpo)
        else:
            self._enviar_json(404, {"error": "ruta no encontrada"})

    def do_GET(self):
        ruta = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        if ruta == "/":
            self._pagina_principal(params)
        elif ruta == "/equipos":
            self._api_equipos(params)
        elif ruta == "/detalle":
            id_equipo = params.get("id", [None])[0]
            if id_equipo:
                self._pagina_detalle(id_equipo)
            else:
                self._enviar_json(400, {"error": "id es requerido"})
        else:
            self._enviar_json(404, {"error": "ruta no encontrada"})

    def _ruta_inscribir(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (ValueError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return

        id_equipo = datos.get("id_equipo")
        organizacion = datos.get("organizacion")
        sede = datos.get("sede", "")
        area = datos.get("area", "")

        if not id_equipo or not organizacion:
            self._enviar_json(400, {"error": "id_equipo y organizacion son requeridos"})
            return

        token_existente = obtener_token(id_equipo)
        if token_existente is not None:
            log.warning("Intento de inscripción duplicada: %s", id_equipo)
            self._enviar_json(409, {
                "ok": False,
                "error": f"El equipo '{id_equipo}' ya está inscrito.",
                "id_equipo": id_equipo,
                "token": token_existente,
            })
            return

        try:
            token = registrar_equipo(id_equipo, organizacion, sede, area)
            log.info("Equipo inscrito: %s (%s)", id_equipo, organizacion)
            self._enviar_json(200, {
                "ok": True,
                "id_equipo": id_equipo,
                "token": token,
                "mensaje": "Equipo inscrito correctamente.",
            })
        except sqlite3.Error as error:
            log.error("Error inscribiendo equipo: %s", error)
            self._enviar_json(500, {"error": "Error de base de datos"})

    def _ruta_eliminar_equipo(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (ValueError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return

        id_equipo = datos.get("id_equipo")

        if not id_equipo:
            self._enviar_json(400, {"error": "id_equipo es requerido"})
            return

        exito, motivo = eliminar_equipo(id_equipo)
        if exito:
            log.info("Equipo eliminado: %s", id_equipo)
            self._enviar_json(200, {
                "ok": True,
                "id_equipo": id_equipo,
                "mensaje": "Equipo eliminado correctamente",
            })
        elif motivo == "no_encontrado":
            self._enviar_json(404, {"error": f"El equipo '{id_equipo}' no está inscrito"})
        else:
            self._enviar_json(500, {"error": "Error de base de datos"})

    def _ruta_reporte(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (ValueError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return

        id_equipo = datos.get("id_equipo")
        firma_recibida = datos.get("firma_hmac")

        if not id_equipo or not firma_recibida:
            self._enviar_json(400, {"error": "id_equipo y firma_hmac son requeridos"})
            return

        # Validar nonce y edad del reporte (anti-replay y anti-reporte antiguo).
        valido, motivo = self._validar_nonce_y_edad(datos)
        if not valido:
            log.warning("Reporte rechazado de %s: %s", id_equipo, motivo)
            self._enviar_json(400, {"error": motivo})
            return

        token = obtener_token(id_equipo)
        if token is None:
            log.warning("Reporte de equipo no inscrito: %s", id_equipo)
            self._enviar_json(403, {"error": "Equipo no inscrito"})
            return

        datos_sin_firma = dict(datos)
        datos_sin_firma.pop("firma_hmac", None)
        datos_sin_firma.pop("nonce", None)
        datos_sin_firma.pop("timestamp", None)
        cuerpo_sin_firma = json.dumps(datos_sin_firma, ensure_ascii=False, sort_keys=True)

        if not verificar_firma(cuerpo_sin_firma, firma_recibida, token):
            log.warning("Firma inválida de equipo: %s", id_equipo)
            self._enviar_json(403, {"error": "Firma inválida"})
            return

        if guardar_reporte(id_equipo, datos, firma_recibida):
            log.info("Reporte guardado: %s", id_equipo)
            self._enviar_json(200, {"ok": True, "mensaje": "Reporte recibido"})
        else:
            self._enviar_json(500, {"error": "Error guardando reporte"})

    def _ruta_aviso(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (ValueError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return

        id_equipo = datos.get("id_equipo")
        estado = datos.get("estado")
        mensaje = datos.get("mensaje", "")

        if not id_equipo or not estado:
            self._enviar_json(400, {"error": "id_equipo y estado son requeridos"})
            return

        # Autenticar al equipo mediante su token en el header Authorization.
        token_recibido = self._obtener_token_autorizacion()
        if not token_recibido:
            self._enviar_json(401, {"error": "Token de equipo requerido"})
            return

        token_esperado = obtener_token(id_equipo)
        if token_esperado is None:
            self._enviar_json(403, {"error": "Equipo no inscrito"})
            return
        if not hmac.compare_digest(token_recibido, token_esperado):
            self._enviar_json(403, {"error": "Token de equipo inválido"})
            return

        conexion = sqlite3.connect(RUTA_DB)
        try:
            ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conexion.execute(
                "INSERT INTO avisos (id_equipo, estado, mensaje, timestamp) VALUES (?, ?, ?, ?)",
                (id_equipo, estado, mensaje, ahora),
            )
            conexion.commit()
            log.info("Aviso registrado: %s - %s", id_equipo, estado)
            self._enviar_json(200, {"ok": True, "mensaje": "Aviso recibido"})
        except sqlite3.Error as error:
            log.error("Error guardando aviso: %s", error)
            self._enviar_json(500, {"error": "Error de base de datos"})
        finally:
            conexion.close()

    def _pagina_principal(self, params):
        """Panel de TI con estilo visual de SaludPC 0.5.3 y auto-refresco."""
        equipos = listar_equipos(params.get("buscar", [None])[0])

        estados = {}
        for e in equipos:
            estado = e[6] if len(e) > 6 else "desconocido"
            estados[estado] = estados.get(estado, 0) + 1

        total = len(equipos)
        ok = estados.get("ok", 0)
        atencion = estados.get("atencion", 0)
        accion = estados.get("accion", 0)
        aprendizaje = estados.get("aprendizaje", 0)
        desconocido = estados.get("desconocido", 0)

        filas_html = ""
        for equipo in equipos:
            id_equipo = equipo[0] if len(equipo) > 0 else ""
            org = equipo[1] if len(equipo) > 1 else ""
            sede = equipo[2] if len(equipo) > 2 else ""
            area = equipo[3] if len(equipo) > 3 else ""
            fecha_ins = equipo[4] if len(equipo) > 4 else ""
            ultima = equipo[5] if len(equipo) > 5 else ""
            estado = equipo[6] if len(equipo) > 6 else "desconocido"

            ultimo_reporte = obtener_ultimo_reporte(id_equipo) if id_equipo else None
            detalle = ""
            badge_clase = "badge-desconocido"
            if estado == "ok":
                badge_clase = "badge-ok"
            elif estado == "atencion":
                badge_clase = "badge-atencion"
            elif estado == "accion":
                badge_clase = "badge-accion"
            elif estado == "aprendizaje":
                badge_clase = "badge-aprendizaje"

            if ultimo_reporte:
                ts, est, cpu, ram, disco, temp = ultimo_reporte
                detalle = (
                    '<div class="detalle-metrica">'
                    '<span class="metrica-label">Último reporte:</span>'
                    f'<span class="metrica-valor">{ts}</span></div>'
                    '<div class="detalle-metrica">'
                    '<span class="metrica-label">Estado:</span>'
                    f'<span class="metrica-valor">{est}</span></div>'
                    f"<div class='detalle-metrica'>"
                    f"<span class='metrica-label'>CPU:</span>"
                    f"<span class='metrica-valor'>{cpu}%</span></div>"
                    f"<div class='detalle-metrica'>"
                    f"<span class='metrica-label'>RAM:</span>"
                    f"<span class='metrica-valor'>{ram}%</span></div>"
                    f"<div class='detalle-metrica'>"
                    f"<span class='metrica-label'>Disco:</span>"
                    f"<span class='metrica-valor'>{disco}%</span></div>"
                )
                if temp:
                    detalle += (
                        '<div class="detalle-metrica">'
                        f'<span class="metrica-label">Temp. CPU:</span>'
                        f'<span class="metrica-valor">{temp}°C</span></div>'
                    )
            else:
                detalle = '<div class="detalle-metrica"><span class="metrica-label">Sin reportes</span></div>'

            filas_html += (
                '<tr>'
                f'<td class="celda-id"><a href="/detalle?id={id_equipo}" style="color:#3b82f6; text-decoration:underline;">{id_equipo}</a></td>'
                f'<td>{org}</td>'
                f'<td>{sede}</td>'
                f'<td>{area}</td>'
                f'<td><span class="badge {badge_clase}">{estado.upper()}</span></td>'
                f'<td>{ultima if ultima else "—"}</td>'
                f'<td>{detalle}</td>'
                '<td class="celda-acciones">'
                f'<button class="btn-eliminar" onclick="eliminarEquipo(\'{id_equipo}\')" title="Eliminar equipo">🗑️</button>'
                '</td>'
                '</tr>'
            )

        ahora_str = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
        buscar_valor = params.get("buscar", [None])[0] or ""

        html = self._generar_html_principal(
            equipos, filas_html, ahora_str, buscar_valor,
            ok, atencion, accion, aprendizaje, desconocido, total
        )
        self._enviar_respuesta(200, html)

    def _generar_html_principal(self, equipos, filas_html, ahora_str, buscar_valor,
                                ok, atencion, accion, aprendizaje, desconocido, total):
        """Genera el HTML completo del panel principal."""
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SaludPC Enterprise — Panel de TI</title>
<style>
    :root {{
        --fondo: #0E0F13;
        --fondo-tarjeta: #191A20;
        --texto: #F2F4F7;
        --suave: #98A2B3;
        --borde: #272832;
        --ok: #12805C;
        --ok-fondo: #E7F5EE;
        --atencion: #B54708;
        --atencion-fondo: #FEF3DD;
        --accion: #B42318;
        --accion-fondo: #FDE8E6;
        --aprendizaje: #475467;
        --aprendizaje-fondo: #EEF1F5;
        --azul: #3b82f6;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: var(--fondo);
        color: var(--texto);
        min-height: 100vh;
        padding: 24px;
    }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    header {{
        background: transparent;
        padding: 0 0 30px 0;
        margin-bottom: 30px;
    }}
    .header-content {{ display: flex; align-items: center; gap: 16px; }}
    .logo {{
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, var(--azul), #1d4ed8);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 18px;
        color: white;
    }}
    h1 {{
        font-size: 24px;
        font-weight: 700;
        color: var(--texto);
        letter-spacing: -0.5px;
    }}
    .subtitulo {{
        font-size: 14px;
        color: var(--suave);
        margin-top: 4px;
    }}
    .barra-acciones {{
        display: flex;
        gap: 12px;
        margin-bottom: 24px;
        flex-wrap: wrap;
        align-items: center;
    }}
    .btn-actualizar {{
        background: var(--azul);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .btn-actualizar:hover {{ background: #2563eb; }}
    .btn-actualizar:active {{ background: #1e4ed8; }}
    .btn-eliminar {{
        background: #ef4444;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 12px;
        cursor: pointer;
        margin-left: 8px;
        transition: background 0.2s;
    }}
    .btn-eliminar:hover {{ background: #dc2626; }}
    .resumen-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px;
        margin-bottom: 30px;
    }}
    .tarjeta-resumen {{
        background: var(--fondo-tarjeta);
        border: 1px solid var(--borde);
        border-radius: 16px;
        padding: 20px;
        display: flex;
        align-items: center;
        gap: 16px;
        transition: transform 0.2s, border-color 0.2s;
    }}
    .tarjeta-resumen:hover {{
        transform: translateY(-2px);
        border-color: #3E434A;
    }}
    .tarjeta-icono {{
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
    }}
    .tarjeta-ok .tarjeta-icono {{ background: var(--ok-fondo); color: var(--ok); }}
    .tarjeta-atencion .tarjeta-icono {{ background: var(--atencion-fondo); color: var(--atencion); }}
    .tarjeta-accion .tarjeta-icono {{ background: var(--accion-fondo); color: var(--accion); }}
    .tarjeta-aprendizaje .tarjeta-icono {{ background: var(--aprendizaje-fondo); color: var(--aprendizaje); }}
    .tarjeta-desconocido .tarjeta-icono {{ background: #3E434A; color: #98A2B3; }}
    .tarjeta-contenido h3 {{
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--suave);
        margin-bottom: 4px;
    }}
    .tarjeta-contenido .numero {{
        font-size: 32px;
        font-weight: 800;
        color: var(--texto);
    }}
    table {{
        width: 100%;
        background: var(--fondo-tarjeta);
        border: 1px solid var(--borde);
        border-radius: 16px;
        overflow: hidden;
        margin-bottom: 30px;
    }}
    th {{
        background: #141519;
        color: var(--suave);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
        padding: 16px 20px;
        text-align: left;
        border-bottom: 1px solid var(--borde);
    }}
    td {{
        padding: 16px 20px;
        border-bottom: 1px solid var(--borde);
        font-size: 14px;
        color: var(--texto);
        vertical-align: middle;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: #141519; }}
    .celda-id {{
        font-weight: 700;
        color: var(--texto);
        font-family: 'Courier New', monospace;
        font-size: 13px;
    }}
    .celda-acciones {{ text-align: center; }}
    .badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        white-space: nowrap;
    }}
    .badge-ok {{ background: var(--ok-fondo); color: var(--ok); border: 1px solid rgba(18, 128, 92, 0.3); }}
    .badge-atencion {{ background: var(--atencion-fondo); color: var(--atencion); border: 1px solid rgba(181, 71, 8, 0.3); }}
    .badge-accion {{ background: var(--accion-fondo); color: var(--accion); border: 1px solid rgba(180, 35, 24, 0.3); }}
    .badge-aprendizaje {{ background: var(--aprendizaje-fondo); color: var(--aprendizaje); border: 1px solid rgba(71, 84, 103, 0.3); }}
    .badge-desconocido {{ background: #3E434A; color: #98A2B3; border: 1px solid #5B6068; }}
    .detalle-metrica {{
        font-size: 12px;
        margin-bottom: 4px;
        color: #CBD5E1;
    }}
    .detalle-metrica .metrica-label {{ color: #64748B; margin-right: 6px; }}
    .detalle-metrica .metrica-valor {{ color: #F8FAFC; font-weight: 600; }}
    .footer {{
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid var(--borde);
        color: #64748B;
        font-size: 12px;
        text-align: center;
    }}
    .refresh-hint {{
        font-size: 12px;
        color: #64748B;
        margin-bottom: 10px;
        text-align: right;
    }}
    .mensaje-temporal {{
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        z-index: 1000;
        display: none;
    }}
    .mensaje-temporal.exito {{ background: var(--ok); }}
    .mensaje-temporal.error {{ background: var(--accion); }}
</style>
</head>
<body>
<div class="container">
    <header>
        <div class="header-content">
            <div class="logo">SP</div>
            <div>
                <h1>SaludPC Enterprise</h1>
                <div class="subtitulo">Panel de Monitoreo de TI — Edición Empresarial</div>
            </div>
        </div>
        <div class="barra-acciones">
            <div class="buscador">
                <input type="text" id="buscarInput" placeholder="Buscar equipo, organización, sede o área..." value="{buscar_valor}" style="width:100%; padding:10px 15px; border-radius:8px; border:1px solid var(--borde); background:var(--fondo-tarjeta); color:var(--texto); font-size:14px;">
            </div>
            <button class="btn-buscar" onclick="buscarEquipos()">🔍 Buscar</button>
            <button class="btn-actualizar" onclick="refrescarPanel()">↻ Actualizar</button>
        </div>
    </header>

    <div id="mensajeTemporal" class="mensaje-temporal"></div>

    <div class="refresh-hint">Última actualización: {ahora_str} UTC | Total equipos: {total}</div>

    <div class="resumen-grid">
        <div class="tarjeta-resumen tarjeta-ok">
            <div class="tarjeta-icono">✓</div>
            <div class="tarjeta-contenido">
                <h3>Equipos Normales</h3>
                <div class="numero">{ok}</div>
            </div>
        </div>
        <div class="tarjeta-resumen tarjeta-atencion">
            <div class="tarjeta-icono">⚠</div>
            <div class="tarjeta-contenido">
                <h3>Atención</h3>
                <div class="numero">{atencion}</div>
            </div>
        </div>
        <div class="tarjeta-resumen tarjeta-accion">
            <div class="tarjeta-icono">!</div>
            <div class="tarjeta-contenido">
                <h3>Requiere Acción</h3>
                <div class="numero">{accion}</div>
            </div>
        </div>
        <div class="tarjeta-resumen tarjeta-aprendizaje">
            <div class="tarjeta-icono">📚</div>
            <div class="tarjeta-contenido">
                <h3>En Aprendizaje</h3>
                <div class="numero">{aprendizaje}</div>
            </div>
        </div>
        <div class="tarjeta-resumen tarjeta-desconocido">
            <div class="tarjeta-icono">⚪</div>
            <div class="tarjeta-contenido">
                <h3>Sin Reportar</h3>
                <div class="numero">{desconocido}</div>
            </div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>ID Equipo</th>
                <th>Organización</th>
                <th>Sede</th>
                <th>Área</th>
                <th>Estado</th>
                <th>Última Conexión</th>
                <th>Métricas</th>
                <th>Acciones</th>
            </tr>
        </thead>
        <tbody id="cuerpoTabla">{filas_html}</tbody>
    </table>

    <div class="footer">
        SaludPC Enterprise v1.0 · Edición Empresarial · Datos locales · Sin envío de información personal
    </div>
</div>

<script>
function mostrarMensaje(texto, tipo) {{
    var el = document.getElementById('mensajeTemporal');
    el.textContent = texto;
    el.className = 'mensaje-temporal ' + tipo;
    el.style.display = 'block';
    setTimeout(function() {{ el.style.display = 'none'; }}, 3000);
}}

function refrescarPanel() {{
    fetch('/equipos')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{ location.reload(); }})
        .catch(function(err) {{ mostrarMensaje('Error al actualizar: ' + err, 'error'); }});
}}

function buscarEquipos() {{
    var input = document.getElementById('buscarInput');
    var valor = input.value.trim();
    var url = '/';
    if (valor) {{
        url += '?buscar=' + encodeURIComponent(valor);
    }}
    window.location.href = url;
}}

function eliminarEquipo(idEquipo) {{
    if(!confirm('¿Está seguro de eliminar el equipo ' + idEquipo + '?')) return;
    fetch('/eliminar', {{
        method: 'DELETE',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ id_equipo: idEquipo }})
    }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
        if(data.ok) {{
            mostrarMensaje('Equipo eliminado correctamente', 'exito');
            setTimeout(function() {{ location.reload(); }}, 500);
        }} else {{
            mostrarMensaje(data.error || 'Error al eliminar', 'error');
        }}
    }})
    .catch(function(err) {{ mostrarMensaje('Error de conexión: ' + err, 'error'); }});
}}

// Auto-refresco cada 30 segundos
setInterval(function() {{
    fetch('/equipos')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{ location.reload(); }})
        .catch(function() {{}});
}}, 30000);
</script>
</body>
</html>"""
        cuerpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _pagina_detalle(self, id_equipo):
        """Página de detalle de un equipo con historial de reportes."""
        equipos = listar_equipos()
        equipo_encontrado = None
        for e in equipos:
            if e[0] == id_equipo:
                equipo_encontrado = e
                break

        if not equipo_encontrado:
            self._enviar_json(404, {"error": f"Equipo '{id_equipo}' no encontrado"})
            return

        historial = obtener_historial_equipo(id_equipo, 50)

        filas_historial = ""
        if historial:
            for fila in historial:
                ts, est, cpu, ram, disco, temp = fila
                filas_historial += (
                    '<tr>'
                    f'<td>{ts}</td>'
                    f'<td>{est}</td>'
                    f'<td>{cpu if cpu is not None else "—"}%</td>'
                    f'<td>{ram if ram is not None else "—"}%</td>'
                    f'<td>{disco if disco is not None else "—"}%</td>'
                    f'<td>{temp if temp is not None else "—"}°C</td>'
                    '</tr>'
                )
        else:
            filas_historial = '<tr><td colspan="6" style="text-align:center; color:var(--suave);">Sin reportes disponibles</td></tr>'

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SaludPC Enterprise — Detalle: {id_equipo}</title>
<style>
    :root {{
        --fondo: #0E0F13;
        --fondo-tarjeta: #191A20;
        --texto: #F2F4F7;
        --suave: #98A2B3;
        --borde: #272832;
        --ok: #12805C;
        --ok-fondo: #E7F5EE;
        --atencion: #B54708;
        --atencion-fondo: #FEF3DD;
        --accion: #B42318;
        --accion-fondo: #FDE8E6;
        --aprendizaje: #475467;
        --aprendizaje-fondo: #EEF1F5;
        --azul: #3b82f6;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: var(--fondo);
        color: var(--texto);
        min-height: 100vh;
        padding: 24px;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
        padding: 0 0 30px 0;
        margin-bottom: 30px;
    }}
    .btn-volver {{
        background: var(--azul);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 24px;
    }}
    .btn-volver:hover {{ background: #2563eb; }}
    .tarjeta-info {{
        background: var(--fondo-tarjeta);
        border: 1px solid var(--borde);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 24px;
    }}
    .tarjeta-info h2 {{
        font-size: 20px;
        font-weight: 700;
        color: var(--texto);
        margin-bottom: 16px;
    }}
    .info-row {{
        display: flex;
        gap: 30px;
        margin-bottom: 10px;
    }}
    .info-item {{
        font-size: 14px;
        color: var(--texto);
    }}
    .info-item strong {{
        color: var(--suave);
    }}
    table {{
        width: 100%;
        background: var(--fondo-tarjeta);
        border: 1px solid var(--borde);
        border-radius: 16px;
        overflow: hidden;
    }}
    th {{
        background: #141519;
        color: var(--suave);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
        padding: 16px 20px;
        text-align: left;
        border-bottom: 1px solid var(--borde);
    }}
    td {{
        padding: 16px 20px;
        border-bottom: 1px solid var(--borde);
        font-size: 14px;
        color: var(--texto);
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: #141519; }}
    .badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        white-space: nowrap;
    }}
    .badge-ok {{ background: var(--ok-fondo); color: var(--ok); }}
    .badge-atencion {{ background: var(--atencion-fondo); color: var(--atencion); }}
    .badge-accion {{ background: var(--accion-fondo); color: var(--accion); }}
    .badge-aprendizaje {{ background: var(--aprendizaje-fondo); color: var(--aprendizaje); }}
    .badge-desconocido {{ background: #3E434A; color: #98A2B3; }}
    .footer {{
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid var(--borde);
        color: #64748B;
        font-size: 12px;
        text-align: center;
    }}
</style>
</head>
<body>
<div class="container">
    <header>
        <a href="/" class="btn-volver">← Volver al panel</a>
        <h2>Detalle: {id_equipo}</h2>
    </header>

    <div class="tarjeta-info">
        <div class="info-row"><strong>ID:</strong> <span>{id_equipo}</span> <strong>Organización:</strong> <span>{equipo_encontrado[1]}</span></div>
        <div class="info-row"><strong>Sede:</strong> <span>{equipo_encontrado[2]}</span> <strong>Área:</strong> <span>{equipo_encontrado[3]}</span></div>
        <div class="info-row"><strong>Inscripción:</strong> <span>{equipo_encontrado[4]}</span> <strong>Última conexión:</strong> <span>{equipo_encontrado[5] if equipo_encontrado[5] else '—'}</span></div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Fecha y Hora</th>
                <th>Estado</th>
                <th>CPU</th>
                <th>RAM</th>
                <th>Disco</th>
                <th>Temp. CPU</th>
            </tr>
        </thead>
        <tbody>{filas_historial}</tbody>
    </table>

    <div class="footer">
        SaludPC Enterprise v1.0 · Edición Empresarial · Detalle de equipo
    </div>
</div>
</body>
</html>"""
        cuerpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _api_equipos(self, params):
        """Devuelve JSON con la lista de equipos."""
        filtro_busqueda = params.get("buscar", [None])[0]
        equipos = listar_equipos(filtro_busqueda)
        resultado = []
        for equipo in equipos:
            id_equipo, org, sede, area, fecha_ins, ultima, estado = equipo
            resultado.append({
                "id_equipo": id_equipo,
                "organizacion": org,
                "sede": sede,
                "area": area,
                "estado": estado,
                "ultima_conexion": ultima,
            })
        self._enviar_json(200, resultado)


def main():
    """Punto de entrada del servidor."""
    crear_base()
    ThreadingHTTPServer.allow_reuse_address = True
    servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), ManejadorSaludPC)

    # Soporte opcional HTTPS mediante variables de entorno.
    cert_file = os.environ.get("SALUDP_SSL_CERT")
    key_file = os.environ.get("SALUDP_SSL_KEY")
    if cert_file and key_file:
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.load_cert_chain(cert_file, key_file)
        servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
        esquema = "https"
        log.info("TLS habilitado con certificado %s", cert_file)
    else:
        esquema = "http"
        log.warning(
            "TLS no habilitado (defina SALUDP_SSL_CERT y SALUDP_SSL_KEY). "
            "El tráfico irá en texto plano."
        )

    log.info("Servidor central SaludPC escuchando en puerto %d", PUERTO)
    log.info("Panel de TI: %s://localhost:%d/", esquema, PUERTO)
    print(f"Servidor SaludPC iniciado en puerto {PUERTO}")
    print(f"Panel de TI: {esquema}://localhost:{PUERTO}/")
    print("Presiona Ctrl+C para detener")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log.info("Servidor detenido")
        servidor.server_close()


if __name__ == "__main__":
    main()
