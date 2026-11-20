"""Rutas de la aplicación, tanto en desarrollo como empaquetada."""

import os
import sys
from pathlib import Path


def congelado():
    return bool(getattr(sys, "frozen", False))


def carpeta_app():
    """Carpeta donde está el ejecutable (o los scripts en desarrollo)."""
    if congelado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def carpeta_recursos():
    """Carpeta interna de PyInstaller, donde quedan los archivos empaquetados."""
    if congelado():
        return Path(getattr(sys, "_MEIPASS", carpeta_app()))
    return carpeta_app()


def carpeta_sensores():
    """DLL de sensores: en desarrollo vive aparte para no mezclarla con el código."""
    if congelado():
        return carpeta_app()
    return carpeta_app() / "empaquetado" / "sensores"


def buscar_recurso(nombre):
    """Busca una DLL o archivo junto al ejecutable o dentro del paquete."""
    # En modo empaquetado (onefile), _MEIPASS es donde PyInstaller extrae los datos.
    if congelado():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            ruta = Path(meipass) / nombre
            if ruta.is_file():
                return ruta
    for base in (carpeta_sensores(), carpeta_app(), carpeta_recursos()):
        ruta = base / nombre
        if ruta.is_file():
            return ruta
    return carpeta_app() / nombre


def carpeta_datos():
    """Datos compartidos entre el servicio y la ventana.

    En desarrollo usa la carpeta del proyecto. Empaquetado usa ProgramData,
    que el instalador crea con permisos para todos los usuarios.
    """
    override = os.environ.get("SALUD_PC_DATOS")
    if override:
        ruta = Path(override)
    elif congelado():
        ruta = Path(os.environ.get("PROGRAMDATA", str(Path.home()))) / "SaludPC"
    else:
        ruta = carpeta_app()
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_reportes():
    """Reportes en HTML, uno por semana consultada."""
    ruta = carpeta_datos() / "reportes"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
