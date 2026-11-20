"""Consumo del propio agente: CPU y memoria del servicio y del panel.

El servicio corre siempre y el panel solo cuando está abierto, así que cada
proceso mide lo suyo. El servicio publica su consumo en un JSON chico y el
panel lo lee y lo suma al propio. Así el panel no necesita permisos sobre el
proceso elevado del servicio.

La CPU de psutil se mide por núcleo; acá se divide por la cantidad de núcleos
lógicos para que el número sea comparable con el uso total del equipo.
"""

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

import psutil

import rutas

log = logging.getLogger("salud.agente")

ARCHIVO = "consumo_servicio.json"

# Si el servicio dejó de escribir hace más de esto, su dato ya no sirve.
FRESCURA_SEGUNDOS = 180

# Debajo de este promedio se puede decir que el consumo es bajo.
UMBRAL_BAJO = 0.95

# Una medición recién arrancada no es representativa: se espera a que la
# ventana se estabilice después del trabajo de inicio.
ESPERA_MINIMA_SEGUNDOS = 10.0

# El promedio se calcula sobre los últimos 5 minutos, no sobre una cantidad
# fija de muestras: las lecturas de sensores no siempre tardan lo mismo.
VENTANA_SEGUNDOS = 300


class Medidor:
    """Promedio móvil por tiempo de CPU y memoria de un proceso."""

    def __init__(self, pid=None, ventana_segundos=VENTANA_SEGUNDOS):
        self.proceso = psutil.Process(pid)
        self.ventana = max(1, int(ventana_segundos))
        self.nucleos = psutil.cpu_count(logical=True) or 1
        self.total_ram = psutil.virtual_memory().total or 1
        self._cpu = deque()
        self._ram = deque()
        self._inicio = time.monotonic()
        try:
            # La primera llamada de psutil siempre devuelve 0: se descarta.
            self.proceso.cpu_percent(interval=None)
        except psutil.Error:
            pass

    def medir(self):
        """Devuelve (cpu %, RAM MB, RAM %) promediados, o None si no se puede."""
        if time.monotonic() - self._inicio < ESPERA_MINIMA_SEGUNDOS:
            return None
        try:
            cpu = self.proceso.cpu_percent(interval=None) / self.nucleos
            memoria = self.proceso.memory_info().rss
        except psutil.Error:
            return None

        ahora = time.monotonic()
        self._cpu.append((ahora, max(0.0, float(cpu))))
        self._ram.append((ahora, max(0, int(memoria))))
        while len(self._cpu) > 1 and ahora - self._cpu[0][0] > self.ventana:
            self._cpu.popleft()
        while len(self._ram) > 1 and ahora - self._ram[0][0] > self.ventana:
            self._ram.popleft()

        cpu_promedio = sum(valor for _, valor in self._cpu) / len(self._cpu)
        ram_promedio = sum(valor for _, valor in self._ram) / len(self._ram)
        ram_mb = ram_promedio / (1024 * 1024)
        ram_pct = ram_promedio / self.total_ram * 100
        return cpu_promedio, ram_mb, ram_pct


def _ruta_servicio():
    return rutas.carpeta_datos() / ARCHIVO


def escribir_servicio(cpu, ram_mb, ram_pct, ts=None):
    """Publica el consumo del servicio para que lo lea el panel."""
    momento = ts or datetime.now(timezone.utc)
    if isinstance(momento, str):
        marca = momento
    else:
        marca = momento.astimezone(timezone.utc).isoformat(timespec="seconds")
    datos = {
        "ts": marca,
        "cpu": round(float(cpu), 2),
        "ram_mb": round(float(ram_mb), 1),
        "ram_pct": round(float(ram_pct), 2),
    }
    ruta = _ruta_servicio()
    temporal = ruta.with_suffix(".tmp")
    try:
        temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        temporal.replace(ruta)
    except OSError:
        log.exception("No se pudo guardar el consumo del servicio")


def leer_servicio(ahora=None):
    """Lee el consumo publicado por el servicio, si todavía está fresco."""
    try:
        datos = json.loads(_ruta_servicio().read_text(encoding="utf-8"))
        marca = datetime.fromisoformat(datos["ts"])
        cpu = float(datos["cpu"])
        ram_mb = float(datos["ram_mb"])
        ram_pct = float(datos["ram_pct"])
    except (OSError, ValueError, KeyError, TypeError):
        return None

    if marca.tzinfo is None:
        marca = marca.replace(tzinfo=timezone.utc)
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    if (ahora - marca).total_seconds() > FRESCURA_SEGUNDOS:
        return None

    return {"cpu": cpu, "ram_mb": ram_mb, "ram_pct": ram_pct, "ts": datos["ts"]}


def texto(cpu, ram_mb, ram_pct):
    """Línea discreta para la cabecera del panel."""
    linea = (
        f"Consumo del agente ({VENTANA_SEGUNDOS // 60} min): CPU: {cpu:.1f}% | "
        f"RAM: {ram_mb:.1f} MB ({ram_pct:.1f}%)"
    )
    if cpu < UMBRAL_BAJO:
        linea += " · consumo bajo"
    return linea
