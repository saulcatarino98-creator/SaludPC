"""Cliente enterprise para agentes SaludPC.

Envía reportes al servidor central con firma HMAC-SHA256 y guarda
localmente el registro del equipo para no volver a inscribirlo.
"""

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


class ClienteEnterprise:
    def __init__(self, id_equipo, token, url_servidor="https://localhost:8443"):
        self.id_equipo = id_equipo
        self.token = token or ""
        self.url_servidor = url_servidor.rstrip("/")

    # ------------------------------------------------------------------
    # Utilidades HTTP
    # ------------------------------------------------------------------

    def _firmar(self, datos_json):
        """Crea firma HMAC-SHA256 con el token del equipo."""
        return hmac.new(
            self.token.encode("utf-8"),
            datos_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _pedir_json(self, ruta, payload=None, metodo="POST", timeout=10):
        cuerpo = None
        cabeceras = {}
        if payload is not None:
            cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            cabeceras["Content-Type"] = "application/json"
        peticion = urllib.request.Request(
            f"{self.url_servidor}{ruta}",
            data=cuerpo,
            headers=cabeceras,
            method=metodo,
        )
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            # El servidor responde 409 con el token cuando el equipo ya existe.
            try:
                return json.loads(error.read().decode("utf-8"))
            except (ValueError, OSError):
                return {"ok": False, "error": f"HTTP {error.code}"}
        except urllib.error.URLError as error:
            return {"ok": False, "error": f"No se pudo conectar: {error.reason}"}
        except (ValueError, OSError) as error:
            return {"ok": False, "error": str(error)}

    # ------------------------------------------------------------------
    # API del servidor
    # ------------------------------------------------------------------

    def inscribir(self, organizacion, sede, area):
        """Inscribe este equipo en el servidor central."""
        payload = {
            "id_equipo": self.id_equipo,
            "organizacion": organizacion,
            "sede": sede,
            "area": area,
        }
        return self._pedir_json("/inscribir", payload)

    def enviar_reporte(self, datos):
        """Envía un reporte de métricas al servidor central."""
        reporte = dict(datos)
        reporte["id_equipo"] = self.id_equipo
        reporte["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        reporte["fecha_local"] = datetime.now().strftime("%Y-%m-%d")
        cuerpo = json.dumps(reporte, ensure_ascii=False)
        reporte["firma_hmac"] = self._firmar(cuerpo)
        return self._pedir_json("/reporte", reporte)

    def enviar_aviso(self, estado, mensaje=""):
        """Envía un aviso al servidor central."""
        payload = {
            "id_equipo": self.id_equipo,
            "estado": estado,
            "mensaje": mensaje,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return self._pedir_json("/aviso", payload)

    def consultar_progreso(self):
        """Consulta el avance de aprendizaje registrado en el servidor."""
        # El token se envía en el header Authorization, no en la URL.
        ruta = f"/progreso?id={quote(self.id_equipo)}"
        peticion = urllib.request.Request(
            f"{self.url_servidor}{ruta}",
            method="GET",
        )
        if self.token:
            peticion.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(peticion, timeout=10) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                return json.loads(error.read().decode("utf-8"))
            except (ValueError, OSError):
                return {"ok": False, "error": f"HTTP {error.code}"}
        except urllib.error.URLError as error:
            return {"ok": False, "error": f"No se pudo conectar: {error.reason}"}
        except (ValueError, OSError) as error:
            return {"ok": False, "error": str(error)}


# ---------------------------------------------------------------------------
# Registro local del equipo (token + datos de inscripción)
# ---------------------------------------------------------------------------

def _carpeta_datos():
    """Carpeta local donde se guarda el registro del equipo."""
    override = os.environ.get("SALUD_PC_DATOS")
    if override:
        carpeta = Path(override)
    elif getattr(sys, "frozen", False):
        programa = os.environ.get("PROGRAMDATA")
        carpeta = (
            Path(programa) / "SaludPC" / "Cliente"
            if programa
            else Path.home() / ".saludpc"
        )
    else:
        carpeta = Path(__file__).resolve().parent
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _ruta_token():
    return _carpeta_datos() / "token_equipo.json"


def guardar_token_guardado(id_equipo, token, **extras):
    """Guarda el token y los datos de inscripción en un archivo local."""
    try:
        datos = {"id_equipo": id_equipo, "token": token}
        datos.update({clave: valor for clave, valor in extras.items() if valor is not None})
        ruta = _ruta_token()
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        temporal.replace(ruta)
    except OSError:
        pass


def cargar_registro():
    """Devuelve el registro completo del equipo, o {} si no existe."""
    try:
        datos = json.loads(_ruta_token().read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            return {}
        return datos
    except (OSError, ValueError):
        return {}


def cargar_token_guardado():
    """Carga el token y el ID guardados. Devuelve (token, id_equipo)."""
    datos = cargar_registro()
    return datos.get("token"), datos.get("id_equipo")


def borrar_registro():
    """Elimina el registro local (para reinscribir desde cero)."""
    try:
        _ruta_token().unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Preferencias del cliente
# ---------------------------------------------------------------------------

def _ruta_config():
    return _carpeta_datos() / "config_cliente.json"


def cargar_config_cliente():
    """Devuelve las preferencias locales del cliente."""
    try:
        datos = json.loads(_ruta_config().read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_config_cliente(**cambios):
    """Guarda una o varias preferencias del cliente."""
    datos = cargar_config_cliente()
    datos.update(cambios)
    try:
        ruta = _ruta_config()
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporal.replace(ruta)
    except OSError:
        pass


def mostrar_ventana_inicio():
    """True si la ventana debe mostrarse al iniciar sesión."""
    return bool(cargar_config_cliente().get("mostrar_ventana_inicio", True))
