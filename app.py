"""Punto de entrada único de SaludPC.

Modos:
  (sin argumentos) / --panel   Ventana del semáforo.
  --servicio                   Recolección en segundo plano + análisis cada 6 h.
  --cerebro                    Recalcular el baseline una vez.
  --una-vez                    Tomar una sola lectura (para pruebas).
  --aviso atencion|accion      Mostrar un aviso flotante de prueba.
  --vigia                      Reiniciar el servicio si dejó de guardar datos.
"""

import argparse
import ctypes
import logging
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import rutas

LOG = logging.getLogger("salud")


def configurar_log(nombre="salud"):
    ruta = rutas.carpeta_datos() / f"{nombre}.log"
    manejador = RotatingFileHandler(
        ruta, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    manejador.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(manejador)
    if sys.stdout:
        consola = logging.StreamHandler()
        consola.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        raiz.addHandler(consola)


def bloquear_instancia():
    """Evita dos servicios de recolección al mismo tiempo."""
    import os

    kernel32 = ctypes.windll.kernel32
    nombre = os.environ.get("SALUD_PC_MUTEX", "Local\\SaludPC_Servicio")
    mutex = kernel32.CreateMutexW(None, False, nombre)
    error = kernel32.GetLastError()
    if not mutex:
        LOG.warning(
            "No se pudo crear el bloqueo de instancia (error %s).", error
        )
        return True
    if error == 183:  # ERROR_ALREADY_EXISTS
        return None
    return mutex


def lanzar_aviso(estado, mensaje):
    """Muestra el aviso en la sesión del usuario, sin depender del panel.

    El servicio corre en la misma sesión que el usuario (tarea AtLogOn), así
    que puede abrir una ventana propia aunque el panel esté cerrado.
    """
    if rutas.congelado():
        comando = [sys.executable, "--aviso", estado, "--mensaje", mensaje]
    else:
        comando = [
            sys.executable,
            str(Path(__file__).resolve().parent / "app.py"),
            "--aviso",
            estado,
            "--mensaje",
            mensaje,
        ]
    try:
        subprocess.Popen(
            comando,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except OSError:
        LOG.exception("No se pudo mostrar el aviso flotante")
        return False


def servicio():
    import agente
    import almacen
    import cerebro
    import colector
    import eventos
    import reportes
    import vigilante
    from datetime import datetime, timezone

    mutex = bloquear_instancia()
    if mutex is None:
        LOG.info("Ya hay un servicio de recolección funcionando.")
        return

    almacen.crear()
    medidor_agente = agente.Medidor()
    try:
        cerebro.main()
    except Exception:
        LOG.exception("No se pudo generar el baseline inicial")

    ultimo_cerebro = time.monotonic()
    ultima_limpieza = None  # None fuerza el mantenimiento en el primer arranque
    estado_previo = eventos.ultimo_estado()
    # El baseline del arranque se calcula antes de la primera muestra del día,
    # así que puede quedar con una fecha de menos. Este primer refresco, ya con
    # datos nuevos, lo corrige sin esperar las 6 horas.
    refresco_pendiente = True
    dia_local = datetime.now().astimezone().date()

    # Se compara contra la última lectura guardada: si el servicio estuvo
    # apagado o el equipo suspendido, queda un hueco que hay que explicar.
    ultimo_momento = None
    try:
        marca = almacen.ultima_muestra()
        if marca:
            ultimo_momento = datetime.fromisoformat(marca)
    except Exception:
        LOG.exception("No se pudo leer la última medición")

    LOG.info("Servicio de recolección iniciado.")

    while True:
        ahora = datetime.now(timezone.utc)
        if ultimo_momento is not None:
            minutos = (ahora - ultimo_momento).total_seconds() / 60
            if minutos >= eventos.PAUSA_MINIMA_MINUTOS:
                try:
                    tipo = eventos.registrar_pausa(minutos, ultimo_momento)
                    LOG.info(
                        "Pausa registrada: %s de %s minutos",
                        tipo,
                        round(minutos),
                    )
                except Exception:
                    LOG.exception("No se pudo registrar la pausa")

        try:
            colector.recolectar()
        except Exception:
            LOG.exception("Error al recolectar datos")
        ultimo_momento = datetime.now(timezone.utc)

        diagnostico = None
        try:
            diagnostico = vigilante.diagnosticar()
            estado = diagnostico["estado"]
            metrica = next(
                (
                    dato["metrica"]
                    for dato in diagnostico["detalles"]
                    if dato["estado"] == estado
                ),
                None,
            )
            if estado != estado_previo:
                if estado in ("atencion", "accion"):
                    eventos.registrar_estado(estado, metrica)
                    LOG.info("El equipo pasó a estado %s (%s)", estado, metrica)
                elif (
                    estado_previo in ("atencion", "accion") and estado == "ok"
                ):
                    eventos.registrar("normal")
                    LOG.info("El equipo volvió a la normalidad")
                estado_previo = estado

            # El aviso lo dispara el servicio: antes dependía de que el panel
            # estuviera abierto y de que viera el cambio, así que se perdía si
            # el usuario no estaba mirando.
            anterior_aviso = eventos.estado_avisado()
            if eventos.debe_avisar(estado, anterior_aviso):
                if lanzar_aviso(estado, diagnostico["mensaje"]):
                    eventos.marcar_estado_aviso(estado, metrica)
                    LOG.info("Aviso flotante mostrado para el estado %s", estado)
            elif anterior_aviso != estado:
                # También se guarda cuando mejora, para que un empeoramiento
                # posterior vuelva a avisar. No se escribe en cada minuto.
                eventos.marcar_estado_aviso(estado, metrica)
        except Exception:
            LOG.exception("No se pudo evaluar el estado del equipo")

        # Los picos se miden sobre el mismo diagnóstico que dispara los avisos:
        # un episodio empieza y termina con la regla de 3 de 5 muestras.
        if diagnostico is not None:
            try:
                cerrados = eventos.actualizar_episodios(diagnostico)
                for pico in cerrados:
                    LOG.info(
                        "Pico registrado: %s durante %s minutos (máximo %s)",
                        pico["metrica"],
                        pico["duracion"],
                        pico["maximo"],
                    )
            except Exception:
                LOG.exception("No se pudieron actualizar los episodios de pico")

        # El panel no puede leer el proceso elevado del servicio, así que el
        # servicio publica su propio consumo una vez por minuto.
        try:
            consumo = medidor_agente.medir()
            if consumo is not None:
                agente.escribir_servicio(*consumo)
        except Exception:
            LOG.exception("No se pudo medir el consumo del servicio")

        # Se recalcula al arrancar, al cambiar el día local y cada 6 horas.
        # El cambio de día es lo que hace avanzar el contador de aprendizaje:
        # antes podía quedar hasta 6 horas mostrando un día de menos.
        ahora_local = datetime.now().astimezone()
        if (
            refresco_pendiente
            or ahora_local.date() != dia_local
            or time.monotonic() - ultimo_cerebro >= 6 * 3600
        ):
            try:
                cerebro.main()
            except Exception:
                LOG.exception("No se pudo recalcular el baseline")
                # Reintentar en 10 minutos en vez de esperar 6 horas.
                ultimo_cerebro = time.monotonic() - 6 * 3600 + 600
            else:
                LOG.info("Baseline recalculado")
                ultimo_cerebro = time.monotonic()
            refresco_pendiente = False
            dia_local = ahora_local.date()

        if ultima_limpieza is None or time.monotonic() - ultima_limpieza >= 24 * 3600:
            try:
                dias = almacen.resumir_y_limpiar()
                LOG.info("Mantenimiento de la base: %s días resumidos", dias)
            except Exception:
                LOG.exception("No se pudo hacer mantenimiento de la base")
            try:
                ruta = reportes.generar()
                LOG.info("Reporte semanal actualizado: %s", ruta.name)
            except Exception:
                LOG.exception("No se pudo generar el reporte semanal")
            ultima_limpieza = time.monotonic()

        time.sleep(60)


def proceso_servicio():
    """Devuelve el proceso de recolección si está vivo."""
    import psutil

    for proceso in psutil.process_iter(["name", "cmdline"]):
        try:
            nombre = (proceso.info["name"] or "").lower()
            orden = proceso.info["cmdline"] or []
        except psutil.Error:
            continue
        if "--servicio" not in orden:
            continue
        if "saludpc" in nombre or any(str(x).endswith("app.py") for x in orden):
            return proceso
    return None


def vigia():
    """Reinicia el servicio si pasó demasiado tiempo sin guardar datos."""
    import subprocess
    from datetime import datetime, timezone

    import almacen

    LIMITE_MINUTOS = 10
    GRACIA_MINUTOS = 3
    TAREA = "SaludPC Servicio"

    def schtasks(accion):
        banderas = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(
            ["schtasks", accion, "/TN", TAREA],
            capture_output=True,
            text=True,
            creationflags=banderas,
        )

    try:
        marca = almacen.ultima_muestra()
    except Exception:
        LOG.exception("No se pudo consultar la base; no se toca el servicio")
        return

    ahora = datetime.now(timezone.utc)
    atraso = None
    if marca:
        try:
            atraso = (ahora - datetime.fromisoformat(marca)).total_seconds() / 60
        except ValueError:
            atraso = None
        if atraso is not None and atraso <= LIMITE_MINUTOS:
            return  # todo en orden: no escribe nada

    proceso = proceso_servicio()
    if proceso is not None:
        try:
            edad = (time.time() - proceso.create_time()) / 60
        except Exception:
            edad = None
        if edad is not None and edad < GRACIA_MINUTOS:
            return  # recién arrancó: darle tiempo
        LOG.warning(
            "El servicio lleva %s minutos sin guardar datos. Reiniciando.",
            round(atraso) if atraso is not None else "demasiados",
        )
        schtasks("/End")
        # Esperar a que muera: si no, el mutex hace salir a la instancia nueva.
        limite = time.monotonic() + 20
        while time.monotonic() < limite and proceso_servicio() is not None:
            time.sleep(0.5)
    else:
        LOG.warning("El servicio no está corriendo. Arrancando.")

    resultado = schtasks("/Run")
    if resultado.returncode != 0:
        LOG.error(
            "No se pudo arrancar el servicio: %s",
            (resultado.stderr or "").strip() or f"código {resultado.returncode}",
        )
    else:
        LOG.info("Servicio reiniciado por el vigía.")


def main():
    parser = argparse.ArgumentParser(prog="SaludPC")
    parser.add_argument("--servicio", action="store_true")
    parser.add_argument("--panel", action="store_true")
    parser.add_argument("--cerebro", action="store_true")
    parser.add_argument("--una-vez", action="store_true")
    parser.add_argument("--vigia", action="store_true")
    parser.add_argument("--reporte", action="store_true")
    parser.add_argument(
        "--aviso",
        choices=["atencion", "accion"],
        help="Muestra un aviso flotante de prueba y termina.",
    )
    parser.add_argument(
        "--panel-auto",
        action="store_true",
        help="Abrir panel al inicio de sesión (respetar preferencia del usuario).",
    )
    parser.add_argument(
        "--mensaje",
        default=None,
        help="Texto del aviso de prueba (opcional).",
    )
    args = parser.parse_args()

    if args.servicio:
        configurar_log("salud-servicio")
        servicio()
    elif args.aviso:
        configurar_log("salud-aviso")
        from main import mostrar_aviso

        mostrar_aviso(args.aviso, args.mensaje)
    elif args.reporte:
        configurar_log("salud-reporte")
        import reportes

        reportes.abrir(reportes.generar())
    elif args.vigia:
        configurar_log("salud-vigia")
        vigia()
    elif args.cerebro:
        configurar_log("salud-cli")
        import cerebro

        cerebro.main()
    elif args.una_vez:
        configurar_log("salud-cli")
        import almacen
        import colector

        almacen.crear()
        colector.recolectar()
        colector.cerrar_equipo()
    elif args.panel_auto:
        configurar_log("salud-panel")
        import config_usuario

        if not config_usuario.mostrar_ventana_inicio():
            return
        from main import Ventana

        Ventana()
    else:
        configurar_log("salud-panel")
        from main import Ventana

        Ventana()


if __name__ == "__main__":
    main()
