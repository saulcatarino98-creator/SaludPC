"""SaludPC Servidor Central - Versión Estable"""

import ctypes
import hashlib
import hmac
import html as _html
import json
import logging
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Configuración
PUERTO = int(os.environ.get("SALUDP_PUERTO", "8443"))
CLAVE_HMAC_ORG = os.environ.get("SALUDP_ORG_KEY", "clave-organizacion-cambiar-en-produccion")


def _directorios_candidatos():
    """Devuelve las carpetas donde puede vivir la base de datos, en orden de preferencia."""
    if os.environ.get("SALUD_PC_DATOS"):
        return [Path(os.environ["SALUD_PC_DATOS"])]
    programa = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    return [
        programa / "SaludPC" / "Servidor",
        programa / "SaludPC",
        programa / "SaludPC" / "SaludPC",
    ]


def _elegir_directorio_datos():
    """Reutiliza la base existente si ya hay una; si no, usa ProgramData\\SaludPC\\Servidor."""
    candidatos = _directorios_candidatos()
    for carpeta in candidatos:
        if (carpeta / "servidor_central.db").exists():
            return carpeta
    return candidatos[0]


RUTA_DATOS = _elegir_directorio_datos()
RUTA_DB = str(RUTA_DATOS / "servidor_central.db")
RUTA_LOG = RUTA_DATOS / "servidor.log"

VERSION_SERVIDOR = "1.0.3"

ETIQUETAS_ESTADO = {
    "ok": "Normal",
    "atencion": "Atención",
    "accion": "Requiere acción",
    "en_aprendizaje": "En aprendizaje",
    "desconocido": "Sin reportar",
}

ESTADOS_FILTRO = [
    ("", "Todos los estados"),
    ("ok", "Normal"),
    ("atencion", "Atención"),
    ("accion", "Requiere acción"),
    ("en_aprendizaje", "En aprendizaje"),
    ("desconocido", "Sin reportar"),
]

CSS_INFORME = """
    :root { --texto:#1f2937; --suave:#6b7280; --borde:#e5e7eb; --ok:#047857; --atencion:#b45309; --accion:#b91c1c; --aprendizaje:#475467; }
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', Arial, sans-serif; color: var(--texto); background:#fff; margin:0; padding:30px; }
    .container { max-width: 1200px; margin: 0 auto; }
    .barra { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px; }
    .btn { background:#1d4ed8; color:#fff; border:none; padding:10px 18px; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; text-decoration:none; display:inline-block; }
    .btn:hover { background:#1e40af; }
    .btn-sec { background:#fff; color:#1f2937; border:1px solid var(--borde); }
    .btn-sec:hover { background:#f3f4f6; }
    header { border-bottom:2px solid #111827; padding-bottom:16px; margin-bottom:24px; }
    h1 { font-size:26px; margin:0 0 6px 0; }
    .sub { color:var(--suave); font-size:13px; }
    .resumen { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin:20px 0 26px 0; }
    .dato { border:1px solid var(--borde); border-radius:12px; padding:14px 16px; }
    .dato .n { font-size:26px; font-weight:800; }
    .dato .e { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--suave); }
    .ficha { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:10px 24px; border:1px solid var(--borde); border-radius:12px; padding:18px; margin-bottom:24px; font-size:14px; }
    .ficha strong { color:var(--suave); font-weight:600; }
    table { width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }
    th { background:#f9fafb; border-bottom:2px solid var(--borde); padding:10px 8px; text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--suave); }
    td { border-bottom:1px solid var(--borde); padding:9px 8px; }
    tr:nth-child(even) td { background:#fcfcfd; }
    .badge { display:inline-block; padding:3px 9px; border-radius:20px; font-size:11px; font-weight:700; text-transform:uppercase; }
    .b-ok { background:#ecfdf5; color:var(--ok); }
    .b-atencion { background:#fffbeb; color:var(--atencion); }
    .b-accion { background:#fef2f2; color:var(--accion); }
    .b-aprendizaje { background:#f1f5f9; color:var(--aprendizaje); }
    .b-desconocido { background:#f3f4f6; color:#6b7280; }
    .nota { color:var(--suave); font-size:12px; margin-top:14px; }
    footer { margin-top:32px; padding-top:14px; border-top:1px solid var(--borde); color:var(--suave); font-size:11px; text-align:center; }
    @media print {
        body { padding:0; }
        .barra { display:none; }
        .container { max-width:none; }
        table { font-size:11px; }
        tr { page-break-inside: avoid; }
    }
"""


def configurar_log():
    """Registra en archivo y consola; nunca falla por permisos."""
    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    registro = logging.getLogger("salud.servidor")
    registro.setLevel(logging.INFO)
    registro.handlers.clear()
    try:
        os.makedirs(RUTA_DATOS, exist_ok=True)
        manejador = RotatingFileHandler(
            RUTA_LOG, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        manejador.setFormatter(formato)
        registro.addHandler(manejador)
    except OSError:
        pass
    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    registro.addHandler(consola)
    return registro


log = configurar_log()


def mostrar_error(titulo, mensaje):
    """Muestra el error en consola, en el log y en un cuadro de diálogo."""
    log.error("%s: %s", titulo, mensaje)
    try:
        ctypes.windll.user32.MessageBoxW(None, str(mensaje), str(titulo), 0x10)
    except Exception:
        pass


_MUTEX = None


def ya_hay_instancia():
    """Evita que dos servidores escuchen en el mismo puerto."""
    global _MUTEX
    try:
        _MUTEX = ctypes.windll.kernel32.CreateMutexW(
            None, False, f"Local\\SaludPC-Servidor-Central-{PUERTO}"
        )
        return ctypes.windll.kernel32.GetLastError() == 183
    except Exception:
        return False

def crear_base():
    os.makedirs(os.path.dirname(RUTA_DB), exist_ok=True)
    conexion = sqlite3.connect(RUTA_DB)
    try:
        conexion.executescript("""
            CREATE TABLE IF NOT EXISTS equipos (
                id_equipo TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                organizacion TEXT NOT NULL,
                sede TEXT,
                area TEXT,
                fecha_inscripcion TEXT NOT NULL,
                ultima_conexion TEXT,
                estado TEXT DEFAULT 'en_aprendizaje'
            );
            CREATE TABLE IF NOT EXISTS reportes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_equipo TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                fecha_local TEXT,
                estado TEXT,
                cpu_load REAL,
                ram_load REAL,
                disk_used_pct REAL,
                cpu_temp REAL,
                firma_hmac TEXT NOT NULL,
                datos_json TEXT,
                FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
            );
            CREATE TABLE IF NOT EXISTS avisos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_equipo TEXT NOT NULL,
                estado TEXT NOT NULL,
                mensaje TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
            );
        """)
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(reportes)")}
        if "fecha_local" not in columnas:
            conexion.execute("ALTER TABLE reportes ADD COLUMN fecha_local TEXT")
        conexion.commit()
    finally:
        conexion.close()

def generar_token(id_equipo):
    material = f"{id_equipo}|{CLAVE_HMAC_ORG}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]

def registrar_equipo(id_equipo, organizacion, sede, area):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        token = generar_token(id_equipo)
        ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conexion.execute(
            "INSERT OR REPLACE INTO equipos (id_equipo, token, organizacion, sede, area, fecha_inscripcion, estado) VALUES (?, ?, ?, ?, ?, ?, 'en_aprendizaje')",
            (id_equipo, token, organizacion, sede, area, ahora),
        )
        conexion.commit()
        return token
    finally:
        conexion.close()

def obtener_token(id_equipo):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute("SELECT token FROM equipos WHERE id_equipo = ?", (id_equipo,)).fetchone()
        return fila[0] if fila else None
    finally:
        conexion.close()

def verificar_firma(datos_json, firma_recibida, token_equipo):
    esperado = hmac.new(token_equipo.encode("utf-8"), datos_json.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma_recibida)

def estado_equipo_visible(muestras, dias, estado_reporte):
    """Mientras el equipo aprende, el estado visible es en_aprendizaje."""
    if muestras < MUESTRAS_APRENDIZAJE or dias < DIAS_APRENDIZAJE:
        return "en_aprendizaje"
    return estado_reporte or "desconocido"


def guardar_reporte(id_equipo, datos, firma_hmac):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        fecha_local = datos.get("fecha_local") or ahora[:10]
        conexion.execute(
            "INSERT INTO reportes (id_equipo, timestamp, fecha_local, estado, cpu_load, ram_load, disk_used_pct, cpu_temp, firma_hmac, datos_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                id_equipo,
                ahora,
                fecha_local,
                datos.get("estado"),
                datos.get("cpu_load"),
                datos.get("ram_load"),
                datos.get("disk_used_pct"),
                datos.get("cpu_temp"),
                firma_hmac,
                json.dumps(datos, ensure_ascii=False),
            ),
        )
        muestras, dias = conexion.execute(
            """
            SELECT COUNT(*),
                   COUNT(DISTINCT COALESCE(fecha_local, substr(timestamp, 1, 10)))
            FROM reportes
            WHERE id_equipo = ?
            """,
            (id_equipo,),
        ).fetchone()
        estado_equipo = estado_equipo_visible(
            muestras, dias, datos.get("estado")
        )
        conexion.execute(
            "UPDATE equipos SET ultima_conexion = ?, estado = ? WHERE id_equipo = ?",
            (ahora, estado_equipo, id_equipo),
        )
        conexion.commit()
        return True
    except Exception as e:
        log.error(f"Error guardando reporte: {e}")
        return False
    finally:
        conexion.close()


MUESTRAS_APRENDIZAJE = 300
DIAS_APRENDIZAJE = 3


def obtener_progreso(id_equipo):
    """Devuelve el avance de aprendizaje de un equipo según sus reportes."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute(
            """
            SELECT COUNT(*),
                   COUNT(DISTINCT COALESCE(fecha_local, substr(timestamp, 1, 10))),
                   MAX(timestamp)
            FROM reportes
            WHERE id_equipo = ?
            """,
            (id_equipo,),
        ).fetchone()
    finally:
        conexion.close()

    muestras = int(fila[0] or 0)
    dias = int(fila[1] or 0)
    ultima = fila[2]

    avance = min(muestras / MUESTRAS_APRENDIZAJE, dias / DIAS_APRENDIZAJE)
    progreso = max(0, min(100, int(round(avance * 100))))
    completo = muestras >= MUESTRAS_APRENDIZAJE and dias >= DIAS_APRENDIZAJE

    return {
        "ok": True,
        "id_equipo": id_equipo,
        "muestras": muestras,
        "dias": dias,
        "muestras_objetivo": MUESTRAS_APRENDIZAJE,
        "dias_objetivo": DIAS_APRENDIZAJE,
        "progreso": progreso,
        "aprendizaje_completo": completo,
        "ultima_conexion": ultima,
    }

def listar_equipos(filtro_busqueda=None, filtro_estado=None):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        consulta = """
            SELECT e.id_equipo, e.organizacion, e.sede, e.area,
                   e.fecha_inscripcion, e.ultima_conexion,
                   CASE
                       WHEN COUNT(r.id) < ?
                        OR COUNT(DISTINCT COALESCE(r.fecha_local, substr(r.timestamp, 1, 10))) < ?
                       THEN 'en_aprendizaje'
                       ELSE COALESCE(e.estado, 'desconocido')
                   END AS estado_visible
            FROM equipos e
            LEFT JOIN reportes r ON r.id_equipo = e.id_equipo
        """
        parametros = [MUESTRAS_APRENDIZAJE, DIAS_APRENDIZAJE]
        if filtro_busqueda:
            filtro = f"%{filtro_busqueda}%"
            consulta += (
                " WHERE e.id_equipo LIKE ? OR e.organizacion LIKE ?"
                " OR e.sede LIKE ? OR e.area LIKE ?"
            )
            parametros.extend([filtro, filtro, filtro, filtro])
        consulta += " GROUP BY e.id_equipo ORDER BY e.fecha_inscripcion DESC"
        filas = conexion.execute(consulta, parametros).fetchall()
        if filtro_estado:
            filas = [
                fila for fila in filas
                if (fila[6] if len(fila) > 6 else "desconocido") == filtro_estado
            ]
        return filas
    finally:
        conexion.close()


def obtener_historial_completo(id_equipo, limite=None):
    """Historial con fecha local, en orden cronológico. limite=None devuelve todo."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        consulta = (
            "SELECT timestamp, fecha_local, estado, cpu_load, ram_load, "
            "disk_used_pct, cpu_temp FROM reportes WHERE id_equipo = ? "
        )
        parametros = [id_equipo]
        if limite:
            consulta += "ORDER BY timestamp DESC LIMIT ?"
            parametros.append(limite)
        else:
            consulta += "ORDER BY timestamp ASC"
        filas = conexion.execute(consulta, parametros).fetchall()
        if limite:
            filas.reverse()
        return filas
    finally:
        conexion.close()


def obtener_resumen_equipo(id_equipo):
    """Totales y promedios/máximos de todos los reportes de un equipo."""
    conexion = sqlite3.connect(RUTA_DB)
    try:
        return conexion.execute(
            "SELECT COUNT(*), MIN(timestamp), MAX(timestamp), "
            "AVG(cpu_load), MAX(cpu_load), AVG(ram_load), MAX(ram_load), "
            "AVG(disk_used_pct), MAX(disk_used_pct) "
            "FROM reportes WHERE id_equipo = ?",
            (id_equipo,),
        ).fetchone()
    finally:
        conexion.close()


def _texto(valor):
    """Escapa texto para insertarlo en HTML."""
    if valor is None:
        return ""
    return _html.escape(str(valor))


def _csv_campo(valor):
    """Prepara un campo CSV con separador punto y coma."""
    if valor is None:
        return ""
    texto = str(valor).replace('"', '""')
    if any(caracter in texto for caracter in ';"\n\r'):
        return f'"{texto}"'
    return texto


def _badge_estado(estado):
    clase = "b-desconocido"
    if estado == "ok":
        clase = "b-ok"
    elif estado == "atencion":
        clase = "b-atencion"
    elif estado == "accion":
        clase = "b-accion"
    elif estado == "en_aprendizaje":
        clase = "b-aprendizaje"
    etiqueta = ETIQUETAS_ESTADO.get(estado, estado or "Sin reportar")
    return f'<span class="badge {clase}">{_texto(etiqueta)}</span>'


def _numero(valor, sufijo=""):
    if valor is None:
        return "—"
    try:
        return f"{float(valor):.1f}{sufijo}"
    except (TypeError, ValueError):
        return _texto(valor)


def obtener_ultimo_reporte(id_equipo):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute("SELECT timestamp, estado, cpu_load, ram_load, disk_used_pct, cpu_temp FROM reportes WHERE id_equipo = ? ORDER BY timestamp DESC LIMIT 1", (id_equipo,)).fetchone()
        return fila
    finally:
        conexion.close()

def obtener_historial_equipo(id_equipo, limite=50):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        filas = conexion.execute("SELECT timestamp, estado, cpu_load, ram_load, disk_used_pct, cpu_temp FROM reportes WHERE id_equipo = ? ORDER BY timestamp DESC LIMIT ?", (id_equipo, limite)).fetchall()
        return filas
    finally:
        conexion.close()

def eliminar_equipo(id_equipo):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute("SELECT id_equipo FROM equipos WHERE id_equipo = ?", (id_equipo,)).fetchone()
        if fila is None:
            return False, "no_encontrado"
        conexion.execute("DELETE FROM reportes WHERE id_equipo = ?", (id_equipo,))
        conexion.execute("DELETE FROM avisos WHERE id_equipo = ?", (id_equipo,))
        conexion.execute("DELETE FROM equipos WHERE id_equipo = ?", (id_equipo,))
        conexion.commit()
        return True, "ok"
    except Exception as e:
        log.error(f"Error eliminando equipo: {e}")
        return False, "error_db"
    finally:
        conexion.close()

class ManejadorSaludPC(BaseHTTPRequestHandler):
    def log_message(self, formato, *args):
        log.info("%s - %s" % (self.address_string(), formato % args))

    def _enviar_json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _leer_cuerpo(self):
        largo = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(largo).decode("utf-8") if largo > 0 else ""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        ruta = urlparse(self.path).path
        cuerpo = self._leer_cuerpo()
        try:
            if ruta == "/inscribir":
                self._ruta_inscribir(cuerpo)
            elif ruta == "/reporte":
                self._ruta_reporte(cuerpo)
            elif ruta == "/aviso":
                self._ruta_aviso(cuerpo)
            elif ruta == "/eliminar":
                self._ruta_eliminar_equipo(cuerpo)
            else:
                self._enviar_json(404, {"error": "ruta no encontrada"})
        except Exception as e:
            log.error(f"Error POST {ruta}: {e}")
            self._enviar_json(500, {"error": str(e)})

    def do_DELETE(self):
        ruta = urlparse(self.path).path
        cuerpo = self._leer_cuerpo()
        if ruta == "/eliminar":
            self._ruta_eliminar_equipo(cuerpo)
        else:
            self._enviar_json(404, {"error": "ruta no encontrada"})

    def do_GET(self):
        ruta = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)
        try:
            if ruta == "/":
                self._pagina_principal(params)
            elif ruta == "/equipos":
                self._api_equipos(params)
            elif ruta == "/progreso":
                self._api_progreso(params)
            elif ruta == "/detalle":
                id_equipo = params.get("id", [None])[0]
                if id_equipo:
                    self._pagina_detalle(id_equipo)
                else:
                    self._enviar_json(400, {"error": "id es requerido"})
            elif ruta == "/informe":
                self._pagina_informe(params)
            else:
                self._enviar_json(404, {"error": "ruta no encontrada"})
        except Exception as e:
            log.error(f"Error GET {ruta}: {e}")
            self._enviar_json(500, {"error": str(e)})

    def _ruta_inscribir(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except:
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
            self._enviar_json(409, {"ok": False, "error": f"El equipo '{id_equipo}' ya está inscrito.", "id_equipo": id_equipo, "token": token_existente})
            return
        try:
            token = registrar_equipo(id_equipo, organizacion, sede, area)
            log.info("Equipo inscrito: %s (%s)", id_equipo, organizacion)
            self._enviar_json(200, {"ok": True, "id_equipo": id_equipo, "token": token, "mensaje": "Equipo inscrito correctamente."})
        except Exception as e:
            log.error(f"Error inscribiendo: {e}")
            self._enviar_json(500, {"error": str(e)})

    def _ruta_eliminar_equipo(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except:
            self._enviar_json(400, {"error": "JSON inválido"})
            return
        id_equipo = datos.get("id_equipo")
        if not id_equipo:
            self._enviar_json(400, {"error": "id_equipo es requerido"})
            return
        exito, motivo = eliminar_equipo(id_equipo)
        if exito:
            log.info("Equipo eliminado: %s", id_equipo)
            self._enviar_json(200, {"ok": True, "id_equipo": id_equipo, "mensaje": "Equipo eliminado correctamente"})
        elif motivo == "no_encontrado":
            self._enviar_json(404, {"error": f"El equipo '{id_equipo}' no está inscrito"})
        else:
            self._enviar_json(500, {"error": "Error de base de datos"})

    def _ruta_reporte(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except:
            self._enviar_json(400, {"error": "JSON inválido"})
            return
        id_equipo = datos.get("id_equipo")
        firma_recibida = datos.get("firma_hmac")
        if not id_equipo or not firma_recibida:
            self._enviar_json(400, {"error": "id_equipo y firma_hmac son requeridos"})
            return
        token = obtener_token(id_equipo)
        if token is None:
            self._enviar_json(403, {"error": "Equipo no inscrito"})
            return
        datos_sin_firma = dict(datos)
        datos_sin_firma.pop("firma_hmac", None)
        cuerpo_sin_firma = json.dumps(datos_sin_firma, ensure_ascii=False)
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
        except:
            self._enviar_json(400, {"error": "JSON inválido"})
            return
        id_equipo = datos.get("id_equipo")
        estado = datos.get("estado")
        mensaje = datos.get("mensaje", "")
        if not id_equipo or not estado:
            self._enviar_json(400, {"error": "id_equipo y estado son requeridos"})
            return
        token = obtener_token(id_equipo)
        if token is None:
            self._enviar_json(403, {"error": "Equipo no inscrito"})
            return
        try:
            conexion = sqlite3.connect(RUTA_DB)
            ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conexion.execute("INSERT INTO avisos (id_equipo, estado, mensaje, timestamp) VALUES (?, ?, ?, ?)", (id_equipo, estado, mensaje, ahora))
            conexion.commit()
            conexion.close()
            log.info("Aviso registrado: %s - %s", id_equipo, estado)
            self._enviar_json(200, {"ok": True, "mensaje": "Aviso recibido"})
        except Exception as e:
            log.error(f"Error guardando aviso: {e}")
            self._enviar_json(500, {"error": str(e)})

    def _pagina_principal(self, params):
        buscar_valor = params.get("buscar", [None])[0] or ""
        estado_filtro = params.get("estado", [None])[0] or ""
        if estado_filtro not in ("ok", "atencion", "accion", "en_aprendizaje", "desconocido"):
            estado_filtro = ""

        todos = listar_equipos(buscar_valor)
        equipos = [
            equipo for equipo in todos
            if not estado_filtro
            or (equipo[6] if len(equipo) > 6 else "desconocido") == estado_filtro
        ]

        estados = {}
        for e in todos:
            estado = e[6] if len(e) > 6 else "desconocido"
            estados[estado] = estados.get(estado, 0) + 1
        total = len(todos)
        ok = estados.get("ok", 0)
        atencion = estados.get("atencion", 0)
        accion = estados.get("accion", 0)
        aprendizaje = estados.get("en_aprendizaje", 0)
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
            if estado == "ok": badge_clase = "badge-ok"
            elif estado == "atencion": badge_clase = "badge-atencion"
            elif estado == "accion": badge_clase = "badge-accion"
            elif estado == "en_aprendizaje": badge_clase = "badge-aprendizaje"

            if ultimo_reporte:
                ts, est, cpu, ram, disco, temp = ultimo_reporte
                detalle = f"""
                <div class="detalle-metrica"><span class="metrica-label">Último reporte:</span> <span class="metrica-valor">{_texto(ts)}</span></div>
                <div class="detalle-metrica"><span class="metrica-label">Estado:</span> <span class="metrica-valor">{_texto(est)}</span></div>
                <div class="detalle-metrica"><span class="metrica-label">CPU:</span> <span class="metrica-valor">{_numero(cpu, '%')}</span></div>
                <div class="detalle-metrica"><span class="metrica-label">RAM:</span> <span class="metrica-valor">{_numero(ram, '%')}</span></div>
                <div class="detalle-metrica"><span class="metrica-label">Disco:</span> <span class="metrica-valor">{_numero(disco, '%')}</span></div>
                """ + (f"<div class='detalle-metrica'><span class='metrica-label'>Temp. CPU:</span> <span class='metrica-valor'>{_numero(temp, '°C')}</span></div>" if temp is not None else "")
            else:
                detalle = '<div class="detalle-metrica"><span class="metrica-label">Sin reportes</span></div>'

            filas_html += f"""
            <tr>
                <td class="celda-id"><a href="/detalle?id={_texto(id_equipo)}" style="color:#3b82f6; text-decoration:underline;">{_texto(id_equipo)}</a></td>
                <td>{_texto(org)}</td><td>{_texto(sede)}</td><td>{_texto(area)}</td>
                <td><span class="badge {badge_clase}">{_texto(estado.upper())}</span></td>
                <td>{_texto(ultima) if ultima else '—'}</td>
                <td>{detalle}</td>
                <td class="celda-acciones"><button class="btn-eliminar" onclick="eliminarEquipo('{_texto(id_equipo)}')" title="Eliminar equipo">🗑️</button></td>
            </tr>
            """

        ahora_str = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
        buscar_valor_html = _texto(buscar_valor)
        opciones_estado_html = "".join(
            f'<option value="{valor}"{" selected" if valor == estado_filtro else ""}>{texto}</option>'
            for valor, texto in ESTADOS_FILTRO
        )
        opciones_equipos_html = "".join(
            f'<option value="{_texto(e[0])}">{_texto(e[0])} — {_texto(e[1])}</option>'
            for e in todos
        ) or '<option value="">No hay equipos inscritos</option>'
        if not filas_html:
            filas_html = '<tr><td colspan="8" style="text-align:center; color:var(--suave); padding:28px;">No hay equipos que coincidan con la búsqueda o el filtro.</td></tr>'

        html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>SaludPC Enterprise — Panel de TI</title>
<style>
    :root {{ --fondo: #0E0F13; --fondo-tarjeta: #191A20; --texto: #F2F4F7; --suave: #98A2B3; --borde: #272832; --ok: #12805C; --ok-fondo: #E7F5EE; --atencion: #B54708; --atencion-fondo: #FEF3DD; --accion: #B42318; --accion-fondo: #FDE8E6; --aprendizaje: #475467; --aprendizaje-fondo: #EEF1F5; --azul: #3b82f6; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--fondo); color: var(--texto); min-height: 100vh; padding: 24px; }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    header {{ padding: 0 0 30px 0; margin-bottom: 30px; }}
    .header-content {{ display: flex; align-items: center; gap: 16px; }}
    .logo {{ width: 48px; height: 48px; background: linear-gradient(135deg, var(--azul), #1d4ed8); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 18px; color: white; }}
    h1 {{ font-size: 24px; font-weight: 700; color: var(--texto); letter-spacing: -0.5px; }}
    .subtitulo {{ font-size: 14px; color: var(--suave); margin-top: 4px; }}
    .barra-acciones {{ display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; align-items: center; }}
    .barra-acciones {{ display: flex; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; align-items: center; justify-content: space-between; }}
    .acciones-derecha {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-left: auto; }}
    .buscador {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .buscador input {{ background: #141519; border: 1px solid var(--borde); color: var(--texto); padding: 10px 14px; border-radius: 8px; font-size: 14px; min-width: 280px; }}
    .buscador input:focus {{ outline: none; border-color: var(--azul); }}
    .buscador select {{ background: #141519; border: 1px solid var(--borde); color: var(--texto); padding: 10px 12px; border-radius: 8px; font-size: 13px; }}
    .btn-buscar {{ background: #334155; color: white; border: none; padding: 10px 16px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }}
    .btn-buscar:hover {{ background: #475569; }}
    .btn-limpiar {{ background: transparent; color: var(--suave); border: 1px solid var(--borde); padding: 10px 14px; border-radius: 8px; font-size: 13px; text-decoration: none; }}
    .btn-limpiar:hover {{ color: var(--texto); border-color: var(--azul); }}
    .btn-reporte {{ background: #0f766e; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.2s; }}
    .btn-reporte:hover {{ background: #0d9488; }}
    .btn-actualizar {{ background: var(--azul); color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.2s; }}
    .btn-actualizar:hover {{ background: #2563eb; }}
    .modal-fondo {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 2000; align-items: center; justify-content: center; padding: 20px; }}
    .modal-fondo.visible {{ display: flex; }}
    .modal {{ background: var(--fondo-tarjeta); border: 1px solid var(--borde); border-radius: 16px; padding: 26px; width: 100%; max-width: 470px; }}
    .modal h2 {{ font-size: 18px; margin-bottom: 18px; }}
    .modal .campo {{ margin-bottom: 16px; }}
    .modal .campo-titulo {{ font-size: 11px; color: var(--suave); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }}
    .modal label.opcion {{ display: flex; gap: 10px; align-items: center; padding: 7px 0; font-size: 14px; cursor: pointer; }}
    .modal select {{ width: 100%; background: #141519; border: 1px solid var(--borde); color: var(--texto); padding: 10px 12px; border-radius: 8px; font-size: 14px; }}
    .modal select:disabled {{ opacity: 0.45; }}
    .modal-acciones {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }}
    .btn-secundario {{ background: transparent; color: var(--suave); border: 1px solid var(--borde); padding: 10px 18px; border-radius: 8px; font-size: 14px; cursor: pointer; }}
    .btn-secundario:hover {{ color: var(--texto); border-color: var(--azul); }}
    .btn-eliminar {{ background: #ef4444; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: background 0.2s; }}
    .btn-eliminar:hover {{ background: #dc2626; }}
    .resumen-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 30px; }}
    .tarjeta-resumen {{ background: var(--fondo-tarjeta); border: 1px solid var(--borde); border-radius: 16px; padding: 20px; display: flex; align-items: center; gap: 16px; }}
    .tarjeta-icono {{ width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; }}
    .tarjeta-ok .tarjeta-icono {{ background: var(--ok-fondo); color: var(--ok); }}
    .tarjeta-atencion .tarjeta-icono {{ background: var(--atencion-fondo); color: var(--atencion); }}
    .tarjeta-accion .tarjeta-icono {{ background: var(--accion-fondo); color: var(--accion); }}
    .tarjeta-aprendizaje .tarjeta-icono {{ background: var(--aprendizaje-fondo); color: var(--aprendizaje); }}
    .tarjeta-desconocido .tarjeta-icono {{ background: #3E434A; color: #98A2B3; }}
    .tarjeta-contenido h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--suave); margin-bottom: 4px; }}
    .tarjeta-contenido .numero {{ font-size: 32px; font-weight: 800; color: var(--texto); }}
    table {{ width: 100%; background: var(--fondo-tarjeta); border: 1px solid var(--borde); border-radius: 16px; overflow: hidden; margin-bottom: 30px; }}
    th {{ background: #141519; color: var(--suave); font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; padding: 16px 20px; text-align: left; border-bottom: 1px solid var(--borde); }}
    td {{ padding: 16px 20px; border-bottom: 1px solid var(--borde); font-size: 14px; color: var(--texto); vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: #141519; }}
    .celda-id {{ font-weight: 700; color: var(--texto); font-family: 'Courier New', monospace; font-size: 13px; }}
    .badge {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap; }}
    .badge-ok {{ background: var(--ok-fondo); color: var(--ok); border: 1px solid rgba(18, 128, 92, 0.3); }}
    .badge-atencion {{ background: var(--atencion-fondo); color: var(--atencion); border: 1px solid rgba(181, 71, 8, 0.3); }}
    .badge-accion {{ background: var(--accion-fondo); color: var(--accion); border: 1px solid rgba(180, 35, 24, 0.3); }}
    .badge-aprendizaje {{ background: var(--aprendizaje-fondo); color: var(--aprendizaje); border: 1px solid rgba(71, 84, 103, 0.3); }}
    .badge-desconocido {{ background: #3E434A; color: #98A2B3; border: 1px solid #5B6068; }}
    .detalle-metrica {{ font-size: 12px; margin-bottom: 4px; color: #CBD5E1; }}
    .detalle-metrica .metrica-label {{ color: #64748B; margin-right: 6px; }}
    .detalle-metrica .metrica-valor {{ color: #F8FAFC; font-weight: 600; }}
    .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--borde); color: #64748B; font-size: 12px; text-align: center; }}
    .refresh-hint {{ font-size: 12px; color: #64748B; margin-bottom: 10px; text-align: right; }}
    .mensaje-temporal {{ position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; color: white; font-weight: 600; z-index: 1000; display: none; }}
    .mensaje-temporal.exito {{ background: var(--ok); }}
    .mensaje-temporal.error {{ background: var(--accion); }}
</style>
</head>
<body>
<div class="container">
    <header>
        <div class="header-content">
            <div class="logo">SP</div>
            <div><h1>SaludPC Enterprise</h1><div class="subtitulo">Panel de Monitoreo de TI — Edición Empresarial</div></div>
        </div>
        <div class="barra-acciones">
            <button class="btn-reporte" onclick="abrirReporte()">📄 Generar reporte</button>
            <div class="acciones-derecha">
                <form class="buscador" onsubmit="event.preventDefault(); buscarEquipos();">
                    <input id="buscarInput" type="text" placeholder="Buscar equipo, organización, sede o área…" value="{buscar_valor_html}">
                    <select id="filtroEstado" title="Filtrar por estado">
                        {opciones_estado_html}
                    </select>
                    <button type="submit" class="btn-buscar">Buscar</button>
                    <a class="btn-limpiar" href="/">Limpiar</a>
                </form>
                <button class="btn-actualizar" onclick="refrescarPanel()">↻ Actualizar</button>
            </div>
        </div>
        <div class="refresh-hint">Última actualización: {ahora_str} UTC · Total de equipos: {total} · Mostrando: {len(equipos)}</div>
    </header>
    <div id="mensajeTemporal" class="mensaje-temporal"></div>
    <div class="resumen-grid">
        <div class="tarjeta-resumen tarjeta-ok"><div class="tarjeta-icono">✓</div><div class="tarjeta-contenido"><h3>Equipos Normales</h3><div class="numero">{ok}</div></div></div>
        <div class="tarjeta-resumen tarjeta-atencion"><div class="tarjeta-icono">⚠</div><div class="tarjeta-contenido"><h3>Atención</h3><div class="numero">{atencion}</div></div></div>
        <div class="tarjeta-resumen tarjeta-accion"><div class="tarjeta-icono">!</div><div class="tarjeta-contenido"><h3>Requiere Acción</h3><div class="numero">{accion}</div></div></div>
        <div class="tarjeta-resumen tarjeta-aprendizaje"><div class="tarjeta-icono">📚</div><div class="tarjeta-contenido"><h3>En Aprendizaje</h3><div class="numero">{aprendizaje}</div></div></div>
        <div class="tarjeta-resumen tarjeta-desconocido"><div class="tarjeta-icono">⚪</div><div class="tarjeta-contenido"><h3>Sin Reportar</h3><div class="numero">{desconocido}</div></div></div>
    </div>
    <table>
        <thead><tr><th>ID Equipo</th><th>Organización</th><th>Sede</th><th>Área</th><th>Estado</th><th>Última Conexión</th><th>Métricas</th><th>Acciones</th></tr></thead>
        <tbody id="cuerpoTabla">{filas_html}</tbody>
    </table>
    <div id="modalReporte" class="modal-fondo">
        <div class="modal">
            <h2>Generar reporte</h2>
            <div class="campo">
                <div class="campo-titulo">¿Qué informe necesitas?</div>
                <label class="opcion"><input type="radio" name="tipoReporte" value="general" checked onchange="actualizarTipoReporte()"> Todas las máquinas</label>
                <label class="opcion"><input type="radio" name="tipoReporte" value="equipo" onchange="actualizarTipoReporte()"> Un equipo específico</label>
            </div>
            <div class="campo">
                <div class="campo-titulo">Equipo</div>
                <select id="selectEquipo" disabled>
                    {opciones_equipos_html}
                </select>
            </div>
            <div class="campo">
                <div class="campo-titulo">Formato</div>
                <select id="formatoReporte">
                    <option value="html">Para imprimir o guardar como PDF</option>
                    <option value="csv">CSV para Excel</option>
                </select>
            </div>
            <div class="modal-acciones">
                <button class="btn-secundario" onclick="cerrarReporte()">Cancelar</button>
                <button class="btn-actualizar" onclick="generarReporte()">Generar</button>
            </div>
        </div>
    </div>
    <div class="footer">SaludPC Enterprise v{VERSION_SERVIDOR} · Edición Empresarial · Datos locales · Sin envío de información personal</div>
</div>
<script>
function mostrarMensaje(texto, tipo) {{
    var el = document.getElementById('mensajeTemporal');
    el.textContent = texto;
    el.className = 'mensaje-temporal ' + tipo;
    el.style.display = 'block';
    setTimeout(function() {{ el.style.display = 'none'; }}, 3000);
}}
function refrescarPanel() {{ fetch('/equipos').then(function(r) {{ return r.json(); }}).then(function(data) {{ location.reload(); }}).catch(function(err) {{ mostrarMensaje('Error al actualizar: ' + err, 'error'); }}); }}
function buscarEquipos() {{
    var input = document.getElementById('buscarInput');
    var select = document.getElementById('filtroEstado');
    var partes = [];
    var valor = input ? input.value.trim() : '';
    if (valor) {{ partes.push('buscar=' + encodeURIComponent(valor)); }}
    if (select && select.value) {{ partes.push('estado=' + encodeURIComponent(select.value)); }}
    window.location.href = partes.length ? '/?' + partes.join('&') : '/';
}}
function abrirReporte() {{
    document.getElementById('modalReporte').classList.add('visible');
    actualizarTipoReporte();
}}
function cerrarReporte() {{
    document.getElementById('modalReporte').classList.remove('visible');
}}
function actualizarTipoReporte() {{
    var elegido = document.querySelector('input[name="tipoReporte"]:checked');
    var tipo = elegido ? elegido.value : 'general';
    var select = document.getElementById('selectEquipo');
    if (select) {{ select.disabled = (tipo !== 'equipo'); }}
}}
function generarReporte() {{
    var elegido = document.querySelector('input[name="tipoReporte"]:checked');
    var tipo = elegido ? elegido.value : 'general';
    var formato = document.getElementById('formatoReporte').value;
    var url = '/informe?tipo=' + tipo + '&formato=' + formato;
    if (tipo === 'equipo') {{
        var id = document.getElementById('selectEquipo').value;
        if (!id) {{
            mostrarMensaje('Selecciona un equipo para el informe', 'error');
            return;
        }}
        url += '&id=' + encodeURIComponent(id);
    }}
    window.open(url, '_blank');
    cerrarReporte();
}}
function eliminarEquipo(idEquipo) {{
    if(!confirm('¿Está seguro de eliminar el equipo ' + idEquipo + '?')) return;
    fetch('/eliminar', {{ method: 'DELETE', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ id_equipo: idEquipo }}) }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
        if(data.ok) {{ mostrarMensaje('Equipo eliminado correctamente', 'exito'); setTimeout(function() {{ location.reload(); }}, 500); }}
        else {{ mostrarMensaje(data.error || 'Error al eliminar', 'error'); }}
    }})
    .catch(function(err) {{ mostrarMensaje('Error de conexión: ' + err, 'error'); }});
}}
var fondoReporte = document.getElementById('modalReporte');
if (fondoReporte) {{
    fondoReporte.addEventListener('click', function(evento) {{
        if (evento.target === fondoReporte) {{ cerrarReporte(); }}
    }});
}}
setInterval(function() {{
    var modal = document.getElementById('modalReporte');
    var activo = document.activeElement;
    if (modal && modal.classList.contains('visible')) return;
    if (activo && (activo.tagName === 'INPUT' || activo.tagName === 'SELECT' || activo.tagName === 'TEXTAREA')) return;
    fetch('/equipos').then(function(r) {{ return r.json(); }}).then(function(data) {{ location.reload(); }}).catch(function() {{}});
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
        progreso = obtener_progreso(id_equipo)
        filas_historial = ""
        if historial:
            for fila in historial:
                ts, est, cpu, ram, disco, temp = fila
                filas_historial += f"<tr><td>{ts}</td><td>{est}</td><td>{cpu if cpu is not None else '—'}%</td><td>{ram if ram is not None else '—'}%</td><td>{disco if disco is not None else '—'}%</td><td>{temp if temp is not None else '—'}°C</td></tr>"
        else:
            filas_historial = '<tr><td colspan="6" style="text-align:center; color:var(--suave);">Sin reportes disponibles</td></tr>'
        html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>SaludPC Enterprise - Detalle: {id_equipo}</title>
<style>
    :root {{ --fondo: #0E0F13; --fondo-tarjeta: #191A20; --texto: #F2F4F7; --suave: #98A2B3; --borde: #272832; --ok: #12805C; --ok-fondo: #E7F5EE; --atencion: #B54708; --atencion-fondo: #FEF3DD; --accion: #B42318; --accion-fondo: #FDE8E6; --aprendizaje: #475467; --aprendizaje-fondo: #EEF1F5; --azul: #3b82f6; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--fondo); color: var(--texto); min-height: 100vh; padding: 24px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{ padding: 0 0 30px 0; margin-bottom: 30px; }}
    .btn-volver {{ background: var(--azul); color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; margin-bottom: 24px; }}
    .btn-volver:hover {{ background: #2563eb; }}
    .tarjeta-info {{ background: var(--fondo-tarjeta); border: 1px solid var(--borde); border-radius: 16px; padding: 20px; margin-bottom: 24px; }}
    .tarjeta-info h2 {{ font-size: 20px; font-weight: 700; color: var(--texto); margin-bottom: 16px; }}
    .info-row {{ display: flex; gap: 30px; margin-bottom: 10px; }}
    .info-item {{ font-size: 14px; color: var(--texto); }}
    .info-item strong {{ color: var(--suave); }}
    table {{ width: 100%; background: var(--fondo-tarjeta); border: 1px solid var(--borde); border-radius: 16px; overflow: hidden; }}
    th {{ background: #141519; color: var(--suave); font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; padding: 16px 20px; text-align: left; border-bottom: 1px solid var(--borde); }}
    td {{ padding: 16px 20px; border-bottom: 1px solid var(--borde); font-size: 14px; color: var(--texto); }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: #141519; }}
    .badge {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap; }}
    .badge-ok {{ background: var(--ok-fondo); color: var(--ok); }}
    .badge-atencion {{ background: var(--atencion-fondo); color: var(--atencion); }}
    .badge-accion {{ background: var(--accion-fondo); color: var(--accion); }}
    .badge-aprendizaje {{ background: var(--aprendizaje-fondo); color: var(--aprendizaje); }}
    .badge-desconocido {{ background: #3E434A; color: #98A2B3; }}
    .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--borde); color: #64748B; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
<div class="container">
    <header>
        <a href="/" class="btn-volver">← Volver al panel</a>
        <a href="/informe?tipo=equipo&amp;id={_texto(id_equipo)}" class="btn-volver" style="background:#0f766e;">📄 Generar informe de este equipo</a>
        <h2>Detalle: {_texto(id_equipo)}</h2>
    </header>
    <div class="tarjeta-info">
        <div class="info-row"><strong>ID:</strong> <span>{_texto(id_equipo)}</span> <strong>Organización:</strong> <span>{_texto(equipo_encontrado[1])}</span></div>
        <div class="info-row"><strong>Sede:</strong> <span>{_texto(equipo_encontrado[2])}</span> <strong>Área:</strong> <span>{_texto(equipo_encontrado[3])}</span></div>
        <div class="info-row"><strong>Inscripción:</strong> <span>{_texto(equipo_encontrado[4])}</span> <strong>Última conexión:</strong> <span>{_texto(equipo_encontrado[5]) if equipo_encontrado[5] else '—'}</span></div>
        <div class="info-row"><strong>Estado:</strong> <span>{_texto(ETIQUETAS_ESTADO.get(equipo_encontrado[6], equipo_encontrado[6]))}</span> <strong>Aprendizaje:</strong> <span>{progreso['muestras']} de {progreso['muestras_objetivo']} muestras · {progreso['dias']} de {progreso['dias_objetivo']} días{'' if progreso['aprendizaje_completo'] else ' (pendiente)'}</span></div>
    </div>
    <table>
        <thead><tr><th>Fecha y Hora</th><th>Estado</th><th>CPU</th><th>RAM</th><th>Disco</th><th>Temp. CPU</th></tr></thead>
        <tbody>{filas_historial}</tbody>
    </table>
    <div class="footer">SaludPC Enterprise v{VERSION_SERVIDOR} · Edición Empresarial · Detalle de equipo</div>
</div>
</body>
</html>"""
        cuerpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _enviar_html(self, html_texto):
        cuerpo = html_texto.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _enviar_csv(self, nombre, texto):
        # BOM para que Excel reconozca los acentos.
        cuerpo = ("\ufeff" + texto).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{nombre}"')
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _pagina_informe(self, params):
        tipo = (params.get("tipo", ["general"])[0] or "general").lower()
        formato = (params.get("formato", ["html"])[0] or "html").lower()
        if tipo not in ("general", "equipo"):
            tipo = "general"
        if formato not in ("html", "csv"):
            formato = "html"

        if tipo == "equipo":
            id_equipo = params.get("id", [None])[0]
            if not id_equipo:
                self._enviar_json(400, {"error": "id es requerido para el informe por equipo"})
                return
            equipo = next((e for e in listar_equipos() if e[0] == id_equipo), None)
            if equipo is None:
                self._enviar_json(404, {"error": f"Equipo '{id_equipo}' no encontrado"})
                return
            if formato == "csv":
                self._informe_equipo_csv(id_equipo)
            else:
                self._informe_equipo_html(id_equipo, equipo)
        else:
            if formato == "csv":
                self._informe_general_csv()
            else:
                self._informe_general_html()

    def _informe_general_html(self):
        equipos = listar_equipos()
        conteo = {}
        filas = ""
        for equipo in equipos:
            id_equipo, org, sede, area, fecha_ins, ultima, estado = equipo
            estado = estado or "desconocido"
            conteo[estado] = conteo.get(estado, 0) + 1
            ultimo = obtener_ultimo_reporte(id_equipo)
            if ultimo:
                ts, est, cpu, ram, disco, temp = ultimo
            else:
                ts = est = cpu = ram = disco = temp = None
            filas += (
                "<tr>"
                f"<td><strong>{_texto(id_equipo)}</strong></td>"
                f"<td>{_texto(org)}</td>"
                f"<td>{_texto(sede)}</td>"
                f"<td>{_texto(area)}</td>"
                f"<td>{_badge_estado(estado)}</td>"
                f"<td>{_texto(ultima) if ultima else '—'}</td>"
                f"<td>{_numero(cpu, '%')}</td>"
                f"<td>{_numero(ram, '%')}</td>"
                f"<td>{_numero(disco, '%')}</td>"
                f"<td>{_numero(temp, '°C')}</td>"
                "</tr>"
            )
        if not equipos:
            filas = '<tr><td colspan="10" style="text-align:center;color:#6b7280;padding:24px;">No hay equipos inscritos.</td></tr>'
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        total = len(equipos)
        html_texto = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Informe general — SaludPC Enterprise</title><style>{CSS_INFORME}</style></head>
<body><div class="container">
<div class="barra">
    <a class="btn btn-sec" href="/">← Volver al panel</a>
    <button class="btn" onclick="window.print()">🖨 Imprimir / Guardar PDF</button>
    <a class="btn btn-sec" href="/informe?tipo=general&amp;formato=csv">⬇ Descargar CSV</a>
</div>
<header>
    <h1>Informe general de equipos</h1>
    <div class="sub">SaludPC Enterprise · Generado el {ahora} · {total} equipo(s)</div>
</header>
<div class="resumen">
    <div class="dato"><div class="n">{total}</div><div class="e">Equipos</div></div>
    <div class="dato"><div class="n">{conteo.get('ok', 0)}</div><div class="e">Normales</div></div>
    <div class="dato"><div class="n">{conteo.get('atencion', 0)}</div><div class="e">Atención</div></div>
    <div class="dato"><div class="n">{conteo.get('accion', 0)}</div><div class="e">Requiere acción</div></div>
    <div class="dato"><div class="n">{conteo.get('en_aprendizaje', 0)}</div><div class="e">En aprendizaje</div></div>
    <div class="dato"><div class="n">{conteo.get('desconocido', 0)}</div><div class="e">Sin reportar</div></div>
</div>
<table>
    <thead><tr><th>ID Equipo</th><th>Organización</th><th>Sede</th><th>Área</th><th>Estado</th><th>Última conexión</th><th>CPU</th><th>RAM</th><th>Disco</th><th>Temp. CPU</th></tr></thead>
    <tbody>{filas}</tbody>
</table>
<p class="nota">El estado «En aprendizaje» significa que el equipo todavía no reunió 300 muestras en 3 fechas locales. Las métricas corresponden al último reporte recibido.</p>
<footer>SaludPC Enterprise v{VERSION_SERVIDOR} · Informe generado automáticamente · Solo datos técnicos, sin información personal ni de pacientes</footer>
</div></body></html>"""
        self._enviar_html(html_texto)

    def _informe_general_csv(self):
        equipos = listar_equipos()
        lineas = [
            "ID;Organización;Sede;Área;Estado;Última conexión;"
            "Fecha del último reporte;CPU (%);RAM (%);Disco (%);Temp. CPU (°C);Muestras;Días"
        ]
        for equipo in equipos:
            id_equipo, org, sede, area, fecha_ins, ultima, estado = equipo
            ultimo = obtener_ultimo_reporte(id_equipo)
            progreso = obtener_progreso(id_equipo)
            if ultimo:
                ts, est, cpu, ram, disco, temp = ultimo
            else:
                ts = est = cpu = ram = disco = temp = None
            valores = [
                id_equipo, org, sede, area, ETIQUETAS_ESTADO.get(estado, estado),
                ultima, ts, cpu, ram, disco, temp,
                progreso["muestras"], progreso["dias"],
            ]
            lineas.append(";".join(_csv_campo(valor) for valor in valores))
        nombre = f"SaludPC_informe_general_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        self._enviar_csv(nombre, "\r\n".join(lineas) + "\r\n")

    def _informe_equipo_html(self, id_equipo, equipo):
        _, org, sede, area, fecha_ins, ultima, estado = equipo
        estado = estado or "desconocido"
        progreso = obtener_progreso(id_equipo)
        total, primero, ultimo_ts, cpu_med, cpu_max, ram_med, ram_max, disco_med, disco_max = obtener_resumen_equipo(id_equipo)
        historial = obtener_historial_completo(id_equipo, limite=500)
        filas = ""
        for ts, fecha_local, est, cpu, ram, disco, temp in historial:
            filas += (
                "<tr>"
                f"<td>{_texto(ts)}</td>"
                f"<td>{_texto(fecha_local) if fecha_local else '—'}</td>"
                f"<td>{_badge_estado(est)}</td>"
                f"<td>{_numero(cpu, '%')}</td>"
                f"<td>{_numero(ram, '%')}</td>"
                f"<td>{_numero(disco, '%')}</td>"
                f"<td>{_numero(temp, '°C')}</td>"
                "</tr>"
            )
        if not historial:
            filas = '<tr><td colspan="7" style="text-align:center;color:#6b7280;padding:24px;">Este equipo todavía no tiene reportes.</td></tr>'
        nota = ""
        if total and total > len(historial):
            nota = f'<p class="nota">Se muestran los últimos {len(historial)} de {total} reportes. El CSV incluye el detalle completo.</p>'
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        aprendizaje = (
            "completo"
            if progreso["aprendizaje_completo"]
            else "pendiente"
        )
        html_texto = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Informe del equipo {_texto(id_equipo)} — SaludPC Enterprise</title><style>{CSS_INFORME}</style></head>
<body><div class="container">
<div class="barra">
    <a class="btn btn-sec" href="/">← Volver al panel</a>
    <a class="btn btn-sec" href="/detalle?id={_texto(id_equipo)}">Ver detalle en el panel</a>
    <button class="btn" onclick="window.print()">🖨 Imprimir / Guardar PDF</button>
    <a class="btn btn-sec" href="/informe?tipo=equipo&amp;id={_texto(id_equipo)}&amp;formato=csv">⬇ Descargar CSV</a>
</div>
<header>
    <h1>Informe del equipo: {_texto(id_equipo)}</h1>
    <div class="sub">SaludPC Enterprise · Generado el {ahora}</div>
</header>
<div class="ficha">
    <div><strong>ID:</strong> {_texto(id_equipo)}</div>
    <div><strong>Organización:</strong> {_texto(org)}</div>
    <div><strong>Sede:</strong> {_texto(sede)}</div>
    <div><strong>Área:</strong> {_texto(area)}</div>
    <div><strong>Inscripción:</strong> {_texto(fecha_ins)}</div>
    <div><strong>Última conexión:</strong> {_texto(ultima) if ultima else '—'}</div>
    <div><strong>Estado actual:</strong> {_texto(ETIQUETAS_ESTADO.get(estado, estado))}</div>
    <div><strong>Aprendizaje:</strong> {progreso['muestras']} de {progreso['muestras_objetivo']} muestras · {progreso['dias']} de {progreso['dias_objetivo']} días ({aprendizaje})</div>
</div>
<div class="resumen">
    <div class="dato"><div class="n">{total}</div><div class="e">Reportes</div></div>
    <div class="dato"><div class="n">{_numero(cpu_med, '%')}</div><div class="e">CPU media</div></div>
    <div class="dato"><div class="n">{_numero(cpu_max, '%')}</div><div class="e">CPU máxima</div></div>
    <div class="dato"><div class="n">{_numero(ram_med, '%')}</div><div class="e">RAM media</div></div>
    <div class="dato"><div class="n">{_numero(ram_max, '%')}</div><div class="e">RAM máxima</div></div>
    <div class="dato"><div class="n">{_numero(disco_med, '%')}</div><div class="e">Disco medio</div></div>
</div>
<div class="ficha">
    <div><strong>Primer reporte:</strong> {_texto(primero) if primero else '—'}</div>
    <div><strong>Último reporte:</strong> {_texto(ultimo_ts) if ultimo_ts else '—'}</div>
</div>
<table>
    <thead><tr><th>Fecha y hora (UTC)</th><th>Fecha local</th><th>Estado</th><th>CPU</th><th>RAM</th><th>Disco</th><th>Temp. CPU</th></tr></thead>
    <tbody>{filas}</tbody>
</table>
{nota}
<footer>SaludPC Enterprise v{VERSION_SERVIDOR} · Informe generado automáticamente · Solo datos técnicos, sin información personal ni de pacientes</footer>
</div></body></html>"""
        self._enviar_html(html_texto)

    def _informe_equipo_csv(self, id_equipo):
        historial = obtener_historial_completo(id_equipo)
        lineas = ["Fecha y hora (UTC);Fecha local;Estado;CPU (%);RAM (%);Disco (%);Temp. CPU (°C)"]
        for ts, fecha_local, est, cpu, ram, disco, temp in historial:
            valores = [ts, fecha_local, ETIQUETAS_ESTADO.get(est, est), cpu, ram, disco, temp]
            lineas.append(";".join(_csv_campo(valor) for valor in valores))
        seguro = "".join(c for c in id_equipo if c.isalnum() or c in "-_") or "equipo"
        nombre = f"SaludPC_informe_{seguro}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        self._enviar_csv(nombre, "\r\n".join(lineas) + "\r\n")

    def _api_equipos(self, params):
        filtro_busqueda = params.get("buscar", [None])[0]
        filtro_estado = params.get("estado", [None])[0]
        equipos = listar_equipos(filtro_busqueda, filtro_estado)
        resultado = []
        for equipo in equipos:
            id_equipo, org, sede, area, fecha_ins, ultima, estado = equipo
            resultado.append({"id_equipo": id_equipo, "organizacion": org, "sede": sede, "area": area, "estado": estado, "ultima_conexion": ultima})
        self._enviar_json(200, resultado)

    def _api_progreso(self, params):
        """Devuelve el avance de aprendizaje del equipo que consulta."""
        id_equipo = params.get("id", [None])[0]
        token = params.get("token", [None])[0]

        if not id_equipo or not token:
            self._enviar_json(400, {"error": "id y token son requeridos"})
            return

        token_guardado = obtener_token(id_equipo)
        if not token_guardado or not hmac.compare_digest(token_guardado, token):
            self._enviar_json(403, {"ok": False, "error": "Token inválido"})
            return

        self._enviar_json(200, obtener_progreso(id_equipo))

def main():
    if ya_hay_instancia():
        mostrar_error(
            "SaludPC Servidor",
            "El servidor ya está en ejecución en este equipo.\n\n"
            "Cierra la ventana del servidor anterior antes de abrir otra.",
        )
        return 1

    try:
        crear_base()
    except Exception as error:
        mostrar_error(
            "SaludPC Servidor",
            "No se pudo crear o abrir la base de datos.\n\n"
            f"Ruta: {RUTA_DB}\nError: {error}",
        )
        return 1

    ThreadingHTTPServer.allow_reuse_address = False
    try:
        servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), ManejadorSaludPC)
    except OSError as error:
        mostrar_error(
            "SaludPC Servidor",
            f"No se pudo abrir el puerto {PUERTO}.\n\n"
            "Puede que otra instancia del servidor esté en ejecución "
            f"o que el puerto esté ocupado por otro programa.\n\n{error}",
        )
        return 1

    log.info("Base de datos: %s", RUTA_DB)
    log.info("Registro: %s", RUTA_LOG)
    log.info("Servidor central SaludPC escuchando en el puerto %d", PUERTO)
    log.info("Panel de TI: http://localhost:%d/", PUERTO)
    print(f"Servidor SaludPC iniciado en el puerto {PUERTO}")
    print(f"Base de datos: {RUTA_DB}")
    print(f"Panel de TI: http://localhost:{PUERTO}/")
    print("Presiona Ctrl+C para detener")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log.info("Servidor detenido por el usuario")
    finally:
        servidor.server_close()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        detalle = traceback.format_exc()
        mostrar_error("SaludPC Servidor - Error inesperado", detalle)
        sys.exit(1)