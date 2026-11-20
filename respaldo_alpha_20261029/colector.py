import os
import csv
import tkinter as tk
import wmi
from datetime import datetime

ventana = tk.Tk()
ventana.title("alpha")
ventana.geometry("400x300")

resultados = tk.Text(ventana, wrap="word")
resultados.pack(fill="both", expand=True, padx=10, pady=10)

try:
    ordenador = wmi.WMI()
    sistema = ordenador.Win32_OperatingSystem()[0]
    cpu = ordenador.Win32_Processor()[0]
    memoria = ordenador.Win32_ComputerSystem()[0]

    texto = (
        f"Sistema: {sistema.Caption}\n"
        f"Versión: {sistema.Version}\n"
        f"Arquitectura: {sistema.OSArchitecture}\n"
        f"Procesador: {cpu.Name}\n"
        f"Memoria RAM: {round(int(memoria.TotalPhysicalMemory) / (1024 ** 3), 2)} GB\n"
    )
except Exception as error:
    texto = f"No se pudo consultar WMI:\n{error}"

# LibreHardwareMonitorLib.dll debe estar junto al script o en una ruta estándar.
try:
    import clr

    ruta_script = os.path.dirname(os.path.abspath(__file__))
    dll = os.path.join(ruta_script, "LibreHardwareMonitorLib.dll")
    if not os.path.isfile(dll):
        raise FileNotFoundError(f"No se encontró el archivo: {dll}")

    clr.AddReference(dll)
    hardware_namespace = __import__(
        "LibreHardwareMonitor.Hardware", fromlist=["Computer"]
    )
    Computer = hardware_namespace.Computer

    equipo = Computer()
    equipo.IsCpuEnabled = True
    equipo.IsGpuEnabled = True
    equipo.IsMotherboardEnabled = True
    equipo.IsControllerEnabled = True
    equipo.IsMemoryEnabled = True
    equipo.IsStorageEnabled = True
    equipo.IsNetworkEnabled = True
    equipo.Open()
    sensores_disponibles = True
except Exception as error:
    equipo = None
    sensores_disponibles = False
    texto += f"\nSensores: {error}"


def leer_sensores(hardware, registros=None, componente=None):
    valores = []
    for sensor in hardware.Sensors:
        if sensor.Value is not None:
            valores.append(f"  {sensor.Name}: {sensor.Value:.1f} {sensor.SensorType}")
            if registros is not None:
                registros.append((componente or hardware.Name, sensor.Name, sensor.Value, str(sensor.SensorType)))
    for subhardware in hardware.SubHardware:
        subhardware.Update()
        valores.extend(leer_sensores(subhardware, registros, componente or hardware.Name))
    return valores


def actualizar_sensores():
    if sensores_disponibles:
        try:
            contenido = texto + "\n\nSensores en tiempo real:\n"
            registros = []

            def guardar_csv(datos):
                ruta_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial_hardware.csv")
                existe = os.path.isfile(ruta_csv) and os.path.getsize(ruta_csv) > 0
                with open(ruta_csv, "a", newline="", encoding="utf-8") as archivo:
                    escritor = csv.writer(archivo)
                    if not existe:
                        escritor.writerow(("fecha_hora", "componente", "sensor", "valor", "tipo"))
                    fecha_hora = datetime.now().isoformat(timespec="seconds")
                    escritor.writerows((fecha_hora, *dato) for dato in datos)

            for hardware in equipo.Hardware:
                hardware.Update()
                contenido += f"\n{hardware.Name} ({hardware.HardwareType}):\n"
                contenido += "\n".join(leer_sensores(hardware, registros)) + "\n"

            guardar_csv(registros)

            resultados.config(state="normal")
            resultados.delete("1.0", "end")
            resultados.insert("1.0", contenido)
            resultados.config(state="disabled")
        except Exception as error:
            resultados.config(state="normal")
            resultados.delete("1.0", "end")
            resultados.insert("1.0", texto + f"\n\nError leyendo sensores:\n{error}")
            resultados.config(state="disabled")

    ventana.after(1000, actualizar_sensores)


resultados.insert("1.0", texto)
resultados.config(state="disabled")
ventana.after(100, actualizar_sensores)
ventana.mainloop()

