"""Vigilante: convierte las mediciones en un diagnóstico en lenguaje simple."""

import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import almacen
import metricas
import rutas
import tendencias

DIRECTORIO = rutas.carpeta_datos()

ORDEN = {
    "ok": 0,
    "sin_datos": 1,
    "aprendiendo": 1,
    "atencion": 2,
    "accion": 3,
}

COLORES = {
    "ok": "🟢",
    "atencion": "🟡",
    "accion": "🔴",
    "aprendiendo": "⚪",
    "sin_datos": "⚪",
}

MENSAJES = {
    "cpu_load": (
        "El procesador está trabajando más de lo habitual.",
        "Cerrá los programas que no estés usando y fijate si mejora en unos minutos.",
    ),
    "cpu_temp": (
        "El procesador se está calentando más de lo normal.",
        "Revisá que el ventilador no esté tapado por polvo y que el equipo tenga espacio para ventilar.",
    ),
    "ram_load": (
        "La memoria está casi llena.",
        "Cerrá las pestañas y programas que no uses. Si pasa seguido, quizá convenga ampliar la memoria.",
    ),
    "disk_used_pct": (
        "Queda muy poco espacio en el disco.",
        "Liberá espacio o respaldá archivos en un disco externo o en la nube.",
    ),
    "disk_temp": (
        "El disco se está calentando más de lo normal.",
        "Evitá apoyar el equipo sobre superficies blandas y revisá la ventilación.",
    ),
    "gpu_temp": (
        "La tarjeta gráfica se está calentando más de lo normal.",
        "Cerrá juegos o programas pesados y revisá que el ventilador esté limpio.",
    ),
    "gpu_load": (
        "La tarjeta gráfica está trabajando más de lo habitual.",
        "Cerrá juegos o programas pesados que no estés usando.",
    ),
}


def salida(estado, mensaje, detalles=None, ultima=None):
    return {
        "estado": estado,
        "color": COLORES[estado],
        "mensaje": mensaje,
        "detalles": detalles or [],
        "ultima_lectura": ultima.isoformat() if ultima else None,
    }


def ruta_baseline(directorio=None):
    carpeta = Path(directorio) if directorio else DIRECTORIO
    return carpeta / f"baseline_{socket.gethostname()}.json"


def cargar_baseline(directorio=None):
    ruta = ruta_baseline(directorio)
    if not ruta.exists():
        return None
    try:
        with ruta.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(datos, dict) or datos.get("version") != 2:
        return None
    return datos


def limite_para(entrada, ahora_local):
    """Usa la franja horaria si tiene datos suficientes; si no, el límite global."""
    tipo = "finde" if ahora_local.weekday() >= 5 else "laboral"
    franja = (entrada.get("franjas") or {}).get(f"{tipo}_{ahora_local.hour}")
    if franja and franja.get("n", 0) >= 30:
        return (
            franja.get("limite_aviso", entrada["limite_aviso"]),
            entrada["limite_rojo"],
        )
    return entrada["limite_aviso"], entrada["limite_rojo"]


def estado_metrica(valores, aviso, rojo):
    """Pide que la desviación se sostenga: no alerta por un pico de un segundo."""
    if not valores:
        return "sin_datos"
    if sum(1 for valor in valores if valor >= rojo) >= 2:
        return "accion"
    if sum(1 for valor in valores if valor >= aviso) >= 3:
        return "atencion"
    return "ok"


def leer_valores(ahora, horas=6):
    desde = (ahora - timedelta(hours=horas)).isoformat(timespec="seconds")
    por_metrica = {}
    ultima = None
    for ts, metrica, valor, _ in almacen.leer(desde=desde):
        por_metrica.setdefault(metrica, []).append(float(valor))
        try:
            marca = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if ultima is None or marca > ultima:
            ultima = marca
    return por_metrica, ultima


def diagnosticar(directorio=None, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)

    baseline = cargar_baseline(directorio)
    if baseline is None:
        return salida(
            "sin_datos",
            "Todavía no terminamos de analizar este equipo. "
            "Dejá el programa funcionando unos días y volvé a mirar.",
        )

    if baseline.get("aprendiendo"):
        dias = int(baseline.get("dias") or 0)
        muestras = int(baseline.get("muestras") or 0)
        _, ultima = leer_valores(ahora)
        return salida(
            "aprendiendo",
            f"Estamos conociendo tu equipo ({dias} de 3 días, "
            f"{muestras} de 300 muestras). Todavía no podemos decir si algo "
            "está fuera de lo normal.",
            ultima=ultima,
        )

    por_metrica, ultima = leer_valores(ahora)
    if ultima is None:
        return salida(
            "sin_datos",
            "No hay datos recientes del equipo. "
            "Revisá que el programa de recolección esté funcionando.",
        )
    if ahora - ultima > timedelta(minutes=15):
        return salida(
            "sin_datos",
            "Hace más de 15 minutos que no recibimos datos. "
            "Abrí el programa de recolección para volver a medir el equipo.",
        )

    ahora_local = ahora.astimezone()
    detalles = []
    peor = "ok"

    for metrica, entrada in (baseline.get("metricas") or {}).items():
        if metrica not in metricas.UNIDADES:
            continue
        valores = por_metrica.get(metrica, [])[-5:]
        if not valores:
            continue

        aviso, rojo = limite_para(entrada, ahora_local)
        estado = estado_metrica(valores, aviso, rojo)

        # ---- Análisis predictivo por tendencia térmica ----
        if metrica in ("cpu_temp", "gpu_temp", "disk_temp"):
            prefijo = metrica.split("_")[0]  # cpu, gpu, disk
            metrica_trend = f"temp_trend_{prefijo}"
            pendiente_actual = float(entrada.get("pendiente") or 0.0)
            umbral_trend = metricas.PISOS_AVISO.get(metrica_trend)
            if umbral_trend is not None and pendiente_actual > 0:
                minutos_proj = tendencias.minutos_a_umbral(
                    valores[-1], pendiente_actual, rojo
                )
                if minutos_proj is not None and minutos_proj <= 30:
                    if estado == "ok":
                        estado = "atencion"
                    detalles_extra = {
                        "pendiente": round(pendiente_actual, 3),
                        "proyectado_min": round(minutos_proj, 1),
                    }
                    if detalles and detalles[-1]["metrica"] == metrica:
                        detalles[-1].update(detalles_extra)

        detalles.append(
            {
                "metrica": metrica,
                "nombre": metricas.NOMBRES.get(metrica, metrica),
                "unidad": metricas.UNIDADES[metrica],
                "estado": estado,
                "ultimo": valores[-1],
                "limite_aviso": aviso,
                "limite_rojo": rojo,
            }
        )
        if ORDEN[estado] > ORDEN[peor]:
            peor = estado

    if not detalles:
        return salida("sin_datos", "No pudimos leer los sensores de este equipo.")

    if peor == "ok":
        return salida(
            "ok", "Todo se ve dentro de lo normal para tu equipo.", detalles, ultima
        )

    problemas = [detalle for detalle in detalles if detalle["estado"] == peor]
    metrica_peor = problemas[0]["metrica"]
    titulo, consejo = MENSAJES.get(
        metrica_peor,
        (
            f"{metricas.NOMBRES.get(metrica_peor, metrica_peor)} está fuera de lo normal.",
            "Revisá el valor y el historial del equipo.",
        ),
    )
    return salida(peor, f"{titulo} {consejo}", detalles, ultima)


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(diagnosticar(), indent=2, ensure_ascii=False))
