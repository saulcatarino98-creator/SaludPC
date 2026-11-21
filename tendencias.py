"""Tendencias y predictibilidad: detecta si una métrica se va hacia un problema
antes de llegar, calcula riesgo y estima tiempo hasta falla.

Funciones incluidas:
- Regresión lineal simple con coeficiente de determinación (R²) para medir confianza.
- Estimación de minutos hasta cruzar umbral (tiempo hasta falla proyectado).
- Detección de anomalías por z-score (desviación estándar respecto al baseline).
- Score de riesgo global del equipo combinando múltiples métricas.
- Detección de patrones: subidas repentinas, oscilaciones, estancamiento.
- Predicción multi-horizonte: corto (30 min), medio (2 h), largo (24 h).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

# --------------------------------------------------------------------------- #
# Constantes de umbral
# --------------------------------------------------------------------------- #

# Pendiente preocupante: más de 0.2 °C por minuto sostenido (térmicas)
PENDIENTE_ALARMA = 0.2

# Horizonte de predicción corto (minutos)
HORIZONTE_CORTO_MIN = 30

# Horizonte medio (horas)
HORIZONTE_MEDIO_HORAS = 2

# Horizonte largo (horas)
HORIZONTE_LARGO_HORAS = 24

# Umbral z-score para considerar un valor como anomalía (desviaciones estándar)
Z_SCORE_ALERTA = 2.5

# Pesos por categoría para el score de riesgo global
PESO_RIESGO = {
    "cpu_temp": 0.20,
    "gpu_temp": 0.20,
    "disk_temp": 0.15,
    "cpu_load": 0.15,
    "ram_load": 0.10,
    "disk_used_pct": 0.10,
    "fan_cpu_rpm": 0.05,
    "fan_chasis_rpm": 0.03,
    "fan_gpu_rpm": 0.02,
    "psu_12v": 0.03,
    "psu_5v": 0.02,
    "psu_3v3": 0.02,
    "disk_smart_health": 0.05,
    "disk_smart_temp": 0.05,
}

# --------------------------------------------------------------------------- #
# Regresión lineal con R²
# --------------------------------------------------------------------------- #


def calcular_pendiente_con_confianza(
    valores: list[float], tiempos: list[datetime]
) -> dict:
    """Regresión lineal simple con coeficiente de determinación (R²).

    Devuelve dict con:
      - pendiente: unidad por minuto
      - r2: confianza del ajuste (0 a 1, 1 = perfecto)
      - intercepto: valor en t=0
      - n: cantidad de puntos usados
    """
    if len(valores) < 2 or len(tiempos) < 2:
        return {"pendiente": 0.0, "r2": 0.0, "intercepto": 0.0, "n": len(valores)}

    n = len(valores)
    t0 = tiempos[0]
    xs = [(t - t0).total_seconds() / 60.0 for t in tiempos]
    ys = valores

    media_x = sum(xs) / n
    media_y = sum(ys) / n

    num = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    den = sum((x - media_x) ** 2 for x in xs)

    if den == 0:
        return {"pendiente": 0.0, "r2": 0.0, "intercepto": media_y, "n": n}

    pendiente = num / den
    intercepto = media_y - pendiente * media_x

    # R² = 1 - SS_res / SS_tot
    ss_res = sum(
        (y - (pendiente * x + intercepto)) ** 2 for x, y in zip(xs, ys)
    )
    ss_tot = sum((y - media_y) ** 2 for y in ys)

    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))  # acotar a [0, 1]

    return {
        "pendiente": round(pendiente, 4),
        "r2": round(r2, 4),
        "intercepto": round(intercepto, 4),
        "n": n,
    }


def minutos_a_umbral(
    valor_actual: float, pendiente: float, umbral: float
) -> Optional[float]:
    """Si la tendencia es al alza, cuántos minutos faltan para llegar al umbral.

    Retorna None si la pendiente es nula o negativa, o si ya se superó el umbral.
    """
    if pendiente <= 0:
        return None
    if valor_actual >= umbral:
        return 0.0
    return (umbral - valor_actual) / pendiente


# --------------------------------------------------------------------------- #
# Detección de anomalías (z-score)
# --------------------------------------------------------------------------- #


def calcular_zscore(valor: float, media: float, desviacion: float) -> float:
    """Cuántas desviaciones estándar está el valor respecto a la media."""
    if desviacion == 0:
        return 0.0
    return (valor - media) / desviacion


def es_anomalia(valor: float, media: float, desviacion: float, umbral_z: float = Z_SCORE_ALERTA) -> bool:
    """True si el valor está más de `umbral_z` desviaciones estándar de la media."""
    return abs(calcular_zscore(valor, media, desviacion)) >= umbral_z


# --------------------------------------------------------------------------- #
# Predicción multi-horizonte
# --------------------------------------------------------------------------- #


def predecir_valor_en(
    valor_actual: float, pendiente: float, minutos_desde_ahora: int
) -> float:
    """Proyecta el valor dentro de X minutos asumiendo la pendiente actual."""
    return valor_actual + pendiente * minutos_desde_ahora


def prediccion_multi_horizonte(
    valor_actual: float,
    pendiente: float,
    umbral_aviso: float,
    umbral_rojo: float,
) -> dict:
    """Devuelve proyección a corto, medio y largo plazo con estados estimados."""
    ahora = datetime.now(timezone.utc)

    horizons = {
        "corto": {"min": HORIZONTE_CORTO_MIN, "label": "30 min"},
        "medio": {"min": HORIZONTE_MEDIO_HORAS * 60, "label": "2 h"},
        "largo": {"min": HORIZONTE_LARGO_HORAS * 60, "label": "24 h"},
    }

    resultado = {}
    for clave, info in horizons.items():
        min_proj = info["min"]
        valor_proj = predecir_valor_en(valor_actual, pendiente, min_proj)

        if valor_proj >= umbral_rojo:
            estado_proj = "accion"
        elif valor_proj >= umbral_aviso:
            estado_proj = "atencion"
        else:
            estado_proj = "ok"

        minutos_a_rojo = minutos_a_umbral(valor_actual, pendiente, umbral_rojo)
        minutos_a_aviso = minutos_a_umbral(valor_actual, pendiente, umbral_aviso)

        resultado[clave] = {
            "label": info["label"],
            "minutos": min_proj,
            "valor_proyectado": round(valor_proj, 2),
            "estado_estimado": estado_proj,
            "minutos_a_aviso": (
                round(minutos_a_aviso, 1) if minutos_a_aviso is not None else None
            ),
            "minutos_a_rojo": (
                round(minutos_a_rojo, 1) if minutos_a_rojo is not None else None
            ),
            "fecha_estimada": (
                (ahora + timedelta(minutes=min_proj)).isoformat(timespec="seconds")
                if pendiente > 0
                else None
            ),
        }

    return resultado


# --------------------------------------------------------------------------- #
# Detección de patrones
# --------------------------------------------------------------------------- #


def detectar_patron(
    valores: list[float], tiempos: list[datetime]
) -> dict:
    """Analiza la serie reciente para detectar patrones de riesgo.

    Patrones detectados:
      - subida_repentina: último valor muy superior al promedio previo
      - oscilacion: valores suben y bajan bruscamente
      - estancamiento: valores casi constantes (posible sensor bloqueado)
      - tendencia_al_alta: pendiente positiva sostenida
    """
    if len(valores) < 3:
        return {"patrones": [], "confianza": 0.0}

    patrones = []
    n = len(valores)

    # Último vs promedio de los anteriores
    previo = sum(valores[:-1]) / (n - 1)
    ultimo = valores[-1]
    if previo > 0:
        subida_pct = (ultimo - previo) / previo * 100
        if subida_pct > 20:
            patrones.append(
                {
                    "tipo": "subida_repentina",
                    "descripcion": f"Subida del {subida_pct:.0f}% respecto al promedio previo",
                    "severidad": "alta" if subida_pct > 50 else "media",
                }
            )

    # Oscilación: varianza alta relativa a la media
    media = sum(valores) / n
    if media != 0:
        varianza = sum((v - media) ** 2 for v in valores) / n
        coef_var = (varianza ** 0.5) / abs(media)
        if coef_var > 0.3:
            patrones.append(
                {
                    "tipo": "oscilacion",
                    "descripcion": f"Variabilidad alta (coeficiente de variación {coef_var:.2f})",
                    "severidad": "media",
                }
            )

    # Estancamiento: pendiente cercana a cero con pocos cambios
    if len(tiempos) >= 2:
        t0 = tiempos[0]
        xs = [(t - t0).total_seconds() / 60.0 for t in tiempos]
        den = sum((x - sum(xs) / n) ** 2 for x in xs)
        if den > 0:
            pendiente = sum(
                (x - sum(xs) / n) * (v - media) for x, v in zip(xs, valores)
            ) / den
            if abs(pendiente) < 0.01 and n >= 5:
                patrones.append(
                    {
                        "tipo": "estancamiento",
                        "descripcion": "Valores casi constantes (posible sensor bloqueado)",
                        "severidad": "baja",
                    }
                )

    # Tendencia al alza sostenida
    reg = calcular_pendiente_con_confianza(valores, tiempos)
    if reg["pendiente"] > 0 and reg["r2"] > 0.6:
        patrones.append(
            {
                "tipo": "tendencia_al_alta",
                "descripcion": f"Tendencia ascendente sostenida (R²={reg['r2']:.2f})",
                "severidad": "alta" if reg["r2"] > 0.8 else "media",
            }
        )

    confianza = min(1.0, len(patrones) / 3.0)
    return {"patrones": patrones, "confianza": round(confianza, 2)}


# --------------------------------------------------------------------------- #
# Score de riesgo global
# --------------------------------------------------------------------------- #


def calcular_score_riesgo(detalles: list[dict]) -> dict:
    """Combina múltiples métricas en un score de riesgo global (0 a 100).

    `detalles` es una lista de dicts con claves: metrica, estado, ultimo,
    limite_aviso, limite_rojo, pendiente (opcional).
    """
    score = 0.0
    peso_total = 0.0
    contribuciones = []

    for detalle in detalles:
        metrica = detalle["metrica"]
        peso = PESO_RIESGO.get(metrica, 0.01)
        peso_total += peso

        estado = detalle.get("estado", "ok")
        valor = detalle.get("ultimo", 0)
        aviso = detalle.get("limite_aviso")
        rojo = detalle.get("limite_rojo")
        pendiente = detalle.get("pendiente", 0) or 0

        # Puntuación base por estado
        if estado == "accion":
            pts = 100
        elif estado == "atencion":
            pts = 60
        elif estado == "ok":
            pts = 0
        else:
            pts = 20  # sin_datos / aprendiendo

        # Bonificación por pendiente positiva (riesgo creciente)
        if pendiente > 0:
            pts = min(100, pts + abs(pendiente) * 20)

        # Bonificación si está cerca del rojo
        if rojo and aviso and valor > aviso:
            cercania = (valor - aviso) / (rojo - aviso) if rojo > aviso else 0
            pts = min(100, pts + cercania * 30)

        score += pts * peso
        contribuciones.append(
            {
                "metrica": metrica,
                "peso": peso,
                "puntos": round(pts, 1),
                "contribucion": round(pts * peso, 2),
            }
        )

    score_global = round(score / peso_total if peso_total > 0 else 0, 1)

    if score_global >= 70:
        nivel = "critico"
    elif score_global >= 40:
        nivel = "alto"
    elif score_global >= 20:
        nivel = "medio"
    else:
        nivel = "bajo"

    return {
        "score": score_global,
        "nivel": nivel,
        "contribuciones": sorted(
            contribuciones, key=lambda c: c["contribucion"], reverse=True
        ),
    }


# --------------------------------------------------------------------------- #
# Análisis completo predictivo
# --------------------------------------------------------------------------- #


def analisis_predictivo_completo(
    valores: list[float],
    tiempos: list[datetime],
    umbral_aviso: float,
    umbral_rojo: float,
    valor_actual: Optional[float] = None,
) -> dict:
    """Ejecuta todos los análisis predictivos para una métrica.

    Devuelve un dict con pendiente, confianza, proyección multi-horizonte,
    patrones detectados y si hay alarma predictiva inmediata.
    """
    if valor_actual is None:
        valor_actual = valores[-1] if valores else 0.0

    reg = calcular_pendiente_con_confianza(valores, tiempos)
    pendiente = reg["pendiente"]
    r2 = reg["r2"]

    # Minutos hasta umbrales
    min_a_aviso = minutos_a_umbral(valor_actual, pendiente, umbral_aviso)
    min_a_rojo = minutos_a_umbral(valor_actual, pendiente, umbral_rojo)

    # Proyección multi-horizonte
    horizonte = prediccion_multi_horizonte(
        valor_actual, pendiente, umbral_aviso, umbral_rojo
    )

    # Patrones
    patrones = detectar_patron(valores, tiempos)

    # Alarma predictiva inmediata (corto plazo)
    alarma_inmediata = False
    if pendiente > PENDIENTE_ALARMA and r2 > 0.5:
        if min_a_rojo is not None and 0 <= min_a_rojo <= HORIZONTE_CORTO_MIN:
            alarma_inmediata = True

    return {
        "valor_actual": round(valor_actual, 2),
        "pendiente": pendiente,
        "confianza_r2": r2,
        "minutos_a_aviso": round(min_a_aviso, 1) if min_a_aviso is not None else None,
        "minutos_a_rojo": round(min_a_rojo, 1) if min_a_rojo is not None else None,
        "alarma_predictiva_inmediata": alarma_inmediata,
        "horizonte": horizonte,
        "patrones": patrones["patrones"],
        "confianza_patrones": patrones["confianza"],
    }
