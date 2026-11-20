"""Prueba de categorías y episodios de pico.

No toca los datos reales: usa una carpeta temporal mediante SALUD_PC_DATOS.
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(tempfile.gettempdir()) / "saludpc_prueba_episodios"
if BASE.exists():
    shutil.rmtree(BASE)
os.environ["SALUD_PC_DATOS"] = str(BASE)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import almacen  # noqa: E402
import eventos  # noqa: E402


def diagnostico(metrica, estado, ultimo, aviso=87.7, rojo=98.0):
    return {
        "estado": estado,
        "detalles": [
            {
                "metrica": metrica,
                "nombre": metrica,
                "estado": estado,
                "ultimo": ultimo,
                "limite_aviso": aviso,
                "limite_rojo": rojo,
            }
        ],
    }


def picos():
    return [fila for fila in almacen.leer_eventos(limite=50) if fila[1] == "pico"]


def main():
    almacen.crear()

    # ---------------------------------------------------------- categorías --
    assert eventos.categoria("suspension") == "energia"
    assert eventos.categoria("apagado") == "energia"
    assert eventos.categoria("normal") == "carga"
    assert (
        eventos.categoria("estado", json.dumps({"metrica": "cpu_temp"}))
        == "termicas"
    )
    assert (
        eventos.categoria("estado", json.dumps({"metrica": "cpu_load"})) == "carga"
    )
    assert (
        eventos.categoria("pico", json.dumps({"metrica": "gpu_temp"})) == "termicas"
    )
    print("Categorías: energía, carga y térmicas clasifican bien.")

    ahora = datetime.now(timezone.utc).replace(microsecond=0)

    # ------------------------------------------------------- pico muy corto --
    for minuto in range(4):
        eventos.actualizar_episodios(
            diagnostico("cpu_load", "atencion", 88.0),
            ahora + timedelta(minutes=minuto),
        )
    cerrados = eventos.actualizar_episodios(
        diagnostico("cpu_load", "ok", 20.0), ahora + timedelta(minutes=4)
    )
    assert cerrados == [], cerrados
    assert picos() == [], picos()
    print("Un episodio de 4 minutos no se guarda.")

    # -------------------------------------------------------- pico de carga --
    inicio = ahora + timedelta(hours=1)
    valores = [88.0, 89.0, 97.0, 96.0, 90.0, 87.0]
    for minuto, valor in enumerate(valores):
        eventos.actualizar_episodios(
            diagnostico("cpu_load", "atencion", valor),
            inicio + timedelta(minutes=minuto),
        )
    cerrados = eventos.actualizar_episodios(
        diagnostico("cpu_load", "ok", 20.0), inicio + timedelta(minutes=6)
    )
    assert len(cerrados) == 1, cerrados

    filas = picos()
    assert len(filas) == 1, filas
    ts, tipo, detalle, valor = filas[0]
    datos = json.loads(detalle)
    assert tipo == "pico"
    assert datos["metrica"] == "cpu_load"
    assert datos["maximo"] == 97.0, datos
    assert datos["duracion"] == 6.0, datos
    assert datos["inicio"] == inicio.isoformat(timespec="seconds"), datos
    assert datos["fin"] == (inicio + timedelta(minutes=6)).isoformat(
        timespec="seconds"
    ), datos
    assert valor == 97.0, valor

    titulo, texto, tono = eventos.describir(ts, tipo, detalle, valor)
    assert titulo == "Pico de carga", titulo
    assert "6 minutos" in texto, texto
    assert "97 %" in texto, texto
    assert tono == "atencion", tono
    print(f"Pico de carga guardado: {texto}")

    # ----------------------------------------------------- pico térmico rojo --
    detalle_termico = json.dumps(
        {
            "metrica": "cpu_temp",
            "inicio": inicio.isoformat(timespec="seconds"),
            "fin": (inicio + timedelta(minutes=8)).isoformat(timespec="seconds"),
            "maximo": 93.0,
            "duracion": 8.0,
            "limite_aviso": 76.7,
            "limite_rojo": 90.0,
            "estado": "accion",
        }
    )
    titulo, texto, tono = eventos.describir(
        inicio.isoformat(timespec="seconds"), "pico", detalle_termico, 93.0
    )
    assert titulo == "Pico de temperatura", titulo
    assert "8 minutos" in texto, texto
    assert "93 °C" in texto, texto
    assert tono == "accion", tono
    print(f"Pico térmico: {texto}")

    # ------------------------------------------- episodio abandonado al caer --
    viejo = ahora - timedelta(hours=2)
    ruta = eventos._ruta_episodios()
    ruta.write_text(
        json.dumps(
            {
                "gpu_temp": {
                    "inicio": viejo.isoformat(timespec="seconds"),
                    "ultimo": viejo.isoformat(timespec="seconds"),
                    "maximo": 88.0,
                    "limite_aviso": 70.0,
                    "limite_rojo": 85.0,
                    "estado": "accion",
                }
            }
        ),
        encoding="utf-8",
    )
    antes = len(picos())
    eventos.actualizar_episodios(
        diagnostico("gpu_temp", "ok", 50.0, 70.0, 85.0), ahora
    )
    assert len(picos()) == antes, "un episodio viejo no debe cerrarse como pico"
    assert json.loads(ruta.read_text(encoding="utf-8")) == {}
    print("Un episodio abandonado durante una caída se descarta.")

    print("\nTODAS LAS COMPROBACIONES PASARON")


if __name__ == "__main__":
    main()
