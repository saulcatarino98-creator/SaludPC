"""Recolector: guarda una foto del estado del equipo una vez por minuto."""

import ctypes
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psutil
import tkinter as tk

import almacen
import metricas
import rutas

log = logging.getLogger("salud.colector")

INTERVALO_SEGUNDOS = 60

_equipo = None
_sensores_intentados = False

# Si está activa, el programa nunca intenta cargar .NET ni LibreHardwareMonitor.
# Útil para equipos antiguos o sin Visual C++ Redistributable / .NET Framework.
NO_SENSORS = os.environ.get("SALUDPC_NO_SENSORS", "0") == "1"


def es_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def obtener_equipo():
    """Abre LibreHardwareMonitor una sola vez. Devuelve None si no está."""
    global _equipo, _sensores_intentados
    if _sensores_intentados:
        return _equipo
    _sensores_intentados = True

    if NO_SENSORS:
        log.info("Modo lite: sensores de temperatura desactivados")
        return None

    try:
        import clr

        dll = rutas.buscar_recurso("LibreHardwareMonitorLib.dll")
        if not dll.is_file():
            raise FileNotFoundError(f"No se encontró {dll.name}")
        clr.AddReference(str(dll))
        hardware = __import__(
            "LibreHardwareMonitor.Hardware", fromlist=["Computer"]
        )
        equipo = hardware.Computer()
        equipo.IsCpuEnabled = True
        equipo.IsGpuEnabled = True
        equipo.IsMotherboardEnabled = True
        equipo.IsControllerEnabled = True
        equipo.IsMemoryEnabled = True
        equipo.IsStorageEnabled = True
        equipo.Open()
        _equipo = equipo
    except Exception as error:
        log.warning("No se pudieron abrir los sensores de temperatura: %s", error)
    return _equipo


def acumular_temperaturas(hardware, candidatos):
    categoria = str(hardware.HardwareType)
    for sensor in hardware.Sensors:
        if sensor.Value is None:
            continue
        metrica, prioridad = metricas.clasificar(
            categoria, sensor.Name, sensor.SensorType
        )
        if metrica:
            candidatos.setdefault(metrica, []).append(
                (prioridad, float(sensor.Value))
            )
    for sub in hardware.SubHardware:
        sub.Update()
        acumular_temperaturas(sub, candidatos)


def _leer_valores(intervalo_cpu):
    candidatos = {}
    equipo = obtener_equipo()
    if equipo is not None:
        for hardware in equipo.Hardware:
            hardware.Update()
            acumular_temperaturas(hardware, candidatos)

    valores = {
        "cpu_load": (psutil.cpu_percent(interval=intervalo_cpu), "%"),
        "ram_load": (psutil.virtual_memory().percent, "%"),
        "disk_used_pct": (
            psutil.disk_usage(Path.home().anchor or "C:\\").percent,
            "%",
        ),
    }
    valores.update(metricas.elegir(candidatos))
    return valores


def leer_actuales():
    """Lee los valores actuales sin guardarlos ni afectar el aprendizaje."""
    return _leer_valores(intervalo_cpu=0.25)


def recolectar():
    """Toma una foto del equipo y la guarda. Devuelve (hora local, filas, valores)."""
    valores = _leer_valores(intervalo_cpu=0.5)

    ahora = datetime.now(timezone.utc)
    guardadas = almacen.guardar(ahora.isoformat(timespec="seconds"), valores)
    return ahora.astimezone(), guardadas, valores


def cerrar_equipo():
    if _equipo is not None:
        try:
            _equipo.Close()
        except Exception:
            pass


def main():
    almacen.crear()

    ventana = tk.Tk()
    ventana.title("Salud de mi equipo — recolección")
    ventana.geometry("480x280")

    estado = tk.Label(
        ventana,
        text="Preparando la primera lectura…",
        font=("Segoe UI", 11),
        justify="left",
        anchor="w",
        wraplength=440,
    )
    estado.pack(fill="both", expand=True, padx=16, pady=16)

    pie = tk.Label(
        ventana,
        text=(
            f"Se guarda una lectura cada {INTERVALO_SEGUNDOS} segundos.\n"
            "Mantené esta ventana abierta mientras usás la computadora."
        ),
        font=("Segoe UI", 9),
        fg="#555555",
        justify="left",
        anchor="w",
        wraplength=440,
    )
    pie.pack(fill="x", padx=16, pady=(0, 12))

    def ciclo():
        try:
            ahora, guardadas, _ = recolectar()
            equipo = obtener_equipo()
            detalle = (
                "con temperaturas"
                if equipo is not None
                else "sin temperaturas (abrí el programa como administrador)"
            )
            estado.config(
                text=(
                    f"Última lectura: {ahora:%d/%m/%Y %H:%M:%S}\n"
                    f"Se guardaron {guardadas} valores, {detalle}.\n\n"
                    "El análisis se hace sobre estas mediciones. "
                    "Si cerrás la ventana, se dejan de tomar datos."
                )
            )
        except Exception as error:
            estado.config(text=f"No se pudo leer el equipo:\n{error}")
        ventana.after(INTERVALO_SEGUNDOS * 1000, ciclo)

    def cerrar():
        cerrar_equipo()
        ventana.destroy()

    ventana.protocol("WM_DELETE_WINDOW", cerrar)
    ventana.after(100, ciclo)
    ventana.mainloop()


if __name__ == "__main__":
    if "--una-vez" in sys.argv:
        almacen.crear()
        ahora, guardadas, valores = recolectar()
        print(f"{ahora:%Y-%m-%d %H:%M:%S}: {guardadas} valores guardados")
        for metrica, (valor, unidad) in sorted(valores.items()):
            print(f"  {metrica}: {valor:.1f}{unidad}")
        if not es_admin():
            print(
                "Aviso: sin permisos de administrador puede faltar "
                "la temperatura del procesador."
            )
        cerrar_equipo()
    else:
        main()
