"""Vigilante: convierte las mediciones en un diagnóstico en lenguaje simple."""

import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import almacen
import metricas
import rutas
import tendencias
from tendencias import (
    calcular_pendiente_con_confianza,
    prediccion_multi_horizonte,
    detectar_patron,
    calcular_score_riesgo,
    analisis_predictivo_completo,
)

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


def salida(estado, mensaje, detalles=None, ultima=None, riesgo=None):
    return {
        "estado": estado,
        "color": COLORES[estado],
        "mensaje": mensaje,
        "detalles": detalles or [],
        "ultima_lectura": ultima.isoformat() if ultima else None,
        "riesgo": riesgo,
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

        # ---- Análisis predictivo avanzado ----
        # Obtenemos tiempos para calcular tendencia con confianza
        desde = (ahora - timedelta(hours=6)).isoformat(timespec="seconds")
        tiempos_metrica = []
        for ts, met, valor, _ in almacen.leer(desde=desde):
            if met == metrica:
                try:
                    tiempos_metrica.append(datetime.fromisoformat(ts))
                except ValueError:
                    continue
        tiempos_metrica.sort()

        pred = analisis_predictivo_completo(
            valores, tiempos_metrica, aviso, rojo, valor_actual=valores[-1]
        )

        pendiente = pred["pendiente"]
        confianza = pred["confianza_r2"]

        # Si hay alarma predictiva inmediata, elevamos estado
        if pred["alarma_predictiva_inmediata"]:
            if estado == "ok":
                estado = "atencion"

        # Detectar patrones de riesgo
        patrones = pred["patrones"]

        detalles.append(
            {
                "metrica": metrica,
                "nombre": metricas.NOMBRES.get(metrica, metrica),
                "unidad": metricas.UNIDADES[metrica],
                "estado": estado,
                "ultimo": valores[-1],
                "limite_aviso": aviso,
                "limite_rojo": rojo,
                "pendiente": pendiente,
                "confianza": confianza,
                "minutos_a_aviso": pred["minutos_a_aviso"],
                "minutos_a_rojo": pred["minutos_a_rojo"],
                "horizonte": pred["horizonte"],
                "patrones": patrones,
                "alarma_predictiva": pred["alarma_predictiva_inmediata"],
            }
        )
        if ORDEN[estado] > ORDEN[peor]:
            peor = estado

    if not detalles:
        return salida("sin_datos", "No pudimos leer los sensores de este equipo.")

    # ---- Score de riesgo global del equipo ----
    riesgo = calcular_score_riesgo(detalles)

    if peor == "ok":
        mensaje_base = "Todo se ve dentro de lo normal para tu equipo."
    else:
        problemas = [d for d in detalles if d["estado"] == peor]
        metrica_peor = problemas[0]["metrica"]
        titulo, consejo = MENSAJES.get(
            metrica_peor,
            (
                f"{metricas.NOMBRES.get(metrica_peor, metrica_peor)} está fuera de lo normal.",
                "Revisá el valor y el historial del equipo.",
            ),
        )
        mensaje_base = f"{titulo} {consejo}"

    # Agregar información de riesgo global al mensaje si es medio o superior
    if riesgo["nivel"] in ("alto", "critico"):
        mensaje_base += (
            f" Score de riesgo del equipo: {riesgo['score']}/100 ({riesgo['nivel']})."
        )

    return salida(
        peor,
        mensaje_base,
        detalles,
        ultima,
        riesgo=riesgo,
    )


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(diagnosticar(), indent=2, ensure_ascii=False))
