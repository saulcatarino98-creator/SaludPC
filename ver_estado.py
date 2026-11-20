"""Muestra, en lenguaje simple, si SaludPC esta funcionando."""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB = Path(r"C:\ProgramData\SaludPC\salud.db")

NOMBRES = {
    "cpu_load": "Procesador",
    "cpu_temp": "Temperatura del procesador",
    "ram_load": "Memoria",
    "disk_used_pct": "Disco (lleno)",
    "disk_temp": "Temperatura del disco",
    "gpu_temp": "Temperatura de la placa de video",
}

UNIDADES = {"%": "%", "\u00b0C": " C"}


def hace(segundos):
    if segundos < 90:
        return "hace menos de 2 minutos"
    minutos = int(segundos // 60)
    if minutos < 60:
        return f"hace {minutos} minutos"
    horas = minutos // 60
    if horas < 24:
        return f"hace {horas} horas"
    return f"hace {horas // 24} dias"


def main():
    if not DB.is_file():
        print("Todavia no hay datos guardados.")
        return 1

    conexion = sqlite3.connect(DB)
    total = conexion.execute("select count(*) from muestras").fetchone()[0]
    ultima = conexion.execute("select max(ts) from muestras").fetchone()[0]
    if not ultima:
        print("La base existe pero esta vacia.")
        return 1

    momento = datetime.fromisoformat(ultima)
    ahora = datetime.now(timezone.utc)
    segundos = (ahora - momento).total_seconds()

    print("SALUD DE MI EQUIPO")
    print("=" * 40)
    print(f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

    if segundos < 180:
        print("Estado: FUNCIONANDO")
    elif segundos < 1800:
        print("Estado: funcionando, pero la ultima medicion es vieja.")
    else:
        print("Estado: ATENCION - hace mucho que no guarda datos.")

    print(f"Ultima medicion: {hace(segundos)}")
    print(f"Mediciones guardadas: {total}")
    print()

    filas = conexion.execute(
        "select metrica, valor, unidad from muestras "
        "where ts = (select max(ts) from muestras) order by metrica"
    ).fetchall()

    print("Ahora mismo:")
    for metrica, valor, unidad in filas:
        nombre = NOMBRES.get(metrica, metrica)
        simbolo = UNIDADES.get(unidad, unidad)
        if metrica.endswith("_temp"):
            texto = f"{valor:.0f}{simbolo}"
        elif metrica == "disk_used_pct":
            texto = f"{valor:.1f}{simbolo} ocupado"
        else:
            texto = f"{valor:.0f}{simbolo} en uso"
        print(f"  {nombre:<32} {texto}")

    print()
    print("Para el detalle dia por dia, abrir el panel del menu Inicio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
