"""Cerebro: calcula qué es normal para este equipo y genera el baseline."""

import json
import logging
import math
import socket
from datetime import datetime

import pandas as pd

import almacen
import metricas
import rutas
import tendencias

log = logging.getLogger("salud.cerebro")

MIN_DIAS = 3
MIN_MUESTRAS = 300   # fotos distintas del equipo (una por minuto)
MIN_GLOBAL = 100     # valores mínimos por métrica
MIN_FRANJA = 30      # valores mínimos dentro de una franja horaria


def numero_json(valor):
    """Convierte NaN/inf en None para que el JSON sea válido."""
    if valor is None:
        return None
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return None
    return valor if math.isfinite(valor) else None


def resumen(serie, tiempos=None):
    resultado = {
        "n": int(serie.count()),
        "mediana": float(serie.median()),
        "p95": float(serie.quantile(0.95)),
        "p99": float(serie.quantile(0.99)),
        "max": float(serie.max()),
    }
    if tiempos is not None and len(tiempos) == len(serie):
        ajuste = tendencias.calcular_pendiente_con_confianza(
            [float(v) for v in serie], tiempos
        )
        resultado["pendiente"] = ajuste["pendiente"]
    else:
        resultado["pendiente"] = 0.0
    return resultado


def limite_aviso(p95, metrica):
    """Límite personal, sin bajar del piso sano ni pasar el techo de riesgo."""
    techo = metricas.TECHOS_ROJO[metrica]
    piso = metricas.PISOS_AVISO[metrica]
    return min(max(p95 * 1.10, piso), techo * 0.95)


def _filas_a_dataframe(filas):
    """Convierte filas de almacen.leer() a DataFrame con ts local y valor numérico."""
    df = pd.DataFrame(filas, columns=["ts", "metrica", "valor", "unidad"])
    if df.empty:
        return df
    local = datetime.now().astimezone().tzinfo
    df["ts"] = (
        pd.to_datetime(df["ts"], errors="coerce", utc=True)
        .dt.tz_convert(local)
        .dt.tz_localize(None)
    )
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["ts", "valor"])
    df = df[df["valor"].map(math.isfinite)]
    return df


def _resumen_diario_a_dataframe():
    """Reconstruye valores aproximados desde resumen_diario para días ya comprimidos.

    Cada fila del resumen representa n mediciones de un día. Se repite el
    promedio diario n veces para disponer de suficientes puntos y calcular
    percentiles del baseline. No es exacto, pero evita perder todo el
    histórico tras la retención de 90 días.
    """
    filas = almacen.leer_resumen_diario()
    if not filas:
        return pd.DataFrame(columns=["ts", "metrica", "valor", "unidad"])

    registros = []
    for dia, metrica, n, minimo, promedio, maximo in filas:
        if n is None or n <= 0:
            continue
        valor_referencia = promedio if promedio is not None else (
            (minimo + maximo) / 2 if minimo is not None and maximo is not None else None
        )
        if valor_referencia is None:
            continue
        # Un registro por día (usamos el promedio como valor representativo);
        # el conteo n se considera al calcular el baseline.
        registros.append(
            {
                "ts": pd.Timestamp(f"{dia} 12:00:00"),
                "metrica": metrica,
                "valor": float(valor_referencia),
                "unidad": "",
                "_n": int(n),
            }
        )

    if not registros:
        return pd.DataFrame(columns=["ts", "metrica", "valor", "unidad"])

    df = pd.DataFrame(registros)
    return df


def leer_historial():
    filas = almacen.leer()
    df_detallado = _filas_a_dataframe(filas)

    # Incorporar resumen diario para días ya comprimidos por la retención.
    df_resumen = _resumen_diario_a_dataframe()
    if not df_resumen.empty:
        # Ajustar el peso de cada fila del resumen por su conteo n: repetir
        # el promedio tantas veces como indique n para calcular percentiles.
        partes = [df_detallado] if not df_detallado.empty else []
        filas_expandidas = []
        for _, fila in df_resumen.iterrows():
            n = int(fila.get("_n", 1) or 1)
            for _ in range(max(1, min(n, 1440))):  # tope razonable por día
                filas_expandidas.append(
                    {
                        "ts": fila["ts"],
                        "metrica": fila["metrica"],
                        "valor": fila["valor"],
                        "unidad": fila.get("unidad", ""),
                    }
                )
        if filas_expandidas:
            df_expandido = pd.DataFrame(filas_expandidas)
            partes.append(df_expandido)
        if partes:
            df = pd.concat(partes, ignore_index=True)
        else:
            df = df_detallado
    else:
        df = df_detallado

    if df.empty:
        return df, 0, 0

    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["ts", "valor"])
    df = df[df["valor"].map(math.isfinite)]

    dias = int(df["ts"].dt.date.nunique()) if not df.empty else 0
    muestras = int(df["ts"].nunique()) if not df.empty else 0
    return df, dias, muestras


def calcular_metricas(df):
    resultado = {}
    for metrica, grupo in df.groupby("metrica"):
        if metrica not in metricas.TECHOS_ROJO or len(grupo) < MIN_GLOBAL:
            continue

        global_ = resumen(grupo["valor"], grupo["ts"].tolist())
        datos = {
            "unidad": metricas.UNIDADES[metrica],
            "n": global_["n"],
            "mediana": numero_json(global_["mediana"]),
            "p95": numero_json(global_["p95"]),
            "p99": numero_json(global_["p99"]),
            "max": numero_json(global_["max"]),
            "pendiente": numero_json(global_["pendiente"]),
            "limite_aviso": numero_json(limite_aviso(global_["p95"], metrica)),
            "limite_rojo": numero_json(metricas.TECHOS_ROJO[metrica]),
            "franjas": {},
        }

        for franja, sub in grupo.groupby("franja"):
            if len(sub) < MIN_FRANJA:
                continue
            fs = resumen(sub["valor"], sub["ts"].tolist())
            datos["franjas"][franja] = {
                "n": fs["n"],
                "mediana": numero_json(fs["mediana"]),
                "p95": numero_json(fs["p95"]),
                "limite_aviso": numero_json(
                    limite_aviso(fs["p95"], metrica)
                ),
            }
        resultado[metrica] = datos
    return resultado


def main():
    almacen.crear()
    # Mientras aprende alcanza con los conteos: es una consulta agregada y
    # permite refrescar el avance sin cargar 90 días de historial en memoria.
    dias, muestras = almacen.contar_dias_muestras()
    aprendiendo = muestras < MIN_MUESTRAS or dias < MIN_DIAS

    resultado = {}
    if not aprendiendo:
        df, dias, muestras = leer_historial()
        aprendiendo = muestras < MIN_MUESTRAS or dias < MIN_DIAS
        if not df.empty and not aprendiendo:
            df["hora"] = df["ts"].dt.hour
            # pandas 3 usa day_of_week; en versiones anteriores se llama dayofweek
            dias_semana = (
                df["ts"].dt.day_of_week
                if hasattr(df["ts"].dt, "day_of_week")
                else df["ts"].dt.dayofweek
            )
            df["tipo_dia"] = (
                dias_semana.lt(5).map({True: "laboral", False: "finde"})
            )
            df["franja"] = df["tipo_dia"] + "_" + df["hora"].astype(str)
            resultado = calcular_metricas(df)

    hostname = socket.gethostname()
    baseline = {
        "version": 2,
        "equipo": hostname,
        "huella": almacen.huella_equipo(),
        "generado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
        "aprendiendo": bool(aprendiendo or not resultado),
        "dias": dias,
        "muestras": muestras,
        "metricas": resultado,
    }

    ruta = rutas.carpeta_datos() / f"baseline_{hostname}.json"
    temporal = ruta.with_name(ruta.name + ".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(baseline, archivo, indent=2, ensure_ascii=False)
    temporal.replace(ruta)

    log.info("Baseline v2 guardado en %s", ruta)
    log.info(
        "Días con datos: %s | Fotos del equipo: %s | Aprendiendo: %s",
        dias,
        muestras,
        baseline["aprendiendo"],
    )
    for metrica, datos in resultado.items():
        log.info(
            "%s: aviso=%s%s rojo=%s%s (n=%s)",
            metrica,
            datos["limite_aviso"],
            datos["unidad"],
            datos["limite_rojo"],
            datos["unidad"],
            datos["n"],
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
