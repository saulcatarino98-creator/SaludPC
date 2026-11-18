"""Tendencias: detecta si una métrica se va hacia un problema antes de llegar.

Calcula la pendiente (regresión lineal simple) de una serie de valores a lo
del tiempo y estima cuántos minutos faltan para cruzar un umbral de riesgo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# Umbral de pendiente preocupante: más de 0.2 °C por minuto sostenido
PENDIENTE_ALARMA = 0.2

# Horizonte de predicción: si se proyecta cruzar el umbral en menos de esto,
# se considera aviso predictivo.
HORIZONTE_MINUTOS = 30


def calcular_pendiente(
    valores: list[float], tiempos: list[datetime]
) -> float:
    """Regresión lineal simple: pendiente (unidad por minuto).

    `valores` y `tiempos` deben tener la misma longitud y estar ordenados.
    Retorna 0.0 si hay menos de 2 puntos o no se puede calcular.
    """
    if len(valores) < 2 or len(tiempos) < 2:
        return 0.0

    n = len(valores)
    # Convertimos tiempos a minutos relativos al primero
    t0 = tiempos[0]
    xs = [(t - t0).total_seconds() / 60.0 for t in tiempos]
    ys = valores

    media_x = sum(xs) / n
    media_y = sum(ys) / n

    num = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    den = sum((x - media_x) ** 2 for x in xs)

    if den == 0:
        return 0.0

    return num / den  # unidad por minuto


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


def analizar_tendencia(
    valores: list[float],
    tiempos: list[datetime],
    umbral: float,
    horizonte_minutos: int = HORIZONTE_MINUTOS,
) -> dict:
    """Devuelve un dict con pendiente, proyección y si hay alarma predictiva."""
    pendiente = calcular_pendiente(valores, tiempos)
    proyectado = minutos_a_umbral(
        valores[-1] if valores else 0.0, pendiente, umbral
    )

    alarma = False
    if pendiente > PENDIENTE_ALARMA and proyectado is not None:
        if 0 <= proyectado <= horizonte_minutos:
            alarma = True

    return {
        "pendiente": round(pendiente, 4),
        "minutos_a_umbral": (
            round(proyectado, 1) if proyectado is not None else None
        ),
        "alarma_predictiva": alarma,
    }
