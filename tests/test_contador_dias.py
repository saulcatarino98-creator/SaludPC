"""Prueba del contador de días: debe avanzar sin esperar el recálculo de 6 h.

No toca los datos reales: usa una carpeta temporal mediante SALUD_PC_DATOS.
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(tempfile.gettempdir()) / "saludpc_prueba_contador"
if BASE.exists():
    shutil.rmtree(BASE)
os.environ["SALUD_PC_DATOS"] = str(BASE)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import almacen  # noqa: E402
import cerebro  # noqa: E402


def guardar_dia(fecha, minutos=180):
    local = datetime.now().astimezone().tzinfo
    for minuto in range(minutos):
        momento = datetime.combine(
            fecha, datetime.min.time(), local
        ) + timedelta(hours=10, minutes=minuto)
        ts = momento.astimezone(timezone.utc).isoformat(timespec="seconds")
        almacen.guardar(
            ts,
            {
                "cpu_load": (25.0 + (minuto % 10) * 0.5, "%"),
                "ram_load": (50.0, "%"),
                "disk_used_pct": (60.0, "%"),
            },
        )


def leer_baseline():
    candidatos = list(BASE.glob("baseline_*.json"))
    if not candidatos:
        raise RuntimeError("No se generó el baseline")
    return json.loads(candidatos[0].read_text(encoding="utf-8"))


def main():
    almacen.crear()
    local = datetime.now().astimezone().tzinfo
    hoy = datetime.now(local).date()

    # Día 1 y día 2: todavía debe estar aprendiendo.
    guardar_dia(hoy - timedelta(days=2))
    guardar_dia(hoy - timedelta(days=1))
    cerebro.main()
    baseline = leer_baseline()

    dias_rapido, muestras_rapido = almacen.contar_dias_muestras()
    _, dias_pandas, muestras_pandas = cerebro.leer_historial()
    assert (dias_rapido, muestras_rapido) == (dias_pandas, muestras_pandas), (
        dias_rapido,
        muestras_rapido,
        dias_pandas,
        muestras_pandas,
    )

    print("Con 2 fechas:")
    print(f"  dias={baseline['dias']} muestras={baseline['muestras']}")
    print(f"  aprendiendo={baseline['aprendiendo']}")
    assert baseline["dias"] == 2, baseline
    assert baseline["aprendiendo"] is True
    assert baseline["metricas"] == {}

    # Día 3: el mismo cálculo, sin reiniciar nada, debe destrabar el modelo.
    guardar_dia(hoy)
    cerebro.main()
    baseline = leer_baseline()

    print("Con 3 fechas:")
    print(f"  dias={baseline['dias']} muestras={baseline['muestras']}")
    print(f"  aprendiendo={baseline['aprendiendo']}")
    print(f"  metricas={', '.join(sorted(baseline['metricas']))}")
    assert baseline["dias"] == 3, baseline
    assert baseline["muestras"] >= 300
    assert baseline["aprendiendo"] is False
    assert "cpu_load" in baseline["metricas"]

    print("\nTODAS LAS COMPROBACIONES PASARON")


if __name__ == "__main__":
    main()
