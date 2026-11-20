"""Prueba del consumo del agente y del archivo que publica el servicio.

No toca los datos reales: usa una carpeta temporal mediante SALUD_PC_DATOS.
"""

import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(tempfile.gettempdir()) / "saludpc_prueba_agente"
if BASE.exists():
    shutil.rmtree(BASE)
os.environ["SALUD_PC_DATOS"] = str(BASE)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agente  # noqa: E402


def main():
    medidor = agente.Medidor(pid=os.getpid(), ventana_segundos=300)

    # Antes de la espera mínima no hay una medición representativa.
    assert medidor.medir() is None
    medidor._inicio -= agente.ESPERA_MINIMA_SEGUNDOS + 1
    time.sleep(1.0)

    cpu, ram_mb, ram_pct = medidor.medir()
    assert 0.0 <= cpu < 100.0, cpu
    assert ram_mb > 0.0, ram_mb
    assert 0.0 < ram_pct < 100.0, ram_pct

    print("Medición del proceso actual:")
    print(f"  CPU={cpu:.2f} %  RAM={ram_mb:.1f} MB ({ram_pct:.2f} %)")

    # El archivo fresco se lee tal cual lo escribió el servicio.
    agente.escribir_servicio(cpu, ram_mb, ram_pct)
    datos = agente.leer_servicio()
    assert datos is not None
    assert abs(datos["cpu"] - round(cpu, 2)) < 0.01, datos
    assert abs(datos["ram_mb"] - round(ram_mb, 1)) < 0.11, datos
    assert abs(datos["ram_pct"] - round(ram_pct, 2)) < 0.01, datos

    # Un archivo viejo ya no sirve: el servicio pudo haberse detenido.
    viejo = datetime.now(timezone.utc) - timedelta(
        seconds=agente.FRESCURA_SEGUNDOS + 5
    )
    agente.escribir_servicio(0.1, 10.0, 0.1, ts=viejo)
    assert agente.leer_servicio() is None

    linea = agente.texto(0.2, 34.2, 1.1)
    assert "Consumo del agente" in linea
    assert "0.2%" in linea
    assert "34.2 MB" in linea
    assert "1.1%" in linea
    assert "consumo bajo" in linea

    # Con CPU promedio por encima del 1 % no se afirma que sea bajo.
    assert "consumo bajo" not in agente.texto(1.5, 20.0, 0.5)

    print(f"Línea del panel: {agente.texto(0.2, 34.2, 1.1)}")
    print("\nTODAS LAS COMPROBACIONES PASARON")


if __name__ == "__main__":
    main()
