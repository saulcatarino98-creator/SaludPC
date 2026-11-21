"""Ventana principal: semáforo, tarjetas de estado e historial del equipo."""

import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path

import customtkinter as ctk

import agente
import almacen
import config_usuario
import eventos
import metricas
import rutas
import vigilante

# ---------------------------------------------------------------- paleta ----

FONDO = ("#F1F3F7", "#0E0F13")
TARJETA = ("#FFFFFF", "#191A20")
BORDE = ("#E4E7EC", "#272832")
TEXTO = ("#101828", "#F2F4F7")
SUAVE = ("#667085", "#98A2B3")
PISTA = ("#EAECF0", "#2A2B34")

ESTADO_COLOR = {
    "ok": ("#12805C", "#3DD68C"),
    "atencion": ("#B54708", "#F5B547"),
    "accion": ("#B42318", "#FF6B60"),
    "aprendiendo": ("#475467", "#98A2B3"),
    "sin_datos": ("#475467", "#98A2B3"),
}

ESTADO_FONDO = {
    "ok": ("#E7F5EE", "#12251C"),
    "atencion": ("#FEF3DD", "#2A2110"),
    "accion": ("#FDE8E6", "#2E1513"),
    "aprendiendo": ("#EEF1F5", "#1A1B21"),
    "sin_datos": ("#EEF1F5", "#1A1B21"),
}

ETIQUETAS = {
    "ok": "Normal",
    "atencion": "Atención",
    "accion": "Revisar",
    "aprendiendo": "Aprendiendo",
    "sin_datos": "Sin datos",
}

COLOR_TONO = {
    "ok": ("#12805C", "#3DD68C"),
    "atencion": ("#B54708", "#F5B547"),
    "accion": ("#B42318", "#FF6B60"),
    "neutral": ("#98A2B3", "#6B7280"),
}

FILTROS = {
    "Todos": "todos",
    "Energía": "energia",
    "Carga": "carga",
    "Térmicas": "termicas",
}

TARJETAS = [
    ("cpu_load", "Uso del procesador"),
    ("cpu_temp", "Temperatura del procesador"),
    ("ram_load", "Memoria en uso"),
    ("disk_used_pct", "Espacio del disco"),
    ("disk_temp", "Temperatura del disco"),
    ("gpu_temp", "Temperatura de video"),
]

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CLAVE_TRANSPARENTE = "#FF00FE"

DIAS_SEMANA = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
]
MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def texto_valor(valor, unidad, decimales=0):
    return f"{valor:.{decimales}f} {unidad}".strip()


def etiqueta_dia(dia):
    hoy = datetime.now().date()
    if dia == hoy:
        return "Hoy"
    if dia == hoy - timedelta(days=1):
        return "Ayer"
    return f"{DIAS_SEMANA[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]}"


def tema_windows():
    """Claro u oscuro, según la preferencia de Windows."""
    try:
        import winreg

        clave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        valor, _ = winreg.QueryValueEx(clave, "AppsUseLightTheme")
        return "light" if valor else "dark"
    except Exception:
        return None


def comando_reporte():
    if rutas.congelado():
        return [sys.executable, "--reporte"]
    return [
        sys.executable,
        str(Path(__file__).resolve().parent / "app.py"),
        "--reporte",
    ]


def comando_panel():
    if rutas.congelado():
        return [sys.executable, "--panel"]
    return [
        sys.executable,
        str(Path(__file__).resolve().parent / "app.py"),
        "--panel",
    ]


MENSAJES_AVISO = {
    "atencion": "El equipo se salió de lo normal. Abrí el panel para ver qué pasó.",
    "accion": "Hay un valor que conviene revisar. Abrí el panel para ver el detalle.",
}


def mostrar_aviso(estado, mensaje=None):
    """Aviso suelto, para el servicio y para las pruebas (`--aviso`)."""
    ctk.set_appearance_mode(tema_windows() or "system")
    ctk.set_default_color_theme("blue")

    raiz = ctk.CTk()
    raiz.withdraw()

    def abrir_panel():
        try:
            subprocess.Popen(comando_panel(), creationflags=SIN_VENTANA)
        except OSError:
            pass

    aviso = Aviso(
        raiz,
        estado,
        mensaje or MENSAJES_AVISO.get(estado, "Hay algo para revisar."),
        abrir_panel,
        al_cerrar=raiz.destroy,
    )
    raiz.aviso = aviso  # mantener la referencia mientras dura la ventana
    raiz.mainloop()


class Aviso:
    """Ventana chica abajo a la derecha, con el mismo estilo del panel."""

    ANCHO = 400
    ALTO = 148
    DURACION = 9000

    def __init__(self, maestro, estado, mensaje, al_abrir, al_cerrar=None):
        self.al_cerrar = al_cerrar
        self._cerrado = False
        self.ventana = ctk.CTkToplevel(maestro)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.configure(fg_color=CLAVE_TRANSPARENTE)
        try:
            self.ventana.attributes("-transparentcolor", CLAVE_TRANSPARENTE)
        except tk.TclError:
            pass

        marco = ctk.CTkFrame(
            self.ventana,
            corner_radius=16,
            fg_color=TARJETA,
            border_width=1,
            border_color=BORDE,
        )
        marco.pack(fill="both", expand=True)

        barra = ctk.CTkFrame(
            marco,
            width=6,
            corner_radius=3,
            fg_color=ESTADO_COLOR.get(estado, ESTADO_COLOR["sin_datos"]),
        )
        barra.pack(side="left", fill="y", padx=(12, 0), pady=14)

        caja = ctk.CTkFrame(marco, fg_color="transparent")
        caja.pack(side="left", fill="both", expand=True, padx=(12, 14), pady=12)

        titulo = ctk.CTkLabel(
            caja,
            text=ETIQUETAS.get(estado, "Aviso"),
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=ESTADO_COLOR.get(estado, ESTADO_COLOR["sin_datos"]),
            anchor="w",
        )
        titulo.pack(fill="x")

        cuerpo = ctk.CTkLabel(
            caja,
            text=mensaje,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXTO,
            anchor="w",
            justify="left",
            wraplength=300,
        )
        cuerpo.pack(fill="both", expand=True)

        pista = ctk.CTkLabel(
            caja,
            text="Clic para abrir el panel",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            anchor="w",
        )
        pista.pack(fill="x")

        for widget in (marco, barra, caja, titulo, cuerpo, pista):
            widget.bind("<Button-1>", lambda _evento: self.abrir(al_abrir))
            try:
                widget.configure(cursor="hand2")
            except tk.TclError:
                pass

        self.ventana.update_idletasks()
        x = self.ventana.winfo_screenwidth() - self.ANCHO - 24
        y = self.ventana.winfo_screenheight() - self.ALTO - 72
        self.ventana.geometry(f"{self.ANCHO}x{self.ALTO}+{x}+{y}")
        self.ventana.after(self.DURACION, self.cerrar)

    def abrir(self, accion):
        self.cerrar()
        accion()

    def cerrar(self):
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass
        if self.al_cerrar is not None:
            try:
                self.al_cerrar()
            except tk.TclError:
                pass


class Ventana:
    def __init__(self):
        self.tema_actual = tema_windows() or "system"
        ctk.set_appearance_mode(self.tema_actual)
        ctk.set_default_color_theme("blue")

        self.raiz = ctk.CTk()
        self.raiz.title("Salud de mi equipo")
        # La ventana tiene que entrar en pantallas chicas (1366x768), dejando
        # lugar para la barra de tareas y el borde del título.
        ancho, alto = 880, 640
        x = max(0, (self.raiz.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.raiz.winfo_screenheight() - alto) // 2 - 40)
        self.raiz.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.raiz.minsize(760, 600)
        self.raiz.configure(fg_color=FONDO)

        self.fuente_titulo = ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        self.fuente_sub = ctk.CTkFont(family="Segoe UI", size=12)
        self.fuente_estado = ctk.CTkFont(family="Segoe UI", size=21, weight="bold")
        self.fuente_mensaje = ctk.CTkFont(family="Segoe UI", size=13)
        self.fuente_punto = ctk.CTkFont(family="Segoe UI", size=40)
        self.fuente_etiqueta = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self.fuente_valor = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
        self.fuente_pie = ctk.CTkFont(family="Segoe UI", size=11)
        self.fuente_evento = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        self.fuente_texto = ctk.CTkFont(family="Segoe UI", size=12)
        self.fuente_dia = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")

        self.raiz.grid_columnconfigure(0, weight=1)
        self.raiz.grid_rowconfigure(1, weight=1)

        self.filtro_actual = "todos"

        self._crear_encabezado()
        self._crear_pestanas()
        self._crear_pie()

        # Se crea después de armar la ventana: así la primera medición no
        # incluye el trabajo de inicio de la interfaz.
        try:
            self.medidor = agente.Medidor()
        except Exception:
            self.medidor = None

        self.ultimo = None
        self.firma_historial = None
        self.lecturas_actuales = {}
        self.lectura_actual_hora = None
        self.error_lectura_actual = None
        self._resultados_lectura = queue.Queue()
        self._lectura_actual_en_curso = False

        # Widgets de la pestaña Predicción (se llenan en _crear_pestanas)
        self.tarjetas_pred = {}
        self.labels_patrones = {}

        self.raiz.after(150, self.actualizar)
        self.raiz.after(250, self._actualizar_en_vivo)
        self.raiz.after(250, self._ciclo_consumo)
        self.raiz.mainloop()

    # ------------------------------------------------------------ armado --

    def _crear_encabezado(self):
        encabezado = ctk.CTkFrame(self.raiz, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=26, pady=(20, 6))
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Salud de mi equipo",
            font=self.fuente_titulo,
            text_color=TEXTO,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.consumo = ctk.CTkLabel(
            encabezado,
            text="Consumo del agente: midiendo…",
            font=self.fuente_pie,
            text_color=SUAVE,
            anchor="w",
        )
        self.consumo.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.subtitulo = ctk.CTkLabel(
            encabezado,
            text="Leyendo el equipo…",
            font=self.fuente_sub,
            text_color=SUAVE,
            anchor="w",
        )
        self.subtitulo.grid(row=2, column=0, sticky="w", pady=(2, 0))

        self.riesgo_score = ctk.CTkLabel(
            encabezado,
            text="Score de riesgo: —",
            font=self.fuente_pie,
            text_color=SUAVE,
            anchor="w",
        )
        self.riesgo_score.grid(row=3, column=0, sticky="w", pady=(2, 0))

    def _crear_pestanas(self):
        self.pestanas = ctk.CTkTabview(
            self.raiz,
            corner_radius=16,
            fg_color=FONDO,
            border_width=0,
            segmented_button_fg_color=PISTA,
            segmented_button_unselected_color=PISTA,
            segmented_button_selected_color=TARJETA,
            segmented_button_selected_hover_color=TARJETA,
            segmented_button_unselected_hover_color=BORDE,
            text_color=TEXTO,
            text_color_disabled=SUAVE,
            segmented_button_font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.pestanas.grid(row=1, column=0, sticky="nsew", padx=22, pady=6)
        self.pestanas.add("Ahora")
        self.pestanas.add("Historial")
        self.pestanas.add("Predicción")

        ahora = self.pestanas.tab("Ahora")
        ahora.grid_columnconfigure((0, 1, 2), weight=1, uniform="tarjeta")
        ahora.grid_rowconfigure(1, weight=0)
        ahora.grid_rowconfigure(2, weight=0)

        self.hero = ctk.CTkFrame(
            ahora,
            corner_radius=16,
            fg_color=ESTADO_FONDO["sin_datos"],
        )
        self.hero.grid(row=0, column=0, columnspan=3, sticky="ew", padx=2, pady=(2, 14))
        self.hero.grid_columnconfigure(1, weight=1)

        self.punto = ctk.CTkLabel(
            self.hero,
            text="●",
            font=self.fuente_punto,
            text_color=ESTADO_COLOR["sin_datos"],
        )
        self.punto.grid(row=0, column=0, rowspan=2, padx=(22, 12), pady=16)

        self.titulo_estado = ctk.CTkLabel(
            self.hero,
            text="Leyendo…",
            font=self.fuente_estado,
            text_color=TEXTO,
            anchor="w",
        )
        self.titulo_estado.grid(row=0, column=1, sticky="w", pady=(18, 0))

        self.mensaje_estado = ctk.CTkLabel(
            self.hero,
            text="Estamos mirando cómo está el equipo.",
            font=self.fuente_mensaje,
            text_color=TEXTO,
            anchor="w",
            justify="left",
            wraplength=560,
        )
        self.mensaje_estado.grid(row=1, column=1, sticky="w", pady=(0, 18), padx=(0, 18))

        self.tarjetas = {}
        for indice, (metrica, nombre) in enumerate(TARJETAS):
            fila = 1 + indice // 3
            columna = indice % 3
            tarjeta = ctk.CTkFrame(
                ahora,
                corner_radius=14,
                fg_color=TARJETA,
                border_width=1,
                border_color=BORDE,
            )
            tarjeta.grid(
                row=fila, column=columna, sticky="nsew", padx=4, pady=4
            )
            tarjeta.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                tarjeta,
                text=nombre.upper(),
                font=self.fuente_etiqueta,
                text_color=SUAVE,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))

            valor = ctk.CTkLabel(
                tarjeta,
                text="—",
                font=self.fuente_valor,
                text_color=TEXTO,
                anchor="w",
            )
            valor.grid(row=1, column=0, sticky="ew", padx=14)

            barra = ctk.CTkProgressBar(
                tarjeta,
                height=6,
                corner_radius=3,
                fg_color=PISTA,
                progress_color=ESTADO_COLOR["sin_datos"],
            )
            barra.set(0)
            barra.grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 0))

            pie = ctk.CTkLabel(
                tarjeta,
                text="",
                font=self.fuente_pie,
                text_color=SUAVE,
                anchor="w",
            )
            pie.grid(row=3, column=0, sticky="ew", padx=14, pady=(4, 12))

            self.tarjetas[metrica] = {"valor": valor, "barra": barra, "pie": pie}

        historial = self.pestanas.tab("Historial")
        self.filtro = ctk.CTkSegmentedButton(
            historial,
            values=["Todos", "Energía", "Carga", "Térmicas"],
            command=self._cambiar_filtro,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.filtro.set("Todos")
        self.filtro.pack(fill="x", padx=4, pady=(4, 8))

        self.lista = ctk.CTkScrollableFrame(
            historial, fg_color=FONDO, corner_radius=0
        )
        self.lista.pack(fill="both", expand=True, padx=0, pady=0)

        # ----------------------------------------------------- pestaña Predicción --
        prediccion = self.pestanas.tab("Predicción")
        prediccion.grid_columnconfigure(0, weight=1)

        # Título de la pestaña
        ctk.CTkLabel(
            prediccion,
            text="Predictibilidad del equipo",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=TEXTO,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 8))

        # ---- Score de riesgo global ----
        self.frame_riesgo = ctk.CTkFrame(
            prediccion, corner_radius=14, fg_color=TARJETA,
            border_width=1, border_color=BORDE,
        )
        self.frame_riesgo.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            self.frame_riesgo,
            text="Score de riesgo global",
            font=self.fuente_etiqueta,
            text_color=SUAVE,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        self.barra_riesgo = ctk.CTkProgressBar(
            self.frame_riesgo, height=16, corner_radius=8,
            fg_color=PISTA, progress_color=ESTADO_COLOR["ok"],
        )
        self.barra_riesgo.pack(fill="x", padx=16, pady=(0, 4))
        self.barra_riesgo.set(0)

        self.lbl_riesgo = ctk.CTkLabel(
            self.frame_riesgo,
            text="— / 100  (sin datos)",
            font=self.fuente_valor,
            text_color=TEXTO,
            anchor="w",
        )
        self.lbl_riesgo.pack(fill="x", padx=16, pady=(0, 14))

        # ---- Métricas con predictibilidad ----
        self.frame_metricas_pred = ctk.CTkFrame(
            prediccion, corner_radius=14, fg_color=TARJETA,
            border_width=1, border_color=BORDE,
        )
        self.frame_metricas_pred.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            self.frame_metricas_pred,
            text="Métricas térmicas con tendencia",
            font=self.fuente_etiqueta,
            text_color=SUAVE,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 8))

        self.scroll_metricas_pred = ctk.CTkScrollableFrame(
            self.frame_metricas_pred, fg_color="transparent", height=260
        )
        self.scroll_metricas_pred.pack(fill="x", padx=16, pady=(0, 14))

        # Tarjetas de predicción por métrica térmica
        for indice, metrica in enumerate(("cpu_temp", "gpu_temp", "disk_temp")):
            tarjeta = ctk.CTkFrame(
                self.scroll_metricas_pred, corner_radius=10, fg_color="transparent",
            )
            tarjeta.pack(fill="x", padx=0, pady=4)
            tarjeta.grid_columnconfigure(1, weight=1)

            nombre = metricas.NOMBRES.get(metrica, metrica)
            unidad = metricas.UNIDADES.get(metrica, "")

            lbl_nombre = ctk.CTkLabel(
                tarjeta, text=nombre,
                font=self.fuente_etiqueta, text_color=TEXTO, anchor="w",
            )
            lbl_nombre.grid(row=0, column=0, sticky="w", padx=4, pady=(8, 2))

            lbl_valor = ctk.CTkLabel(
                tarjeta, text="—",
                font=self.fuente_valor, text_color=TEXTO, anchor="w",
            )
            lbl_valor.grid(row=1, column=0, sticky="w", padx=4, pady=(0, 2))

            lbl_estado = ctk.CTkLabel(
                tarjeta, text="",
                font=self.fuente_pie, text_color=SUAVE, anchor="w",
            )
            lbl_estado.grid(row=1, column=1, sticky="e", padx=4, pady=(0, 2))

            lbl_tendencia = ctk.CTkLabel(
                tarjeta, text="",
                font=self.fuente_pie, text_color=SUAVE, anchor="w",
                wraplength=400,
            )
            lbl_tendencia.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 8))

            self.tarjetas_pred[metrica] = {
                "valor": lbl_valor,
                "estado": lbl_estado,
                "tendencia": lbl_tendencia,
            }

        # ---- Patrones y alarmas ----
        self.frame_patrones = ctk.CTkFrame(
            prediccion, corner_radius=14, fg_color=TARJETA,
            border_width=1, border_color=BORDE,
        )
        self.frame_patrones.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(
            self.frame_patrones,
            text="Patrones y alarmas predictivas",
            font=self.fuente_etiqueta,
            text_color=SUAVE,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 8))

        self.scroll_patrones = ctk.CTkScrollableFrame(
            self.frame_patrones, fg_color="transparent", height=140
        )
        self.scroll_patrones.pack(fill="x", padx=16, pady=(0, 14))

    def _crear_pie(self):
        pie = ctk.CTkFrame(self.raiz, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ew", padx=26, pady=(8, 18))
        pie.grid_columnconfigure(0, weight=1)

        self.pie_texto = ctk.CTkLabel(
            pie,
            text="",
            font=self.fuente_pie,
            text_color=SUAVE,
            anchor="w",
        )
        self.pie_texto.grid(row=0, column=0, sticky="w")

        # Casilla: "No mostrar esta ventana al iniciar sesión"
        self.ocultar_inicio = ctk.BooleanVar(
            value=not config_usuario.mostrar_ventana_inicio()
        )
        self.casilla_inicio = ctk.CTkCheckBox(
            pie,
            text="No mostrar esta ventana al iniciar sesión",
            variable=self.ocultar_inicio,
            command=self._cambiar_mostrar_inicio,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            hover_color=PISTA,
        )
        self.casilla_inicio.grid(row=1, column=0, sticky="w", pady=(6, 0))

        self.boton_reporte = ctk.CTkButton(
            pie,
            text="Ver reporte de la semana",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=196,
            height=34,
            corner_radius=10,
            command=self.ver_reporte,
        )
        self.boton_reporte.grid(row=0, column=1, sticky="e")

    def _cambiar_mostrar_inicio(self):
        """Guarda la preferencia de mostrar/ocultar la ventana al iniciar sesión."""
        config_usuario.guardar_preferencia(
            "mostrar_ventana_inicio", not self.ocultar_inicio.get()
        )

    # ----------------------------------------------------------- refresco --

    def actualizar(self):
        try:
            self.ultimo = vigilante.diagnosticar()
            self._pintar_estado()
            self._pintar_tarjetas()
            self._pintar_pie()
            self._refrescar_historial()
            self._refrescar_prediccion()
        except Exception as error:
            self.titulo_estado.configure(text="No pudimos actualizar")
            self.mensaje_estado.configure(text=str(error))
            self.hero.configure(fg_color=ESTADO_FONDO["sin_datos"])

        tema = tema_windows()
        if tema and tema != self.tema_actual:
            self.tema_actual = tema
            ctk.set_appearance_mode(tema)

        self.raiz.after(60_000, self.actualizar)

    def _actualizar_en_vivo(self):
        if self._lectura_actual_en_curso:
            return
        self._lectura_actual_en_curso = True
        threading.Thread(
            target=self._leer_en_vivo,
            name="salud-lectura-en-vivo",
            daemon=True,
        ).start()
        self.raiz.after(100, self._procesar_lectura_en_vivo)

    def _leer_en_vivo(self):
        try:
            import colector

            resultado = (colector.leer_actuales(), None)
        except Exception as error:
            resultado = ({}, str(error))
        self._resultados_lectura.put(resultado)

    def _procesar_lectura_en_vivo(self):
        try:
            valores, error = self._resultados_lectura.get_nowait()
        except queue.Empty:
            self.raiz.after(100, self._procesar_lectura_en_vivo)
            return

        self._lectura_actual_en_curso = False
        self.lecturas_actuales = valores
        self.error_lectura_actual = error
        self.lectura_actual_hora = datetime.now().astimezone() if not error else None
        if self.ultimo is not None:
            self._pintar_tarjetas()
            self._pintar_pie()
        self.raiz.after(5_000, self._actualizar_en_vivo)

    def _ciclo_consumo(self):
        self._pintar_consumo()
        self.raiz.after(5_000, self._ciclo_consumo)

    def _pintar_consumo(self):
        if self.medidor is None:
            self.consumo.configure(text="Consumo del agente: sin datos")
            return
        propio = self.medidor.medir()
        if propio is None:
            return
        cpu, ram_mb, ram_pct = propio
        servicio = agente.leer_servicio()
        if servicio is None:
            self.consumo.configure(
                text=agente.texto(cpu, ram_mb, ram_pct) + " · servicio sin datos"
            )
            return
        self.consumo.configure(
            text=agente.texto(
                cpu + servicio["cpu"],
                ram_mb + servicio["ram_mb"],
                ram_pct + servicio["ram_pct"],
            )
        )

    def _pintar_estado(self):
        estado = self.ultimo["estado"]
        self.hero.configure(fg_color=ESTADO_FONDO.get(estado, ESTADO_FONDO["sin_datos"]))
        self.punto.configure(
            text_color=ESTADO_COLOR.get(estado, ESTADO_COLOR["sin_datos"])
        )
        self.titulo_estado.configure(text=ETIQUETAS.get(estado, "Sin datos"))
        self.mensaje_estado.configure(text=self.ultimo["mensaje"])

        # ---- Score de riesgo global ----
        riesgo = self.ultimo.get("riesgo")
        if riesgo:
            color_riesgo = {
                "bajo": ESTADO_COLOR["ok"],
                "medio": ESTADO_COLOR["atencion"],
                "alto": ESTADO_COLOR["atencion"],
                "critico": ESTADO_COLOR["accion"],
            }.get(riesgo["nivel"], SUAVE)
            self.riesgo_score.configure(
                text=(
                    f"Score de riesgo: {riesgo['score']}/100  "
                    f"({riesgo['nivel'].upper()})"
                ),
                text_color=color_riesgo,
            )
        else:
            self.riesgo_score.configure(
                text="Score de riesgo: —", text_color=SUAVE
            )

        # ---- Indicador de alarma predictiva inmediata ----
        detalles = self.ultimo.get("detalles", [])
        alarma_pred = any(
            d.get("alarma_predictiva") for d in detalles
        )
        if alarma_pred and estado == "ok":
            self.titulo_estado.configure(
                text="⚠️ Alerta predictiva",
                text_color=ESTADO_COLOR["atencion"],
            )

    def _pintar_tarjetas(self):
        detalles = {
            dato["metrica"]: dato
            for dato in (self.ultimo or {}).get("detalles", [])
        }
        for metrica, widgets in self.tarjetas.items():
            dato = detalles.get(metrica)
            actual = self.lecturas_actuales.get(metrica)
            if actual:
                valor, unidad = actual
                widgets["valor"].configure(text=texto_valor(valor, unidad))
                limite_aviso = (
                    dato["limite_aviso"]
                    if dato
                    else metricas.PISOS_AVISO[metrica]
                )
                limite_rojo = (
                    dato["limite_rojo"]
                    if dato
                    else metricas.TECHOS_ROJO[metrica]
                )
                proporcion = max(0.0, min(1.0, valor / (limite_rojo or 1)))
                widgets["barra"].set(proporcion)
                if dato:
                    estado_actual = (
                        "accion"
                        if valor >= limite_rojo
                        else "atencion"
                        if valor >= limite_aviso
                        else "ok"
                    )
                    widgets["barra"].configure(
                        progress_color=ESTADO_COLOR[estado_actual]
                    )
                    # ---- Información de predictibilidad en vivo ----
                    tendencia_txt = ""
                    if metrica in ("cpu_temp", "gpu_temp", "disk_temp"):
                        pendiente = dato.get("pendiente", 0) or 0
                        confianza = dato.get("confianza", 0) or 0
                        minutos_aviso = dato.get("minutos_a_aviso")
                        minutos_rojo = dato.get("minutos_a_rojo")
                        patrones = dato.get("patrones", [])

                        if abs(pendiente) > 0.01 and confianza > 0.3:
                            direccion = "subiendo" if pendiente > 0 else "bajando"
                            tendencia_txt = (
                                f" · {direccion} {abs(pendiente):.2f}{unidad}/min"
                                f" (confianza {confianza:.0%})"
                            )

                        if minutos_rojo is not None and minutos_rojo <= 30:
                            tendencia_txt += f" · ⚠️ Riesgo en ~{minutos_rojo:.0f} min"
                        elif minutos_aviso is not None and minutos_aviso <= 30:
                            tendencia_txt += f" · ⚠️ Aviso en ~{minutos_aviso:.0f} min"

                        if patrones:
                            tipos = [p["tipo"] for p in patrones]
                            if "tendencia_al_alta" in tipos:
                                tendencia_txt += " · Tendencia al alza"
                            if "subida_repentina" in tipos:
                                tendencia_txt += " · Subida repentina"

                    widgets["pie"].configure(
                        text=(
                            f"en vivo · normal hasta "
                            f"{texto_valor(limite_aviso, unidad)}"
                            f"{tendencia_txt}"
                        )
                    )
                else:
                    widgets["barra"].configure(
                        progress_color=ESTADO_COLOR["sin_datos"]
                    )
                    widgets["pie"].configure(
                        text="en vivo · umbral histórico no disponible"
                    )
                continue

            if dato:
                unidad = dato["unidad"]
                widgets["valor"].configure(
                    text=texto_valor(dato["ultimo"], unidad)
                )
                tope = dato["limite_rojo"] or 1
                proporcion = max(0.0, min(1.0, dato["ultimo"] / tope))
                widgets["barra"].set(proporcion)
                widgets["barra"].configure(
                    progress_color=ESTADO_COLOR.get(
                        dato["estado"], ESTADO_COLOR["sin_datos"]
                    )
                )
                # ---- Información de predictibilidad (pendiente y tiempo a umbral) ----
                tendencia_txt = ""
                if metrica in ("cpu_temp", "gpu_temp", "disk_temp"):
                    pendiente = dato.get("pendiente", 0) or 0
                    confianza = dato.get("confianza", 0) or 0
                    minutos_aviso = dato.get("minutos_a_aviso")
                    minutos_rojo = dato.get("minutos_a_rojo")
                    patrones = dato.get("patrones", [])

                    if abs(pendiente) > 0.01 and confianza > 0.3:
                        direccion = "subiendo" if pendiente > 0 else "bajando"
                        tendencia_txt = (
                            f"· {direccion} {abs(pendiente):.2f}{unidad}/min"
                            f" (confianza {confianza:.0%})"
                        )

                    if minutos_rojo is not None and minutos_rojo <= 30:
                        tendencia_txt += f" · ⚠️ Riesgo en ~{minutos_rojo:.0f} min"
                    elif minutos_aviso is not None and minutos_aviso <= 30:
                        tendencia_txt += f" · ⚠️ Aviso en ~{minutos_aviso:.0f} min"

                    if patrones:
                        tipos = [p["tipo"] for p in patrones]
                        if "tendencia_al_alta" in tipos:
                            tendencia_txt += " · Tendencia al alza"
                        if "subida_repentina" in tipos:
                            tendencia_txt += " · Subida repentina"

                widgets["pie"].configure(
                    text=(
                        "último dato guardado · normal hasta "
                        f"{texto_valor(dato['limite_aviso'], unidad)}"
                        f"{tendencia_txt}"
                    )
                )
            else:
                widgets["valor"].configure(text="—")
                widgets["barra"].set(0)
                widgets["barra"].configure(
                    progress_color=ESTADO_COLOR["sin_datos"]
                )
                widgets["pie"].configure(text="sin lectura disponible")

    def _pintar_pie(self):
        self.subtitulo.configure(
            text=(
                f"{self._equipo()} · métricas en vivo cada 5 s · "
                "alerta preventiva basada en el historial"
            )
        )
        ultima = (self.ultimo or {}).get("ultima_lectura")
        ahora = datetime.now()
        partes = []
        if self.lectura_actual_hora:
            partes.append(
                f"Lectura en vivo {self.lectura_actual_hora:%H:%M:%S}"
            )
        elif self.error_lectura_actual:
            partes.append(f"Error de lectura en vivo: {self.error_lectura_actual}")

        if ultima:
            try:
                marca = datetime.fromisoformat(ultima).astimezone()
            except ValueError:
                marca = None
            if marca:
                minutos = int((ahora - marca.replace(tzinfo=None)).total_seconds() // 60)
                if minutos <= 0:
                    hace = "recién"
                elif minutos == 1:
                    hace = "hace 1 minuto"
                else:
                    hace = f"hace {minutos} minutos"
                partes.append(f"Última guardada {marca:%H:%M} ({hace})")
        if not partes:
            partes.append("Todavía no hay lecturas")
        self.pie_texto.configure(text=" · ".join(partes))

    def _equipo(self):
        try:
            from socket import gethostname

            return gethostname()
        except Exception:
            return "este equipo"

    def _cambiar_filtro(self, etiqueta):
        self.filtro_actual = FILTROS.get(etiqueta, "todos")
        self.firma_historial = None
        self._refrescar_historial()

    def _refrescar_historial(self):
        desde = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(
            timespec="seconds"
        )
        filas = almacen.leer_eventos(desde=desde, limite=300)
        if self.filtro_actual != "todos":
            filas = [
                fila
                for fila in filas
                if eventos.categoria(fila[1], fila[2]) == self.filtro_actual
            ]
        firma = (
            almacen.ultimo_evento_id(),
            len(filas),
            filas[0][0] if filas else None,
            self.filtro_actual,
        )
        if firma == self.firma_historial:
            return
        self.firma_historial = firma

        for hijo in self.lista.winfo_children():
            hijo.destroy()

        if not filas:
            if self.filtro_actual == "todos":
                texto_vacio = (
                    "Todavía no pasó nada que valga la pena contar.\n"
                    "Las suspensiones, los reinicios y los avisos van a aparecer acá."
                )
            else:
                texto_vacio = (
                    "No hay eventos de este tipo en los últimos 30 días."
                )
            ctk.CTkLabel(
                self.lista,
                text=texto_vacio,
                font=self.fuente_texto,
                text_color=SUAVE,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=10, pady=16)
            return

        dia_actual = None
        for ts, tipo, detalle, valor in filas:
            try:
                momento = datetime.fromisoformat(ts).astimezone()
            except ValueError:
                continue
            if momento.date() != dia_actual:
                dia_actual = momento.date()
                ctk.CTkLabel(
                    self.lista,
                    text=etiqueta_dia(dia_actual),
                    font=self.fuente_dia,
                    text_color=SUAVE,
                    anchor="w",
                ).pack(fill="x", padx=8, pady=(14, 4))

            titulo, texto, tono = eventos.describir(ts, tipo, detalle, valor)
            fila = ctk.CTkFrame(
                self.lista,
                fg_color=TARJETA,
                corner_radius=12,
                border_width=1,
                border_color=BORDE,
            )
            fila.pack(fill="x", padx=4, pady=3)

            ctk.CTkFrame(
                fila,
                width=10,
                height=10,
                corner_radius=5,
                fg_color=COLOR_TONO.get(tono, COLOR_TONO["neutral"]),
            ).pack(side="left", padx=(14, 12), pady=16)

            caja = ctk.CTkFrame(fila, fg_color="transparent")
            caja.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=10)

            encabezado = ctk.CTkFrame(caja, fg_color="transparent")
            encabezado.pack(fill="x")

            ctk.CTkLabel(
                encabezado,
                text=titulo,
                font=self.fuente_evento,
                text_color=TEXTO,
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                encabezado,
                text=f"{momento:%H:%M}",
                font=self.fuente_pie,
                text_color=SUAVE,
            ).pack(side="right")

            ctk.CTkLabel(
                caja,
                text=texto,
                font=self.fuente_texto,
                text_color=SUAVE,
                anchor="w",
                justify="left",
                wraplength=560,
            ).pack(fill="x")

    def _refrescar_prediccion(self):
        """Actualiza la pestaña de Predicción con datos de predictibilidad."""
        ultimo = self.ultimo or {}

        # ---- Score de riesgo global ----
        riesgo = ultimo.get("riesgo")
        if riesgo:
            score = riesgo["score"]
            nivel = riesgo["nivel"]
            self.barra_riesgo.set(score / 100.0)
            color = {
                "bajo": ESTADO_COLOR["ok"],
                "medio": ESTADO_COLOR["atencion"],
                "alto": ESTADO_COLOR["atencion"],
                "critico": ESTADO_COLOR["accion"],
            }.get(nivel, SUAVE)
            self.barra_riesgo.configure(progress_color=color)
            self.lbl_riesgo.configure(
                text=f"{score:.0f} / 100  ({nivel.upper()})",
                text_color=color,
            )
        else:
            self.barra_riesgo.set(0)
            self.barra_riesgo.configure(progress_color=ESTADO_COLOR["sin_datos"])
            self.lbl_riesgo.configure(text="— / 100  (sin datos)", text_color=SUAVE)

        # ---- Métricas térmicas con predictibilidad ----
        detalles = {
            d["metrica"]: d for d in ultimo.get("detalles", [])
        }
        for metrica, widgets in self.tarjetas_pred.items():
            dato = detalles.get(metrica)
            nombre = metricas.NOMBRES.get(metrica, metrica)
            unidad = metricas.UNIDADES.get(metrica, "")

            if dato:
                widgets["valor"].configure(
                    text=texto_valor(dato["ultimo"], unidad)
                )
                estado = dato.get("estado", "ok")
                widgets["estado"].configure(
                    text=ETIQUETAS.get(estado, "Sin datos"),
                    text_color=ESTADO_COLOR.get(estado, SUAVE),
                )

                # Texto de tendencia
                pendiente = dato.get("pendiente", 0) or 0
                confianza = dato.get("confianza", 0) or 0
                minutos_aviso = dato.get("minutos_a_aviso")
                minutos_rojo = dato.get("minutos_a_rojo")
                patrones = dato.get("patrones", [])
                alarma = dato.get("alarma_predictiva", False)

                partes = []
                if abs(pendiente) > 0.01 and confianza > 0.3:
                    direccion = "subiendo" if pendiente > 0 else "bajando"
                    partes.append(
                        f"{direccion} {abs(pendiente):.2f}{unidad}/min"
                        f" (confianza {confianza:.0%})"
                    )

                if alarma:
                    partes.append("🚨 ALARMA PREDICTIVA")

                if minutos_rojo is not None and minutos_rojo <= 30:
                    partes.append(f"⚠️ Riesgo en ~{minutos_rojo:.0f} min")
                elif minutos_aviso is not None and minutos_aviso <= 30:
                    partes.append(f"⚠️ Aviso en ~{minutos_aviso:.0f} min")

                if patrones:
                    tipos = [p["tipo"] for p in patrones]
                    if "tendencia_al_alta" in tipos:
                        partes.append("Tendencia al alza")
                    if "subida_repentina" in tipos:
                        partes.append("Subida repentina")

                widgets["tendencia"].configure(
                    text=" · ".join(partes) if partes else "Sin tendencia clara",
                    text_color=ESTADO_COLOR["accion"] if alarma else SUAVE,
                )
            else:
                widgets["valor"].configure(text="—")
                widgets["estado"].configure(text="Sin datos", text_color=SUAVE)
                widgets["tendencia"].configure(text="", text_color=SUAVE)

        # ---- Patrones y alarmas ----
        for hijo in self.scroll_patrones.winfo_children():
            hijo.destroy()

        tiene_patrones = False
        for metrica, dato in detalles.items():
            if metrica not in ("cpu_temp", "gpu_temp", "disk_temp"):
                continue
            patrones = dato.get("patrones", [])
            alarma = dato.get("alarma_predictiva", False)
            nombre = metricas.NOMBRES.get(metrica, metrica)

            if alarma:
                tiene_patrones = True
                fila = ctk.CTkFrame(
                    self.scroll_patrones, fg_color=TARJETA,
                    corner_radius=8, border_width=1, border_color=BORDE,
                )
                fila.pack(fill="x", padx=0, pady=3)
                ctk.CTkLabel(
                    fila,
                    text=f"🚨 {nombre}: alarma predictiva inmediata",
                    font=self.fuente_texto,
                    text_color=ESTADO_COLOR["accion"],
                    anchor="w",
                ).pack(fill="x", padx=10, pady=6)

            for patron in patrones:
                tiene_patrones = True
                severidad = patron.get("severidad", "media")
                color = {
                    "alta": ESTADO_COLOR["accion"],
                    "media": ESTADO_COLOR["atencion"],
                    "baja": SUAVE,
                }.get(severidad, SUAVE)
                fila = ctk.CTkFrame(
                    self.scroll_patrones, fg_color=TARJETA,
                    corner_radius=8, border_width=1, border_color=BORDE,
                )
                fila.pack(fill="x", padx=0, pady=3)
                ctk.CTkLabel(
                    fila,
                    text=f"● {patron['descripcion']}  ({nombre})",
                    font=self.fuente_texto,
                    text_color=color,
                    anchor="w",
                ).pack(fill="x", padx=10, pady=6)

        if not tiene_patrones:
            ctk.CTkLabel(
                self.scroll_patrones,
                text="Sin patrones de riesgo detectados.",
                font=self.fuente_texto,
                text_color=SUAVE,
                anchor="w",
            ).pack(fill="x", padx=10, pady=16)

    # ------------------------------------------------------------ reporte --

    def ver_reporte(self):
        self.boton_reporte.configure(state="disabled", text="Preparando reporte…")
        try:
            subprocess.Popen(comando_reporte(), creationflags=SIN_VENTANA)
        except OSError:
            pass
        self.raiz.after(4000, self._restaurar_boton)

    def _restaurar_boton(self):
        self.boton_reporte.configure(
            state="normal", text="Ver reporte de la semana"
        )


if __name__ == "__main__":
    Ventana()
