"""Historial: explica en lenguaje simple las pausas y los avisos del equipo."""

import json
import logging
from datetime import datetime, timezone

import psutil

import almacen
import metricas
import rutas

log = logging.getLogger("salud.eventos")

# Un hueco menor a esto es solo una medición que se demoró.
PAUSA_MINIMA_MINUTOS = 3

# Un pico solo se guarda si el equipo estuvo fuera de lo normal este tiempo.
# Así el historial no se llena de eventos de un minuto.
MINUTOS_PICO = 5

# Si el servicio estuvo detenido más que esto, un episodio abierto ya no se
# puede cerrar con una duración real: se descarta.
MINUTOS_REANUDAR = 15

METRICAS_TERMICAS = frozenset({"cpu_temp", "gpu_temp", "disk_temp"})

TONOS = {
    "suspension": "neutral",
    "apagado": "neutral",
    "normal": "ok",
    "estado": "atencion",
    "pico": "atencion",
}

CATEGORIAS = {
    "todos": "Todos",
    "energia": "Energía",
    "carga": "Carga",
    "termicas": "Térmicas",
}


def _datos(detalle):
    """JSON del detalle, sin romper si viene vacío o mal formado."""
    try:
        datos = json.loads(detalle)
    except (TypeError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def categoria(tipo, detalle=""):
    """Clasifica un evento para los filtros del historial.

    Energía son las pausas del equipo (suspensión y apagado). Carga reúne el
    uso de procesador, memoria, disco y tarjeta gráfica; térmicas, las
    temperaturas. Los avisos y picos heredan la categoría de su métrica.
    """
    if tipo in ("suspension", "apagado"):
        return "energia"
    if tipo in ("estado", "pico"):
        metrica = _datos(detalle).get("metrica")
        return "termicas" if metrica in METRICAS_TERMICAS else "carga"
    return "carga"


def _valor(valor, metrica):
    unidad = metricas.UNIDADES.get(metrica, "")
    return f"{valor:.0f} {unidad}".strip()


def registrar(tipo, detalle="", valor=None, ts=None):
    almacen.registrar_evento(tipo, detalle, valor, ts)


def duracion(minutos):
    """'2 horas 15 minutos' en vez de '135 minutos'."""
    minutos = max(1, int(round(minutos)))
    if minutos < 60:
        return f"{minutos} minuto{'s' if minutos != 1 else ''}"
    horas, resto = divmod(minutos, 60)
    if horas < 24:
        texto = f"{horas} hora{'s' if horas != 1 else ''}"
        if resto >= 5:
            texto += f" {resto} minutos"
        return texto
    dias, resto_horas = divmod(horas, 24)
    texto = f"{dias} día{'s' if dias != 1 else ''}"
    if resto_horas:
        texto += f" {resto_horas} hora{'s' if resto_horas != 1 else ''}"
    return texto


def registrar_pausa(minutos, ultima_marca):
    """Distingue una suspensión de un apagado comparando con el arranque de Windows."""
    try:
        arranque = datetime.fromtimestamp(psutil.boot_time(), timezone.utc)
    except Exception:
        arranque = None
    reinicio = arranque is not None and ultima_marca < arranque
    tipo = "apagado" if reinicio else "suspension"
    registrar(tipo, valor=round(float(minutos), 1))
    return tipo


def registrar_estado(estado, metrica):
    detalle = json.dumps(
        {"estado": estado, "metrica": metrica}, ensure_ascii=False
    )
    registrar("estado", detalle)


def ultimo_estado():
    """Último estado registrado, para no repetir el mismo aviso al reiniciar."""
    for _ts, tipo, detalle, _valor in almacen.leer_eventos(limite=50):
        if tipo == "normal":
            return "ok"
        if tipo == "estado":
            try:
                return json.loads(detalle).get("estado")
            except (TypeError, ValueError):
                continue
    return None


# El servicio es quien muestra el aviso, aunque el panel esté cerrado. Este
# archivo recuerda el último estado avisado para no repetirlo en cada arranque.
ORDEN_AVISO = {
    "ok": 0,
    "sin_datos": 0,
    "aprendiendo": 0,
    "atencion": 1,
    "accion": 2,
}


def _ruta_aviso():
    return rutas.carpeta_datos() / "ultimo_estado_aviso.json"


def estado_avisado():
    """Último estado que el servicio tomó como referencia, o None."""
    try:
        datos = json.loads(_ruta_aviso().read_text(encoding="utf-8"))
        return datos.get("estado")
    except (OSError, ValueError):
        return None


def debe_avisar(estado, anterior):
    """Solo se avisa cuando el estado empeora, no cuando mejora."""
    return ORDEN_AVISO.get(estado, 0) > ORDEN_AVISO.get(anterior, 0)


def marcar_estado_aviso(estado, metrica=None):
    """Guarda el estado de referencia después de avisar (o de una mejora)."""
    ruta = _ruta_aviso()
    temporal = ruta.with_suffix(".tmp")
    datos = {
        "estado": estado,
        "metrica": metrica,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        temporal.write_text(
            json.dumps(datos, ensure_ascii=False), encoding="utf-8"
        )
        temporal.replace(ruta)
    except OSError:
        log.exception("No se pudo guardar el estado del último aviso")


def _ruta_episodios():
    return rutas.carpeta_datos() / "episodios_abiertos.json"


def _leer_abiertos(ahora=None):
    """Episodios que seguían abiertos cuando el servicio se detuvo."""
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    try:
        datos = json.loads(_ruta_episodios().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(datos, dict):
        return {}

    abiertos = {}
    for metrica, item in datos.items():
        if not isinstance(item, dict):
            continue
        try:
            ultimo = datetime.fromisoformat(item["ultimo"])
        except (KeyError, ValueError, TypeError):
            continue
        if ultimo.tzinfo is None:
            ultimo = ultimo.replace(tzinfo=timezone.utc)
        if (ahora - ultimo).total_seconds() > MINUTOS_REANUDAR * 60:
            log.info(
                "Episodio de %s descartado: el servicio estuvo detenido", metrica
            )
            continue
        abiertos[metrica] = item
    return abiertos


def _guardar_abiertos(abiertos):
    ruta = _ruta_episodios()
    temporal = ruta.with_suffix(".tmp")
    try:
        temporal.write_text(json.dumps(abiertos, ensure_ascii=False), encoding="utf-8")
        temporal.replace(ruta)
    except OSError:
        log.exception("No se pudieron guardar los episodios abiertos")


def _cerrar_episodio(metrica, datos, fin):
    """Convierte un episodio abierto en evento si duró lo suficiente."""
    try:
        inicio = datetime.fromisoformat(datos["inicio"])
    except (KeyError, ValueError, TypeError):
        return None
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)

    minutos = (fin - inicio).total_seconds() / 60
    if minutos < MINUTOS_PICO:
        return None

    maximo = float(datos.get("maximo") or 0.0)
    detalle = {
        "metrica": metrica,
        "inicio": inicio.isoformat(timespec="seconds"),
        "fin": fin.isoformat(timespec="seconds"),
        "maximo": round(maximo, 1),
        "duracion": round(minutos, 1),
        "limite_aviso": datos.get("limite_aviso"),
        "limite_rojo": datos.get("limite_rojo"),
        "estado": datos.get("estado"),
    }
    registrar(
        "pico",
        json.dumps(detalle, ensure_ascii=False),
        maximo,
        ts=detalle["inicio"],
    )
    return detalle


def actualizar_episodios(diagnostico, ahora=None):
    """Abre, mantiene y cierra episodios de pico por métrica.

    Se llama una vez por minuto, después de diagnosticar. Un episodio empieza
    cuando la métrica entra en atención o acción y termina cuando deja de
    estarlo. Solo se guarda si duró MINUTOS_PICO o más.
    """
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)

    abiertos = _leer_abiertos(ahora)
    detalles = {
        dato.get("metrica"): dato
        for dato in diagnostico.get("detalles", [])
        if dato.get("metrica")
    }
    cerrados = []

    for metrica in list(abiertos):
        datos = abiertos[metrica]
        actual = detalles.get(metrica)
        en_alerta = actual is not None and actual.get("estado") in (
            "atencion",
            "accion",
        )
        if not en_alerta:
            cerrado = _cerrar_episodio(metrica, datos, ahora)
            if cerrado:
                cerrados.append(cerrado)
            del abiertos[metrica]
            continue

        datos["ultimo"] = ahora.isoformat(timespec="seconds")
        valor = actual.get("ultimo")
        if valor is not None:
            datos["maximo"] = max(float(datos.get("maximo") or 0.0), float(valor))
        datos["estado"] = actual.get("estado")
        if actual.get("limite_aviso") is not None:
            datos["limite_aviso"] = actual["limite_aviso"]
        if actual.get("limite_rojo") is not None:
            datos["limite_rojo"] = actual["limite_rojo"]

    for metrica, actual in detalles.items():
        if metrica in abiertos:
            continue
        if actual.get("estado") not in ("atencion", "accion"):
            continue
        marca = ahora.isoformat(timespec="seconds")
        abiertos[metrica] = {
            "inicio": marca,
            "ultimo": marca,
            "maximo": float(actual.get("ultimo") or 0.0),
            "limite_aviso": actual.get("limite_aviso"),
            "limite_rojo": actual.get("limite_rojo"),
            "estado": actual.get("estado"),
        }

    _guardar_abiertos(abiertos)
    return cerrados


def describir(ts, tipo, detalle, valor):
    """Devuelve (titulo, texto, tono) listo para mostrar."""
    if tipo == "suspension":
        return (
            "Equipo suspendido",
            f"Estuvo {duracion(valor or 0)} en reposo. Es normal si cerraste la "
            "tapa o lo dejaste suspendido.",
            "neutral",
        )

    if tipo == "apagado":
        if valor and valor >= 20:
            return (
                "Equipo apagado",
                f"Estuvo apagado {duracion(valor)}. Mientras está apagado no se "
                "toman mediciones.",
                "neutral",
            )
        return (
            "Equipo reiniciado",
            "Se reinició y el programa volvió a arrancar solo.",
            "neutral",
        )

    if tipo == "pico":
        datos = _datos(detalle)
        metrica = datos.get("metrica")
        nombre = metricas.NOMBRES.get(metrica, "el equipo")
        nombre = nombre[0].upper() + nombre[1:] if nombre else "El equipo"
        maxima = datos.get("maximo")
        limite = datos.get("limite_aviso")
        limite_rojo = datos.get("limite_rojo")
        titulo = (
            "Pico de temperatura"
            if metrica in METRICAS_TERMICAS
            else "Pico de carga"
        )
        texto = (
            f"{nombre} estuvo {duracion(datos.get('duracion') or 0)} "
            "por encima de lo habitual."
        )
        if maxima is not None:
            texto += f" Máximo: {_valor(maxima, metrica)}."
        if limite is not None:
            texto += f" Normal hasta {_valor(limite, metrica)}."
        tono = (
            "accion"
            if maxima is not None
            and limite_rojo is not None
            and maxima >= limite_rojo
            else "atencion"
        )
        return titulo, texto, tono

    if tipo == "normal":
        return (
            "Volvió a la normalidad",
            "Los valores regresaron a lo habitual para este equipo.",
            "ok",
        )

    if tipo == "estado":
        try:
            datos = json.loads(detalle)
        except (TypeError, ValueError):
            datos = {}
        estado = datos.get("estado") or "atencion"
        metrica = datos.get("metrica")
        frase = metricas.NOMBRES.get(metrica, "el equipo")
        frase = frase[0].upper() + frase[1:] if frase else "El equipo"
        if estado == "accion":
            return (
                "Aviso rojo",
                f"{frase} llegó a un nivel que conviene revisar.",
                "accion",
            )
        return (
            "Aviso amarillo",
            f"{frase} se salió de lo normal para este equipo.",
            "atencion",
        )

    return (tipo.capitalize(), detalle or "", TONOS.get(tipo, "neutral"))
