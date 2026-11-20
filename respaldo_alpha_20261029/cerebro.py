import pandas as pd
import json
import socket
import math
from datetime import datetime

historial = pd.read_csv("historial_hardware.csv")
historial["fecha_hora"] = pd.to_datetime(historial["fecha_hora"])
historial["valor"] = pd.to_numeric(historial["valor"], errors="coerce")
historial = historial.dropna(subset=["valor"])
historial = historial[historial["valor"].map(math.isfinite)]
historial = historial[historial["sensor"].astype(str).str.strip().str.upper().isin(["CPU", "RAM", "DISCO"])]

filas_antes = len(historial)
df = historial.groupby(
	[pd.Grouper(key="fecha_hora", freq="1min"), "componente", "sensor", "tipo"]
)["valor"].mean().reset_index()
print(f"Filas antes de agrupar: {filas_antes}")
print(f"Filas después de agrupar: {len(df)}")

df["hora"] = df["fecha_hora"].dt.hour
df["tipo_dia"] = df["fecha_hora"].dt.dayofweek.lt(5).map({True: "laboral", False: "finde"})
df["franja"] = df["tipo_dia"] + "_" + df["hora"].astype(str)

resumen = df.groupby(["componente", "sensor", "tipo", "franja"])["valor"].agg(
	N="count",
	mu="mean",
	sigma="std",
	Q1=lambda valores: valores.quantile(0.25),
	Q3=lambda valores: valores.quantile(0.75),
	P99=lambda valores: valores.quantile(0.99),
).reset_index()
resumen["IQR"] = resumen["Q3"] - resumen["Q1"]

MIN_MUESTRAS = 30
def umbral_por_defecto(fila):
	"""Devuelve un límite conservador según la métrica del sensor."""
	texto = " ".join(
		str(fila[columna]).strip().lower()
		for columna in ("componente", "sensor", "tipo")
		if pd.notna(fila[columna])
	)

	if any(indicador in texto for indicador in ("temp", "temperatura", "°c", "celsius")):
		return 85.0 if "cpu" in texto else 80.0
	if "disco" in texto or "disk" in texto:
		return 98.0
	if any(indicador in texto for indicador in ("cpu", "ram", "porcentaje", "%", "uso", "utiliz")):
		return 95.0
	return 95.0

def numero_json(valor):
	"""Convierte valores no finitos en None para serializarlos como null en JSON."""
	if pd.isna(valor) or not math.isfinite(float(valor)):
		return None
	return float(valor)

resumen["limite_Z"] = resumen["mu"] + 3 * resumen["sigma"]
resumen["limite_IQR"] = resumen["Q3"] + 1.5 * resumen["IQR"]
resumen["max_normal"] = resumen[["limite_Z", "limite_IQR"]].min(axis=1)
mask_pocas_muestras = resumen["N"] < MIN_MUESTRAS
resumen.loc[mask_pocas_muestras, "max_normal"] = resumen.loc[mask_pocas_muestras].apply(
	umbral_por_defecto, axis=1
)

print(resumen.shape)
print(resumen.head())

hostname = socket.gethostname()
baseline = {
	hostname: {},
	"generado_en": datetime.now().astimezone().isoformat(),
	"version": 1,
}

for _, fila in resumen.iterrows():
	franja = fila["franja"]
	sensor = fila["sensor"]
	baseline[hostname].setdefault(franja, {})[sensor] = {
		"mu": numero_json(fila["mu"]),
		"sigma": numero_json(fila["sigma"]),
		"max_normal": numero_json(fila["max_normal"]),
		"n": int(fila["N"]),
	}

with open(f"baseline_{hostname}.json", "w", encoding="utf-8") as archivo:
	json.dump(baseline, archivo, indent=2, ensure_ascii=False)
