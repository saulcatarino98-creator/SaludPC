"""Preferencias del usuario para la edición local.

Guarda decisiones del usuario como no mostrar la ventana automáticamente al
iniciar sesión.
"""

import json
import logging
from pathlib import Path

import rutas

log = logging.getLogger("salud.config")

ARCHIVO = "config_usuario.json"


def _ruta():
    return rutas.carpeta_datos() / ARCHIVO


def cargar_preferencias():
    """Devuelve un diccionario con las preferencias del usuario."""
    try:
        datos = json.loads(_ruta().read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_preferencia(clave, valor):
    """Guarda una preferencia individual."""
    preferencias = cargar_preferencias()
    preferencias[clave] = valor
    ruta = _ruta()
    temporal = ruta.with_suffix(".tmp")
    try:
        temporal.write_text(
            json.dumps(preferencias, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporal.replace(ruta)
    except OSError:
        log.exception("No se pudo guardar la preferencia del usuario")


def mostrar_ventana_inicio():
    """Devuelve True si se debe mostrar la ventana al iniciar sesión."""
    return cargar_preferencias().get("mostrar_ventana_inicio", True)
