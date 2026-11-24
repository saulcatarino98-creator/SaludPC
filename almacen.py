"""Almacen local de mediciones (SQLite).

Reemplaza el CSV: crece lento, se puede consultar por fecha y no hay que
releer todo el historial para calcular un promedio.
"""

import math
import sqlite3
from datetime import datetime, timedelta, timezone

import rutas

RUTA_DB = rutas.carpeta_datos() / "salud.db"
RETENCION_DIAS = 90

_esquema_listo = False


def conectar():
    conexion = sqlite3.connect(RUTA_DB, timeout=10)
    conexion.execute("PRAGMA synchronous=NORMAL")
    return conexion


def crear():
    """Crea la base y la tabla. Solo hace trabajo la primera vez del proceso."""
    global _esquema_listo
    if _esquema_listo:
        return
    conexion = conectar()
    try:
        conexion.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS muestras (
                ts      TEXT  NOT NULL,   -- fecha y hora en UTC, formato ISO 8601
                metrica TEXT  NOT NULL,
                valor   REAL  NOT NULL,
                unidad  TEXT  NOT NULL,
                PRIMARY KEY (ts, metrica)
            );
            CREATE INDEX IF NOT EXISTS idx_muestras
                ON muestras (metrica, ts);
            CREATE TABLE IF NOT EXISTS resumen_diario (
                dia      TEXT NOT NULL,   -- YYYY-MM-DD
                metrica  TEXT NOT NULL,
                n        INTEGER NOT NULL,
                minimo   REAL,
                promedio REAL,
                maximo   REAL,
                PRIMARY KEY (dia, metrica)
            );
            CREATE TABLE IF NOT EXISTS eventos (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT NOT NULL,   -- fecha y hora en UTC, formato ISO 8601
                tipo    TEXT NOT NULL,   -- suspension, apagado, estado, normal, pico
                detalle TEXT NOT NULL DEFAULT '',
                valor   REAL
            );
            CREATE INDEX IF NOT EXISTS idx_eventos ON eventos (ts);
            """
        )
        conexion.commit()
        _esquema_listo = True
    finally:
        conexion.close()


def guardar(ts, valores):
    """Guarda una foto del equipo. `valores` = {metrica: (valor, unidad)}."""
    filas = [
        (ts, metrica, float(valor), unidad)
        for metrica, (valor, unidad) in valores.items()
        if valor is not None and math.isfinite(float(valor))
    ]
    if not filas:
        return 0
    crear()
    conexion = conectar()
    try:
        conexion.executemany(
            "INSERT OR REPLACE INTO muestras (ts, metrica, valor, unidad) "
            "VALUES (?, ?, ?, ?)",
            filas,
        )
        conexion.commit()
    finally:
        conexion.close()
    return len(filas)


def resumir_y_limpiar(hoy=None):
    """Resume los días completos que salen de la ventana y borra su detalle.

    Nunca corta un día a la mitad: por eso el corte es una fecha entera.
    Primero guarda el resumen y recién después borra, todo en una transacción.
    """
    crear()
    hoy = hoy or datetime.now(timezone.utc)
    corte = (hoy.date() - timedelta(days=RETENCION_DIAS)).isoformat()
    resumidos = 0
    conexion = conectar()
    try:
        dias = [
            fila[0]
            for fila in conexion.execute(
                "SELECT DISTINCT substr(ts, 1, 10) FROM muestras "
                "WHERE substr(ts, 1, 10) < ? ORDER BY 1",
                (corte,),
            )
        ]
        for dia in dias:
            filas = conexion.execute(
                "SELECT metrica, COUNT(*), MIN(valor), AVG(valor), MAX(valor) "
                "FROM muestras WHERE substr(ts, 1, 10) = ? GROUP BY metrica",
                (dia,),
            ).fetchall()
            conexion.executemany(
                "INSERT OR REPLACE INTO resumen_diario "
                "(dia, metrica, n, minimo, promedio, maximo) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(dia,) + tuple(fila) for fila in filas],
            )
        if dias:
            conexion.execute(
                "DELETE FROM muestras WHERE substr(ts, 1, 10) < ?", (corte,)
            )
        # El historial de eventos se guarda más tiempo: sirve para comparar años.
        corte_eventos = (hoy.date() - timedelta(days=400)).isoformat()
        conexion.execute("DELETE FROM eventos WHERE ts < ?", (corte_eventos,))
        conexion.commit()
        resumidos = len(dias)
        if resumidos:
            conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conexion.close()
    return resumidos


def leer(desde=None):
    """Devuelve [(ts, metrica, valor, unidad), ...] ordenado por fecha."""
    if not RUTA_DB.exists():
        try:
            crear()
        except sqlite3.Error:
            return []
    conexion = conectar()
    try:
        sql = "SELECT ts, metrica, valor, unidad FROM muestras"
        parametros = ()
        if desde:
            sql += " WHERE ts >= ?"
            parametros = (desde,)
        sql += " ORDER BY ts"
        return conexion.execute(sql, parametros).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conexion.close()


def contar_dias_muestras():
    """Cuenta fechas locales distintas y fotos distintas del equipo.

    Es una consulta agregada: sirve para refrescar el avance del aprendizaje
    sin cargar todo el historial en memoria. Las fechas se calculan en la
    zona horaria local, igual que el cerebro.
    """
    if not RUTA_DB.exists():
        return 0, 0
    try:
        crear()
    except sqlite3.Error:
        return 0, 0
    conexion = conectar()
    try:
        fila = conexion.execute(
            "SELECT COUNT(DISTINCT date(ts, 'localtime')), "
            "COUNT(DISTINCT ts) FROM muestras"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0, 0
    finally:
        conexion.close()
    if not fila:
        return 0, 0
    return int(fila[0] or 0), int(fila[1] or 0)


def ultima_muestra():
    """Fecha ISO de la última lectura guardada, o None si no hay datos."""
    if not RUTA_DB.exists():
        return None
    conexion = conectar()
    try:
        fila = conexion.execute("SELECT MAX(ts) FROM muestras").fetchone()
        return fila[0] if fila else None
    except sqlite3.OperationalError:
        return None
    finally:
        conexion.close()


def registrar_evento(tipo, detalle="", valor=None, ts=None):
    """Anota algo que le pasó al equipo (una pausa, un aviso, una vuelta a la calma)."""
    crear()
    momento = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    conexion = conectar()
    try:
        conexion.execute(
            "INSERT INTO eventos (ts, tipo, detalle, valor) VALUES (?, ?, ?, ?)",
            (momento, tipo, detalle, valor),
        )
        conexion.commit()
    finally:
        conexion.close()


def leer_eventos(desde=None, limite=200):
    """Devuelve [(ts, tipo, detalle, valor), ...] del más nuevo al más viejo."""
    if not RUTA_DB.exists():
        return []
    conexion = conectar()
    try:
        sql = "SELECT ts, tipo, detalle, valor FROM eventos"
        parametros = ()
        if desde:
            sql += " WHERE ts >= ?"
            parametros = (desde,)
        sql += " ORDER BY ts DESC LIMIT ?"
        parametros = parametros + (limite,)
        return conexion.execute(sql, parametros).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conexion.close()


def ultimo_evento_id():
    """Número del último evento guardado.

    La firma del historial no puede depender solo de la fecha: un pico se
    guarda con la hora en que empezó, así que puede insertarse "abajo" de
    eventos más nuevos y la ventana no se enteraría.
    """
    if not RUTA_DB.exists():
        return 0
    conexion = conectar()
    try:
        fila = conexion.execute("SELECT COALESCE(MAX(id), 0) FROM eventos").fetchone()
        return int(fila[0]) if fila else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conexion.close()


def leer_resumen_diario(desde=None):
    """Devuelve [(dia, metrica, n, minimo, promedio, maximo), ...] del resumen diario.

    Se usa para reconstruir histórico cuando las muestras detalladas ya fueron
    comprimidas por la retención (más de 90 días).
    """
    if not RUTA_DB.exists():
        return []
    conexion = conectar()
    try:
        sql = (
            "SELECT dia, metrica, n, minimo, promedio, maximo "
            "FROM resumen_diario"
        )
        parametros = ()
        if desde:
            sql += " WHERE dia >= ?"
            parametros = (desde,)
        sql += " ORDER BY dia, metrica"
        return conexion.execute(sql, parametros).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conexion.close()


def huella_equipo():
    """Identifica el hardware para saber si el baseline sigue siendo valido."""
    import hashlib
    import platform

    import psutil

    datos = (
        f"{platform.machine()}|{platform.processor()}|"
        f"{psutil.virtual_memory().total}"
    )
    return hashlib.sha256(datos.encode("utf-8")).hexdigest()[:16]


