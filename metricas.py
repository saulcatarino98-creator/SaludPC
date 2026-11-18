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
    # Voltajes de fuente de poder
    "psu_12v": "V",
    "psu_5v": "V",
    "psu_3v3": "V",
    # Ventiladores
    "fan_cpu_rpm": "RPM",
    "fan_chasis_rpm": "RPM",
    "fan_gpu_rpm": "RPM",
    # Salud del disco (SMART)
    "disk_smart_health": "%",
    "disk_smart_temp": "°C",
    # Tendencias (pendiente de temperatura)
    "temp_trend_cpu": "°C/min",
    "temp_trend_gpu": "°C/min",
    "temp_trend_disk": "°C/min",
}

NOMBRES = {
    "cpu_load": "el procesador",
    "cpu_temp": "la temperatura del procesador",
    "ram_load": "la memoria",
    "disk_used_pct": "el espacio del disco",
    "disk_temp": "la temperatura del disco",
    "gpu_temp": "la temperatura de la tarjeta gráfica",
    "gpu_load": "la tarjeta gráfica",
    "psu_12v": "el voltaje de 12 V de la fuente",
    "psu_5v": "el voltaje de 5 V de la fuente",
    "psu_3v3": "el voltaje de 3.3 V de la fuente",
    "fan_cpu_rpm": "el ventilador del procesador",
    "fan_chasis_rpm": "el ventilador del chasis",
    "fan_gpu_rpm": "el ventilador de la tarjeta gráfica",
    "disk_smart_health": "la salud del disco (SMART)",
    "disk_smart_temp": "la temperatura SMART del disco",
    "temp_trend_cpu": "la subida de temperatura del procesador",
    "temp_trend_gpu": "la subida de temperatura de la tarjeta gráfica",
    "temp_trend_disk": "la subida de temperatura del disco",
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
    # Voltajes críticos (valores muy bajos indican falla de fuente)
    "psu_12v": 11.4,
    "psu_5v": 4.75,
    "psu_3v3": 3.14,
    # Ventilador detenido o casi detenido
    "fan_cpu_rpm": 100,
    "fan_chasis_rpm": 100,
    "fan_gpu_rpm": 100,
    # Salud del disco crítica
    "disk_smart_health": 10.0,
    # Pendiente alarmante: más de 0.5 °C por minuto sostenido
    "temp_trend_cpu": 0.5,
    "temp_trend_gpu": 0.5,
    "temp_trend_disk": 0.5,
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
    # Voltajes mínimos aceptables (por debajo se avisa)
    "psu_12v": 11.8,
    "psu_5v": 4.9,
    "psu_3v3": 3.3,
    # Ventilador muy lento (posible falla o obstrucción)
    "fan_cpu_rpm": 600,
    "fan_chasis_rpm": 400,
    "fan_gpu_rpm": 500,
    # Salud del disco baja
    "disk_smart_health": 60.0,
    # Tendencia preocupante: subida sostenida
    "temp_trend_cpu": 0.2,
    "temp_trend_gpu": 0.2,
    "temp_trend_disk": 0.2,
}


def clasificar_avanzado(categoria, sensor, tipo):
    """Clasifica sensores de voltaje, ventilador y salud de disco.

    Devuelve (metrica, prioridad) o (None, 0) si no coincide.
    Se usa junto a metricas.clasificar (temperaturas) en el colector.
    """
    cat = str(categoria or "").strip().lower()
    nom = str(sensor or "").strip().lower()
    tip = str(tipo or "").strip().lower()

    # ---- Voltajes (fuente de poder) ----
    if tip == "voltage":
        if "12" in nom:
            return "psu_12v", 3
        if "5" in nom and "v" in nom:
            return "psu_5v", 2
        if "3" in nom and ("3.3" in nom or "v" in nom):
            return "psu_3v3", 1

    # ---- Ventiladores (RPM) ----
    if tip == "fan":
        if "cpu" in nom or "procesador" in nom:
            return "fan_cpu_rpm", 3
        if "gpu" in nom or "gráfica" in nom or "video" in nom:
            return "fan_gpu_rpm", 2
        if "chasis" in nom or "case" in nom or "sistema" in nom:
            return "fan_chasis_rpm", 1
        return "fan_chasis_rpm", 1  # cualquier ventilador sin identificar

    # ---- Salud de disco (SMART) ----
    # Nota: depende de que LibreHardwareMonitor exponga el sensor.
    if "smart" in nom or "health" in nom or "vida" in nom:
        if "disco" in cat or "storage" in cat or "nvme" in cat:
            return "disk_smart_health", 3

    return None, 0


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
