"""Prueba de cliente Enterprise - Inscripción y envío de reporte."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cliente_enterprise import ClienteEnterprise


def main():
    print("SaludPC Enterprise - Cliente de prueba")
    print("=" * 45)

    # ID del equipo (cambiar por cada computadora)
    id_equipo = input("ID del equipo (ej. PC-001): ").strip() or "PC-001"
    organizacion = input("Organización: ").strip() or "Hospital Central"
    sede = input("Sede: ").strip() or "Sede Norte"
    area = input("Área: ").strip() or "Área de Emergencias"
    url_servidor = input("URL del servidor (ej. http://192.168.1.100:8443): ").strip() or "http://localhost:8443"

    cliente = ClienteEnterprise(
        id_equipo=id_equipo,
        token="",
        url_servidor=url_servidor,
    )

    print("\n--- Paso 1: Inscripción ---")
    resultado = cliente.inscribir(organizacion, sede, area)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    if not resultado.get("ok"):
        print("\nNo se pudo inscribir. Verifique que el servidor esté en línea.")
        input("Presione Enter para salir...")
        return

    token = resultado["token"]
    print(f"\nToken guardado: {token}")
    print("\nGuarde este token. Lo necesitará para enviar reportes.")

    print("\n--- Paso 2: Enviar reporte de prueba ---")
    cliente.token = token

    reporte = {
        "estado": "ok",
        "cpu_load": 32.5,
        "ram_load": 45.0,
        "disk_used_pct": 24.7,
        "cpu_temp": 54.0,
    }

    resultado_reporte = cliente.enviar_reporte(reporte)
    print(json.dumps(resultado_reporte, indent=2, ensure_ascii=False))

    print("\n--- Paso 3: Enviar aviso de prueba ---")
    resultado_aviso = cliente.enviar_aviso("atencion", "Prueba de aviso desde el cliente")
    print(json.dumps(resultado_aviso, indent=2, ensure_ascii=False))

    print("\n=== Prueba completada ===")
    input("Presione Enter para salir...")


if __name__ == "__main__":
    main()
