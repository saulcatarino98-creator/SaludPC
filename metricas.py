"""Traduce sensores crudos a métricas canónicas, con unidad y techo de riesgo.

Este es el único lugar donde se decide cómo se llama cada cosa. El colector,
el cerebro y el vigilante usan siempre estas mismas claves.
"""

UNIDADES = {
    "cpu_load": "%",
    "cpu_temp": "°C",
    "ram_load": "%",
    "disk_used_pct": "%",
    "disk_temp": "°C",
    "gpu_temp": "°C",
    "gpu_load": "%",
}

NOMBRES = {
    "cpu_load": "el procesador",
    "cpu_temp": "la temperatura del procesador",
    "ram_load": "la memoria",
    "disk_used_pct": "el espacio del disco",
    "disk_temp": "la temperatura del disco",
    "gpu_temp": "la temperatura de la tarjeta gráfica",
    "gpu_load": "la tarjeta gráfica",
}

# A partir de acá hay riesgo real, sin importar el histórico del equipo.
TECHOS_ROJO = {
    "cpu_load": 98.0,
    "cpu_temp": 90.0,
    "ram_load": 97.0,
    "disk_used_pct": 96.0,
    "disk_temp": 70.0,
    "gpu_temp": 85.0,
    "gpu_load": 99.0,
}

# Por debajo de esto no se avisa aunque el histórico del equipo sea bajo.
PISOS_AVISO = {
    "cpu_load": 85.0,
    "cpu_temp": 70.0,
    "ram_load": 80.0,
    "disk_used_pct": 80.0,
    "disk_temp": 50.0,
    "gpu_temp": 70.0,
    "gpu_load": 85.0,
}


def clasificar(categoria, sensor, tipo):
    """Devuelve (métrica, prioridad) para un sensor de LibreHardwareMonitor.

    Solo se usan las temperaturas: los porcentajes de uso los da psutil.
    Así se evita la colisión de "GPU Core" como Load y como Temperature.
    """
    cat = str(categoria or "").strip().lower()
    nom = str(sensor or "").strip().lower()
    tip = str(tipo or "").strip().lower()

    if tip != "temperature":
        return None, 0
    if cat.startswith("cpu"):
        if "package" in nom:
            return "cpu_temp", 3
        if "core" in nom:
            return "cpu_temp", 2
        return "cpu_temp", 1
    if cat.startswith("gpu"):
        return "gpu_temp", 1
    if "storage" in cat or "nvme" in cat:
        return "disk_temp", 1
    return None, 0


def elegir(candidatos):
    """{metrica: [(prioridad, valor), ...]} -> {metrica: (valor, unidad)}."""
    resultado = {}
    for metrica, opciones in candidatos.items():
        _, valor = max(opciones, key=lambda par: par[0])
        resultado[metrica] = (float(valor), UNIDADES[metrica])
    return resultado
