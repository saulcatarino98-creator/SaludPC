"""SaludPC Enterprise - Cliente Operario con panel de aprendizaje.

Una sola ventana: primero la inscripción y, al completarla, el mismo
programa pasa al panel de monitoreo sin cerrarse.
"""

import ctypes
import queue
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cliente_enterprise import (
    ClienteEnterprise,
    cargar_registro,
    guardar_config_cliente,
    guardar_token_guardado,
    mostrar_ventana_inicio,
)

INTERVALO_ENVIO = 60
MUESTRAS_OBJETIVO = 300
DIAS_OBJETIVO = 3
PUERTO_CONTROL = 8457
NOMBRE_MUTEX = "Local\\SaludPC-Cliente-Operario"

VERDE = "#10b981"
AMBAR = "#f59e0b"
ROJO = "#ef4444"
AZUL = "#3b82f6"
TEXTO = "#F2F4F7"
SUAVE = "#98A2B3"
BORDE = "#272832"
TARJETA = "#191A20"

_MUTEX = None


def tomar_instancia():
    """Devuelve True si esta es la primera instancia del cliente."""
    global _MUTEX
    try:
        _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, NOMBRE_MUTEX)
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True


def avisar_instancia_existente():
    """Pide a la instancia que ya corre que muestre su ventana."""
    for _ in range(20):
        try:
            with socket.create_connection(
                ("127.0.0.1", PUERTO_CONTROL), timeout=0.3
            ) as conexion:
                conexion.sendall(b"SHOW\n")
            return True
        except OSError:
            time.sleep(0.15)
    return False


class ClienteGUI(ctk.CTk):
    """Ventana única del cliente operario."""

    def __init__(self, modo_inicio="visible"):
        super().__init__()

        self.title("SaludPC Enterprise — Cliente Operario")
        self.geometry("780x800")
        self.minsize(740, 720)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color="#0E0F13")

        self.modo_inicio = modo_inicio
        self.token = None
        self.id_equipo = None
        self.url_servidor = None
        self.organizacion = ""
        self.sede = ""
        self.area = ""

        self.inscribiendo = False
        self.vista = None
        self.frame_actual = None
        self.entries = {}
        self.tarjetas = {}
        self.cola = queue.Queue()
        self.evento_detener = threading.Event()
        self.aprendizaje_completo = False
        self.ultimo_estado = ("ok", "Todo se ve dentro de lo normal.")
        self._socket_control = None

        self._construir_encabezado()
        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.after(150, self._procesar_cola)
        threading.Thread(target=self._servidor_control, daemon=True).start()

        registro = cargar_registro()
        if registro.get("token"):
            self._aplicar_registro(registro)
            self._mostrar_panel()
            if self.modo_inicio == "oculto" or (
                self.modo_inicio == "auto" and not mostrar_ventana_inicio()
            ):
                self._ocultar_ventana()
        else:
            self._mostrar_configuracion()

    # ------------------------------------------------------------------
    # Instancia única: una segunda apertura solo muestra la ventana
    # ------------------------------------------------------------------

    def _servidor_control(self):
        try:
            servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind(("127.0.0.1", PUERTO_CONTROL))
            servidor.listen(5)
            self._socket_control = servidor
        except OSError:
            return

        while True:
            try:
                conexion, _ = servidor.accept()
                with conexion:
                    orden = conexion.recv(64).decode("utf-8", "ignore").strip().upper()
                    if orden == "SHOW":
                        self.cola.put(("mostrar",))
            except OSError:
                break

    def _detener_control(self):
        servidor = getattr(self, "_socket_control", None)
        if servidor is not None:
            try:
                servidor.close()
            except OSError:
                pass
            self._socket_control = None

    # ------------------------------------------------------------------
    # Encabezado y cambio de vista
    # ------------------------------------------------------------------

    def _construir_encabezado(self):
        header = ctk.CTkFrame(self, fg_color="#0E0F13", corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="SP",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#ffffff",
            width=50,
            height=50,
            fg_color=AZUL,
            corner_radius=12,
        ).pack(side="left", padx=(24, 12), pady=16)

        textos = ctk.CTkFrame(header, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True, pady=16)

        ctk.CTkLabel(
            textos,
            text="SaludPC Enterprise",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#ffffff",
        ).pack(anchor="w")

        self.lbl_subtitulo = ctk.CTkLabel(
            textos,
            text="Cliente Operario · Inscripción y monitoreo",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=SUAVE,
        )
        self.lbl_subtitulo.pack(anchor="w")

        self.lbl_conexion = ctk.CTkLabel(
            header,
            text="● Sin inscribir",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=SUAVE,
        )
        self.lbl_conexion.pack(side="right", padx=24, pady=16)

    def _cambiar_frame(self, nuevo):
        if self.frame_actual is not None and self.frame_actual.winfo_exists():
            self.frame_actual.destroy()
        self.frame_actual = nuevo
        self.frame_actual.pack(fill="both", expand=True)

    def _aplicar_registro(self, registro):
        self.token = registro.get("token")
        self.id_equipo = registro.get("id_equipo")
        self.url_servidor = registro.get("url_servidor") or "http://localhost:8443"
        self.organizacion = registro.get("organizacion", "")
        self.sede = registro.get("sede", "")
        self.area = registro.get("area", "")

    # ------------------------------------------------------------------
    # Vista de configuración / inscripción
    # ------------------------------------------------------------------

    def _mostrar_configuracion(self):
        self._detener_monitoreo()
        self.vista = "config"
        self.geometry("780x800")
        self.minsize(740, 720)
        self.lbl_subtitulo.configure(text="Cliente Operario · Inscripción y monitoreo")
        self.lbl_conexion.configure(
            text="● Inscrito" if self.token else "● Sin inscribir",
            text_color=VERDE if self.token else SUAVE,
        )
        self._cambiar_frame(self._crear_frame_configuracion())

    def _crear_frame_configuracion(self):
        frame = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        frame.pack_propagate(False)

        tarjeta_equipo = ctk.CTkFrame(
            frame, fg_color=TARJETA, border_width=1, border_color=BORDE, corner_radius=16
        )
        tarjeta_equipo.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            tarjeta_equipo,
            text="Datos del Equipo",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=AZUL,
        ).pack(anchor="w", padx=20, pady=(16, 12))

        campos = [
            ("id_equipo", "ID del equipo", "PC-001"),
            ("organizacion", "Organización", "Hospital Central"),
            ("sede", "Sede", "Sede Norte"),
            ("area", "Área", "Área de Emergencias"),
        ]

        bloqueado = bool(self.token)
        for clave, etiqueta, ejemplo in campos:
            fila = ctk.CTkFrame(tarjeta_equipo, fg_color="transparent")
            fila.pack(fill="x", padx=20, pady=(0, 10))

            ctk.CTkLabel(
                fila,
                text=etiqueta,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=TEXTO,
                width=130,
                anchor="w",
            ).pack(side="left", padx=(0, 12))

            entrada = ctk.CTkEntry(
                fila,
                placeholder_text=ejemplo,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                height=40,
                corner_radius=8,
            )
            entrada.pack(side="left", fill="x", expand=True)
            if bloqueado:
                entrada.configure(state="disabled")
            self.entries[clave] = entrada

        tarjeta_servidor = ctk.CTkFrame(
            frame, fg_color=TARJETA, border_width=1, border_color=BORDE, corner_radius=16
        )
        tarjeta_servidor.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            tarjeta_servidor,
            text="Servidor Central",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=AZUL,
        ).pack(anchor="w", padx=20, pady=(16, 12))

        fila_url = ctk.CTkFrame(tarjeta_servidor, fg_color="transparent")
        fila_url.pack(fill="x", padx=20, pady=(0, 6))

        ctk.CTkLabel(
            fila_url,
            text="IP del servidor",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXTO,
            width=130,
            anchor="w",
        ).pack(side="left", padx=(0, 12))

        self.entry_ip = ctk.CTkEntry(
            fila_url,
            placeholder_text="192.168.1.100",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=40,
            corner_radius=8,
        )
        self.entry_ip.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(
            fila_url,
            text=":",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=SUAVE,
            width=10,
        ).pack(side="left")

        self.entry_puerto = ctk.CTkEntry(
            fila_url,
            placeholder_text="8443",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=40,
            corner_radius=8,
            width=90,
        )
        self.entry_puerto.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            tarjeta_servidor,
            text="IP y puerto del servidor central (puerto predeterminado: 8443)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=SUAVE,
        ).pack(anchor="w", padx=(162, 0), pady=(0, 14))

        if self.token:
            ctk.CTkLabel(
                frame,
                text=f"Equipo ya inscrito como {self.id_equipo}. Puedes ajustar la IP o el puerto.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=VERDE,
            ).pack(anchor="w", pady=(0, 8))

        self.btn_inscribir = ctk.CTkButton(
            frame,
            text="Guardar y abrir panel" if self.token else "Inscribir Equipo",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=48,
            corner_radius=10,
            fg_color=AZUL,
            hover_color="#2563eb",
            command=self._accion_inscribir,
        )
        self.btn_inscribir.pack(fill="x", pady=(0, 12))

        self.lbl_estado_config = ctk.CTkLabel(
            frame,
            text="Listo para inscribir",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            anchor="w",
        )
        self.lbl_estado_config.pack(fill="x")

        ctk.CTkLabel(
            frame,
            text="Registro de acciones",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=SUAVE,
        ).pack(anchor="w", pady=(10, 4))

        self.area_log_config = ctk.CTkTextbox(
            frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=130,
            corner_radius=8,
            border_width=1,
            border_color=BORDE,
        )
        self.area_log_config.pack(fill="both", expand=True)

        self._rellenar_configuracion()
        return frame

    def _rellenar_configuracion(self):
        valores = {
            "id_equipo": self.id_equipo,
            "organizacion": self.organizacion,
            "sede": self.sede,
            "area": self.area,
        }
        for clave, valor in valores.items():
            entrada = self.entries.get(clave)
            if entrada is not None and valor:
                entrada.configure(state="normal")
                entrada.delete(0, "end")
                entrada.insert(0, valor)
                if self.token:
                    entrada.configure(state="disabled")

        if self.url_servidor:
            sin_esquema = self.url_servidor.replace("http://", "").replace("https://", "")
            if ":" in sin_esquema:
                ip, puerto = sin_esquema.rsplit(":", 1)
            else:
                ip, puerto = sin_esquema, "8443"
            self.entry_ip.insert(0, ip)
            self.entry_puerto.insert(0, puerto)

    def _log_config(self, mensaje, tipo="info"):
        prefijo = {"info": "", "exito": "✓ ", "error": "✗ "}.get(tipo, "")
        hora = datetime.now().strftime("%H:%M:%S")
        self.area_log_config.insert("end", f"[{hora}] {prefijo}{mensaje}\n")
        self.area_log_config.see("end")
        self.lbl_estado_config.configure(
            text=mensaje[:100],
            text_color=VERDE if tipo == "exito" else ROJO if tipo == "error" else SUAVE,
        )

    def _obtener_datos(self):
        datos = {}
        for clave, entrada in self.entries.items():
            valor = entrada.get().strip()
            if not valor:
                self._log_config(f"El campo {clave} es obligatorio", "error")
                return None
            datos[clave] = valor

        ip = self.entry_ip.get().strip()
        puerto = self.entry_puerto.get().strip() or "8443"

        if not ip:
            self._log_config("La IP del servidor es obligatoria", "error")
            return None
        if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
            self._log_config("El puerto debe ser un número entre 1 y 65535", "error")
            return None

        datos["url_servidor"] = f"http://{ip}:{puerto}"
        return datos

    def _accion_inscribir(self):
        if self.inscribiendo:
            return

        datos = self._obtener_datos()
        if datos is None:
            return

        if self.token:
            self.url_servidor = datos["url_servidor"]
            guardar_token_guardado(
                self.id_equipo,
                self.token,
                organizacion=datos["organizacion"],
                sede=datos["sede"],
                area=datos["area"],
                url_servidor=self.url_servidor,
            )
            self._mostrar_panel()
            return

        self.inscribiendo = True
        self.btn_inscribir.configure(state="disabled", text="Inscribiendo…")
        self._log_config("Conectando con el servidor central…")

        def tarea():
            cliente = ClienteEnterprise(
                datos["id_equipo"], "", datos["url_servidor"]
            )
            try:
                resultado = cliente.inscribir(
                    datos["organizacion"], datos["sede"], datos["area"]
                )
            except Exception as error:
                resultado = {"ok": False, "error": str(error)}
            self.cola.put(("inscripcion", resultado, datos))

        threading.Thread(target=tarea, daemon=True).start()

    def _fin_inscripcion(self, resultado, datos):
        self.inscribiendo = False
        self.btn_inscribir.configure(state="normal", text="Inscribir Equipo")

        token = resultado.get("token")
        if not resultado.get("ok") and not token:
            self._log_config(
                f"No se pudo inscribir: {resultado.get('error', 'error desconocido')}",
                "error",
            )
            return

        if token and not resultado.get("ok"):
            self._log_config("El equipo ya estaba inscrito; se recuperó su token.", "exito")
        else:
            self._log_config("Equipo inscrito correctamente.", "exito")

        self.token = token
        self.id_equipo = datos["id_equipo"]
        self.url_servidor = datos["url_servidor"]
        self.organizacion = datos["organizacion"]
        self.sede = datos["sede"]
        self.area = datos["area"]

        guardar_token_guardado(
            self.id_equipo,
            self.token,
            organizacion=self.organizacion,
            sede=self.sede,
            area=self.area,
            url_servidor=self.url_servidor,
        )
        self._log_config("Abriendo panel de aprendizaje…")
        self.after(600, self._mostrar_panel)

    # ------------------------------------------------------------------
    # Panel de aprendizaje y monitoreo
    # ------------------------------------------------------------------

    def _mostrar_panel(self):
        if not self.token or not self.id_equipo:
            self._mostrar_configuracion()
            return

        self._detener_monitoreo()
        self.vista = "panel"
        self.geometry("1040x800")
        self.minsize(980, 740)
        self.lbl_subtitulo.configure(
            text=f"{self.id_equipo} · {self.organizacion} — {self.sede} — {self.area}"
        )
        self.lbl_conexion.configure(text="● Conectando…", text_color=AMBAR)
        self._cambiar_frame(self._crear_frame_panel())
        self._iniciar_monitoreo()

    def _crear_frame_panel(self):
        frame = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        frame.pack_propagate(False)

        # --- Tarjeta de aprendizaje ---
        aprendizaje = ctk.CTkFrame(
            frame, fg_color=TARJETA, border_width=1, border_color=BORDE, corner_radius=16
        )
        aprendizaje.pack(fill="x", pady=(0, 14))

        cabecera = ctk.CTkFrame(aprendizaje, fg_color="transparent")
        cabecera.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            cabecera,
            text="Aprendizaje del equipo",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXTO,
        ).pack(side="left")

        self.lbl_aprendizaje_pct = ctk.CTkLabel(
            cabecera,
            text="0 %",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=AZUL,
        )
        self.lbl_aprendizaje_pct.pack(side="right")

        ctk.CTkLabel(
            aprendizaje,
            text=(
                "El sistema observa el comportamiento normal de este equipo para "
                "detectar desviaciones. No requiere ninguna acción del operario."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            wraplength=940,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(2, 10))

        self.barra_aprendizaje = ctk.CTkProgressBar(
            aprendizaje,
            height=14,
            corner_radius=7,
            progress_color=AZUL,
            fg_color="#272832",
        )
        self.barra_aprendizaje.set(0)
        self.barra_aprendizaje.pack(fill="x", padx=20, pady=(0, 10))

        datos_aprendizaje = ctk.CTkFrame(aprendizaje, fg_color="transparent")
        datos_aprendizaje.pack(fill="x", padx=20, pady=(0, 4))

        self.lbl_muestras = ctk.CTkLabel(
            datos_aprendizaje,
            text=f"Muestras: 0 de {MUESTRAS_OBJETIVO}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXTO,
        )
        self.lbl_muestras.pack(side="left")

        self.lbl_dias = ctk.CTkLabel(
            datos_aprendizaje,
            text=f"Días: 0 de {DIAS_OBJETIVO}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXTO,
        )
        self.lbl_dias.pack(side="left", padx=(24, 0))

        self.lbl_aprendizaje_estado = ctk.CTkLabel(
            aprendizaje,
            text="Esperando el primer reporte…",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            anchor="w",
        )
        self.lbl_aprendizaje_estado.pack(fill="x", padx=20, pady=(2, 16))

        # --- Tarjetas de métricas ---
        metricas = ctk.CTkFrame(frame, fg_color="transparent")
        metricas.pack(fill="x", pady=(0, 14))
        metricas.grid_columnconfigure((0, 1, 2), weight=1)

        for columna, (clave, nombre, color) in enumerate(
            [
                ("cpu", "CPU", AZUL),
                ("ram", "RAM", VERDE),
                ("disco", "Disco", AMBAR),
            ]
        ):
            tarjeta = ctk.CTkFrame(
                metricas, fg_color=TARJETA, border_width=1, border_color=BORDE, corner_radius=16
            )
            tarjeta.grid(row=0, column=columna, sticky="ew", padx=(0 if columna == 0 else 7, 0))

            ctk.CTkLabel(
                tarjeta,
                text=nombre,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=SUAVE,
            ).pack(pady=(14, 2))

            valor = ctk.CTkLabel(
                tarjeta,
                text="-- %",
                font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
                text_color=color,
            )
            valor.pack(pady=(0, 14))
            self.tarjetas[clave] = valor

        # --- Estado y actividad ---
        inferior = ctk.CTkFrame(frame, fg_color="transparent")
        inferior.pack(fill="both", expand=True, pady=(0, 12))
        inferior.grid_columnconfigure(0, weight=2)
        inferior.grid_columnconfigure(1, weight=3)
        inferior.grid_rowconfigure(0, weight=1)

        estado = ctk.CTkFrame(
            inferior, fg_color=TARJETA, border_width=1, border_color=BORDE, corner_radius=16
        )
        estado.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

        ctk.CTkLabel(
            estado,
            text="Estado actual",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=SUAVE,
        ).pack(anchor="w", padx=18, pady=(16, 4))

        self.lbl_estado_actual = ctk.CTkLabel(
            estado,
            text="APRENDIENDO",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=AZUL,
        )
        self.lbl_estado_actual.pack(anchor="w", padx=18)

        self.lbl_mensaje_estado = ctk.CTkLabel(
            estado,
            text="Esperando la primera muestra para empezar el aprendizaje…",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            wraplength=300,
            justify="left",
        )
        self.lbl_mensaje_estado.pack(anchor="w", padx=18, pady=(2, 12))

        self.lbl_ultimo_envio = ctk.CTkLabel(
            estado,
            text="Último envío: —",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXTO,
            anchor="w",
        )
        self.lbl_ultimo_envio.pack(fill="x", padx=18, pady=(0, 2))

        self.lbl_proximo_envio = ctk.CTkLabel(
            estado,
            text="Próximo envío: —",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=SUAVE,
            anchor="w",
        )
        self.lbl_proximo_envio.pack(fill="x", padx=18, pady=(0, 16))

        actividad = ctk.CTkFrame(
            inferior, fg_color=TARJETA, border_width=1, border_color=BORDE, corner_radius=16
        )
        actividad.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(
            actividad,
            text="Actividad",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=SUAVE,
        ).pack(anchor="w", padx=18, pady=(16, 6))

        self.area_log_panel = ctk.CTkTextbox(
            actividad,
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            border_width=0,
            fg_color="#141519",
        )
        self.area_log_panel.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # --- Pie ---
        pie = ctk.CTkFrame(frame, fg_color="transparent")
        pie.pack(fill="x")

        fila_superior = ctk.CTkFrame(pie, fg_color="transparent")
        fila_superior.pack(fill="x")

        ctk.CTkLabel(
            fila_superior,
            text="Los datos se envían solo al servidor de la organización.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=SUAVE,
        ).pack(side="left")

        botones = ctk.CTkFrame(fila_superior, fg_color="transparent")
        botones.pack(side="right")

        ctk.CTkButton(
            botones,
            text="Ajustes",
            width=90,
            height=30,
            corner_radius=8,
            fg_color="#272832",
            hover_color="#3E434A",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._abrir_ajustes,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            botones,
            text="Ocultar",
            width=90,
            height=30,
            corner_radius=8,
            fg_color="#272832",
            hover_color="#3E434A",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._ocultar_ventana,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            botones,
            text="Salir",
            width=70,
            height=30,
            corner_radius=8,
            fg_color="#3a1d1d",
            hover_color="#7f1d1d",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._salir,
        ).pack(side="left")

        self.ocultar_inicio = ctk.BooleanVar(value=not mostrar_ventana_inicio())
        ctk.CTkCheckBox(
            pie,
            text=(
                "No mostrar esta ventana al iniciar sesión "
                "(el cliente sigue enviando reportes en segundo plano)"
            ),
            variable=self.ocultar_inicio,
            command=self._cambiar_mostrar_inicio,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=SUAVE,
            fg_color=AZUL,
            hover_color="#2563eb",
            border_color=SUAVE,
            checkbox_width=16,
            checkbox_height=16,
        ).pack(anchor="w", pady=(6, 0))

        return frame

    def _cambiar_mostrar_inicio(self):
        guardar_config_cliente(
            mostrar_ventana_inicio=not self.ocultar_inicio.get()
        )

    def _ocultar_ventana(self):
        self.withdraw()

    def _mostrar_ventana(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))

    def _salir(self):
        from tkinter import messagebox

        if messagebox.askyesno(
            "Salir de SaludPC",
            "Se detendrá el monitoreo hasta que vuelvas a abrir el cliente.\n"
            "¿Salir de SaludPC?",
            parent=self,
        ):
            self._detener_monitoreo()
            self._detener_control()
            self.destroy()

    def _abrir_ajustes(self):
        from tkinter import messagebox

        if messagebox.askyesno(
            "Ajustes",
            "Se detendrá el monitoreo mientras revisas la configuración.\n¿Continuar?",
            parent=self,
        ):
            self._mostrar_configuracion()

    # ------------------------------------------------------------------
    # Monitoreo
    # ------------------------------------------------------------------

    def _iniciar_monitoreo(self):
        self.evento_detener = threading.Event()
        self._log_panel("Monitoreo iniciado. Recopilando la primera muestra…")
        self._actualizar_conexion("● Conectando…", AMBAR)
        hilo = threading.Thread(
            target=self._bucle_monitoreo, args=(self.evento_detener,), daemon=True
        )
        hilo.start()

    def _detener_monitoreo(self):
        if getattr(self, "evento_detener", None) is not None:
            self.evento_detener.set()

    def _bucle_monitoreo(self, evento):
        cliente = ClienteEnterprise(self.id_equipo, self.token, self.url_servidor)
        while not evento.is_set():
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory().percent
                disco = psutil.disk_usage(
                    "C:\\" if sys.platform == "win32" else "/"
                ).percent
            except Exception as error:
                self.cola.put(("envio_error", f"No se pudieron leer las métricas: {error}"))
                if not self._esperar(evento, INTERVALO_ENVIO):
                    break
                continue

            estado, mensaje = self._clasificar(cpu, ram)
            self.cola.put(("metricas", cpu, ram, disco))
            self.cola.put(("estado", estado, mensaje))

            resultado = cliente.enviar_reporte(
                {
                    "estado": estado,
                    "cpu_load": round(cpu, 1),
                    "ram_load": round(ram, 1),
                    "disk_used_pct": round(disco, 1),
                    "cpu_temp": None,
                }
            )

            if resultado.get("ok"):
                hora = datetime.now().strftime("%H:%M:%S")
                self.cola.put(("envio_ok", hora))
                avance = cliente.consultar_progreso()
                if avance.get("ok"):
                    self.cola.put(("progreso", avance))
                else:
                    self.cola.put(
                        (
                            "progreso_error",
                            avance.get("error", "el servidor no informó el avance"),
                        )
                    )
            else:
                self.cola.put(
                    ("envio_error", resultado.get("error", "error desconocido"))
                )

            if not self._esperar(evento, INTERVALO_ENVIO):
                break

    def _esperar(self, evento, segundos):
        for restante in range(segundos, 0, -1):
            if evento.is_set():
                return False
            self.cola.put(("cuenta", restante))
            if evento.wait(1):
                return False
        return True

    def _clasificar(self, cpu, ram):
        if cpu > 90 or ram > 95:
            return "accion", "Recursos al límite. Revisa el equipo."
        if cpu > 80 or ram > 85:
            return "atencion", "Uso elevado de recursos."
        return "ok", "Todo se ve dentro de lo normal."

    # ------------------------------------------------------------------
    # Cola de mensajes desde el hilo de monitoreo
    # ------------------------------------------------------------------

    def _procesar_cola(self):
        try:
            for _ in range(60):
                try:
                    mensaje = self.cola.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._aplicar_mensaje(mensaje)
                except Exception:
                    pass
        finally:
            try:
                if self.winfo_exists():
                    self.after(150, self._procesar_cola)
            except Exception:
                pass

    def _aplicar_mensaje(self, mensaje):
        tipo = mensaje[0]

        if tipo == "inscripcion":
            self._fin_inscripcion(mensaje[1], mensaje[2])
            return

        if tipo == "mostrar":
            self._mostrar_ventana()
            return

        if self.vista != "panel":
            return

        if tipo == "metricas":
            _, cpu, ram, disco = mensaje
            for clave, valor in (("cpu", cpu), ("ram", ram), ("disco", disco)):
                tarjeta = self.tarjetas.get(clave)
                if tarjeta is not None and tarjeta.winfo_exists():
                    tarjeta.configure(text=f"{valor:.1f} %")
            return

        if tipo == "estado":
            _, estado, texto = mensaje
            self.ultimo_estado = (estado, texto)
            self._pintar_estado()
            return

        if tipo == "envio_ok":
            self._actualizar_conexion("● Sistema activo", VERDE)
            if getattr(self, "lbl_ultimo_envio", None) is not None:
                self.lbl_ultimo_envio.configure(text=f"Último envío: {mensaje[1]}")
            self._log_panel("Reporte enviado al servidor central.", "exito")
            return

        if tipo == "envio_error":
            self._actualizar_conexion("● Sin conexión", ROJO)
            self._log_panel(f"Error al enviar: {mensaje[1]}", "error")
            if getattr(self, "lbl_ultimo_envio", None) is not None:
                self.lbl_ultimo_envio.configure(text="Último envío: sin confirmar")
            return

        if tipo == "progreso":
            self._actualizar_progreso(mensaje[1])
            return

        if tipo == "progreso_error":
            if getattr(self, "lbl_aprendizaje_estado", None) is not None:
                self.lbl_aprendizaje_estado.configure(
                    text=f"Conectado. El avance no está disponible: {mensaje[1]}",
                    text_color=SUAVE,
                )
            return

        if tipo == "cuenta":
            if getattr(self, "lbl_proximo_envio", None) is not None:
                self.lbl_proximo_envio.configure(
                    text=f"Próximo envío: en {mensaje[1]} s"
                )
            return

    def _actualizar_progreso(self, datos):
        try:
            muestras = int(datos.get("muestras", 0))
            dias = int(datos.get("dias", 0))
            progreso = max(0, min(100, int(datos.get("progreso", 0))))
            completo = bool(datos.get("aprendizaje_completo"))
        except (TypeError, ValueError):
            return

        self.aprendizaje_completo = completo
        if getattr(self, "barra_aprendizaje", None) is None:
            self._pintar_estado()
            return

        self.barra_aprendizaje.set(progreso / 100)
        self.lbl_aprendizaje_pct.configure(text=f"{progreso} %")
        self.lbl_muestras.configure(
            text=f"Muestras: {muestras} de {MUESTRAS_OBJETIVO}"
        )
        self.lbl_dias.configure(text=f"Días: {dias} de {DIAS_OBJETIVO}")

        if completo:
            self.barra_aprendizaje.configure(progress_color=VERDE)
            self.lbl_aprendizaje_pct.configure(text_color=VERDE)
            self.lbl_aprendizaje_estado.configure(
                text="Aprendizaje completado · el equipo ya tiene su línea base.",
                text_color=VERDE,
            )
        else:
            faltan_muestras = max(0, MUESTRAS_OBJETIVO - muestras)
            faltan_dias = max(0, DIAS_OBJETIVO - dias)
            self.lbl_aprendizaje_estado.configure(
                text=(
                    f"Aprendiendo · faltan {faltan_muestras} muestras y "
                    f"{faltan_dias} día(s). El sistema está funcionando."
                ),
                text_color=SUAVE,
            )

        self._pintar_estado()

    def _pintar_estado(self):
        """Muestra APRENDIENDO hasta completar la línea base."""
        if getattr(self, "lbl_estado_actual", None) is None:
            return

        if not self.aprendizaje_completo:
            self.lbl_estado_actual.configure(text="APRENDIENDO", text_color=AZUL)
            self.lbl_mensaje_estado.configure(
                text=(
                    "El equipo está aprendiendo su comportamiento normal. "
                    "Aún no hay diagnóstico."
                )
            )
            return

        estado, texto = self.ultimo_estado
        colores = {"ok": VERDE, "atencion": AMBAR, "accion": ROJO}
        self.lbl_estado_actual.configure(
            text=estado.upper(), text_color=colores.get(estado, SUAVE)
        )
        self.lbl_mensaje_estado.configure(text=texto)

    def _actualizar_conexion(self, texto, color):
        if getattr(self, "lbl_conexion", None) is not None:
            self.lbl_conexion.configure(text=texto, text_color=color)

    def _log_panel(self, mensaje, tipo="info"):
        area = getattr(self, "area_log_panel", None)
        if area is None or not area.winfo_exists():
            return
        prefijo = {"info": "", "exito": "✓ ", "error": "✗ "}.get(tipo, "")
        hora = datetime.now().strftime("%H:%M:%S")
        area.insert("end", f"[{hora}] {prefijo}{mensaje}\n")
        area.see("end")

    def _al_cerrar(self):
        if self.vista == "panel" and self.token:
            if not getattr(self, "_aviso_oculto", False):
                self._aviso_oculto = True
                from tkinter import messagebox

                messagebox.showinfo(
                    "SaludPC sigue activo",
                    "La ventana se ocultó, pero el cliente sigue enviando "
                    "reportes en segundo plano.\n\n"
                    "Ábrelo de nuevo desde el acceso directo "
                    "«SaludPC Cliente Operario».",
                    parent=self,
                )
            self._ocultar_ventana()
            return
        self._detener_monitoreo()
        self._detener_control()
        self.destroy()


def main():
    if not tomar_instancia():
        avisar_instancia_existente()
        return

    modo = "visible"
    argumentos = sys.argv[1:]
    if "--auto" in argumentos:
        modo = "auto"
    elif "--oculto" in argumentos:
        modo = "oculto"

    app = ClienteGUI(modo_inicio=modo)
    app.mainloop()


if __name__ == "__main__":
    main()
