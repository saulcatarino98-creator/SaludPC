import json
import socket
from datetime import datetime
from pathlib import Path


def load_current_limits(directory=".", now=None):
	"""Load the host's limits for the current ``laboral_N`` or ``finde_N`` slot."""
	now = now or datetime.now()
	hostname = socket.gethostname()
	baseline_path = Path(directory) / f"baseline_{hostname}.json"

	with baseline_path.open("r", encoding="utf-8") as file:
		baseline = json.load(file)

	if not isinstance(baseline, dict):
		raise ValueError(f"El baseline debe ser un objeto JSON: {baseline_path}")
	# cerebro_3.py agrupa los datos bajo el hostname.
	host_limits = baseline.get(hostname, baseline)
	if not isinstance(host_limits, dict):
		raise ValueError(f"Los límites de {hostname} deben ser un objeto JSON")

	day_type = "finde" if now.weekday() >= 5 else "laboral"
	period_key = f"{day_type}_{now.hour}"
	if period_key not in host_limits:
		raise KeyError(f"No hay límites para {period_key} en {baseline_path}")
	return host_limits[period_key]


def measure_current_hardware():
	"""Read a snapshot of current hardware utilization using psutil."""
	import psutil

	root = Path.home().anchor or "/"
	cpu_percent = psutil.cpu_percent(interval=0.1)
	memory = psutil.virtual_memory()
	disk = psutil.disk_usage(root)

	return {
		"timestamp": datetime.now().isoformat(),
		"cpu_percent": cpu_percent,
		"memory_percent": memory.percent,
		"memory_used_bytes": memory.used,
		"memory_total_bytes": memory.total,
		"disk_percent": disk.percent,
		"disk_used_bytes": disk.used,
		"disk_total_bytes": disk.total,
	}


def compare_current_hardware(current, limits, warning_ratio=0.9):
	"""Compare psutil metrics with the CPU, RAM and DISCO baseline sensors."""
	metrics = {
		"cpu_percent": "CPU",
		"memory_percent": "RAM",
		"disk_percent": "DISCO",
	}
	statuses = {"green": 0, "yellow": 1, "red": 2}
	results = {}
	overall = "green"

	for metric, sensor in metrics.items():
		if metric not in current or sensor not in limits:
			continue

		metric_limits = limits[sensor]
		if not isinstance(metric_limits, dict) or "max_normal" not in metric_limits:
			continue

		value = current[metric]
		maximum = metric_limits["max_normal"]
		if not isinstance(value, (int, float)) or not isinstance(maximum, (int, float)):
			continue
		anomaly_limit = next(
			(metric_limits[key] for key in ("anomaly_threshold", "max_anomaly", "statistical_threshold")
			 if key in metric_limits),
			None,
		)

		if anomaly_limit is not None and value > anomaly_limit:
			status = "red"
		elif value > maximum or value >= maximum * warning_ratio:
			status = "yellow"
		else:
			status = "green"

		results[metric] = {
			"sensor": sensor,
			"value": value,
			"status": status,
			"max_normal": maximum,
			"anomaly_threshold": anomaly_limit,
		}
		if statuses[status] > statuses[overall]:
			overall = status

	return {
		"status": overall,
		"color": {"green": "🟢", "yellow": "🟡", "red": "🔴"}[overall],
		"message": _human_status_message(overall, results),
		"metrics": results,
	}


def _human_status_message(status, results):
	"""Summarize the hardware status in plain Spanish, without raw values."""
	if status == "green":
		return "El uso del equipo está dentro de lo normal."

	metric_names = {
		"cpu_percent": "el procesador",
		"memory_percent": "la memoria",
		"disk_percent": "el disco",
	}
	affected = [
		metric_names[metric]
		for metric, details in results.items()
		if details["status"] == status
	]
	resources = ", ".join(affected) or "algunos recursos del equipo"
	if status == "red":
		return f"El uso de {resources} es inusualmente alto. Conviene revisarlo."
	return f"El uso de {resources} está cerca o por encima de lo habitual. Conviene revisarlo."
