"""Prueba aislada del modelo: baseline, estado normal, atencion y accion.

No toca los datos reales: usa una carpeta temporal mediante SALUD_PC_DATOS.
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(tempfile.gettempdir()) / "saludpc_prueba_modelo"
if BASE.exists():
    shutil.rmtree(BASE)
os.environ["SALUD_PC_DATOS"] = str(BASE)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import almacen  # noqa: E402
import cerebro  # noqa: E402
import vigilante  # noqa: E402


def guardar(ts, cpu, temp=48.0, ram=50.0, disco=60.0):
    almacen.guardar(
        ts,
        {
            "cpu_load": (cpu, "%"),
            "cpu_temp": (temp, "\u00b0C"),
            "ram_load": (ram, "%"),
            "disk_used_pct": (disco, "%"),
        },
    )


def main():
    almacen.crear()
    local = datetime.now().astimezone().tzinfo
    hoy = datetime.now(local).date()

    # Tres dias distintos con 180 muestras cada uno: supera los minimos
    # de 3 dias y 300 muestras. Los valores son normales y estables.
    for dias_atras in (3, 2, 1):
        fecha = hoy - timedelta(days=dias_atras)
        for minuto in range(180):
            momento = datetime.combine(
                fecha, datetime.min.time(), local
            ) + timedelta(hours=10, minutes=minuto)
            ts = momento.astimezone(timezone.utc).isoformat(timespec="seconds")
            guardar(ts, cpu=25.0 + (minuto % 10) * 0.5)

    cerebro.main()

    ruta = BASE / f"baseline_{os.environ.get('COMPUTERNAME', '')}.json"
    if not ruta.exists():
        candidatos = list(BASE.glob("baseline_*.json"))
        if not candidatos:
            raise RuntimeError("No se genero el baseline")
        ruta = candidatos[0]

    baseline = json.loads(ruta.read_text(encoding="utf-8"))
    cpu = baseline["metricas"].get("cpu_load", {})

    ahora = datetime.now(timezone.utc).replace(microsecond=0)

    # Cinco muestras recientes con CPU al 96 %: debe dar atencion (amarillo).
    for i in range(5):
        ts = (ahora - timedelta(minutes=4 - i)).isoformat(timespec="seconds")
        guardar(ts, cpu=96.0)
    atencion = vigilante.diagnosticar(ahora=ahora + timedelta(minutes=1))

    # Cinco muestras con CPU al 99 %: debe dar accion (rojo).
    for i in range(5):
        ts = (ahora + timedelta(minutes=2 + i)).isoformat(timespec="seconds")
        guardar(ts, cpu=99.0)
    accion = vigilante.diagnosticar(ahora=ahora + timedelta(minutes=8))

    # Cinco muestras normales: debe volver a ok.
    for i in range(5):
        ts = (ahora + timedelta(minutes=9 + i)).isoformat(timespec="seconds")
        guardar(ts, cpu=25.0)
    normal = vigilante.diagnosticar(ahora=ahora + timedelta(minutes=15))

    lineas = [
        "PRUEBA DEL MODELO (datos simulados, carpeta temporal)",
        f"Carpeta: {BASE}",
        "",
        f"Aprendiendo: {baseline['aprendiendo']}",
        f"Dias con datos: {baseline['dias']}",
        f"Muestras distintas: {baseline['muestras']}",
        f"Metricas en el baseline: {', '.join(sorted(baseline['metricas']))}",
        "",
        f"CPU limite amarillo: {cpu.get('limite_aviso')} %",
        f"CPU limite rojo: {cpu.get('limite_rojo')} %",
        f"CPU mediana: {cpu.get('mediana')} %",
        f"CPU p95: {cpu.get('p95')} %",
        "",
        f"Estado con CPU 96 %: {atencion['estado']}",
        f"Mensaje: {atencion['mensaje']}",
        "",
        f"Estado con CPU 99 %: {accion['estado']}",
        f"Mensaje: {accion['mensaje']}",
        "",
        f"Estado con CPU 25 %: {normal['estado']}",
        f"Mensaje: {normal['mensaje']}",
    ]
    texto = "\n".join(lineas)
    (Path(__file__).parent / "resultado_modelo.txt").write_text(texto, encoding="utf-8")
    print(texto.encode("ascii", "replace").decode("ascii"))

    assert baseline["aprendiendo"] is False
    assert baseline["dias"] >= 3
    assert baseline["muestras"] >= 300
    assert "cpu_load" in baseline["metricas"]
    assert atencion["estado"] == "atencion", atencion
    assert accion["estado"] == "accion", accion
    assert normal["estado"] == "ok", normal
    print("\nTODAS LAS COMPROBACIONES PASARON")


if __name__ == "__main__":
    main()
