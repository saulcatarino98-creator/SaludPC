from contextlib import ExitStack
from types import SimpleNamespace
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import colector
from main import Ventana


class FakeWidget:
    def __init__(self):
        self.options = {}
        self.progress = None

    def configure(self, **options):
        self.options.update(options)

    def set(self, value):
        self.progress = value


class LiveMetricsTests(unittest.TestCase):
    def test_live_read_does_not_store_or_affect_learning(self):
        with ExitStack() as stack:
            stack.enter_context(patch("colector.obtener_equipo", return_value=None))
            cpu_percent = stack.enter_context(
                patch("colector.psutil.cpu_percent", return_value=21.0)
            )
            stack.enter_context(
                patch(
                    "colector.psutil.virtual_memory",
                    return_value=SimpleNamespace(percent=43.0),
                )
            )
            stack.enter_context(
                patch(
                    "colector.psutil.disk_usage",
                    return_value=SimpleNamespace(percent=61.0),
                )
            )
            guardar = stack.enter_context(patch("colector.almacen.guardar"))
            valores = colector.leer_actuales()

        self.assertEqual(
            valores,
            {
                "cpu_load": (21.0, "%"),
                "ram_load": (43.0, "%"),
                "disk_used_pct": (61.0, "%"),
            },
        )
        cpu_percent.assert_called_once_with(interval=0.25)
        guardar.assert_not_called()

    def test_scheduled_collection_still_stores_a_sample(self):
        with ExitStack() as stack:
            stack.enter_context(patch("colector.obtener_equipo", return_value=None))
            cpu_percent = stack.enter_context(
                patch("colector.psutil.cpu_percent", return_value=21.0)
            )
            stack.enter_context(
                patch(
                    "colector.psutil.virtual_memory",
                    return_value=SimpleNamespace(percent=43.0),
                )
            )
            stack.enter_context(
                patch(
                    "colector.psutil.disk_usage",
                    return_value=SimpleNamespace(percent=61.0),
                )
            )
            guardar = stack.enter_context(
                patch("colector.almacen.guardar", return_value=3)
            )
            momento, guardadas, valores = colector.recolectar()

        self.assertEqual(guardadas, 3)
        self.assertEqual(valores["cpu_load"], (21.0, "%"))
        self.assertIsNotNone(momento.tzinfo)
        cpu_percent.assert_called_once_with(interval=0.5)
        guardar.assert_called_once()

    def test_dashboard_cards_show_live_values_instead_of_saved_values(self):
        ventana = Ventana.__new__(Ventana)
        # Atributos mínimos que _pintar_tarjetas necesita; Ventana.__init__
        # no se ejecuta (evita crear una ventana tkinter real en el test).
        ventana.ultimo = {
            "detalles": [
                {
                    "metrica": "cpu_load",
                    "unidad": "%",
                    "ultimo": 12.0,
                    "limite_aviso": 85.0,
                    "limite_rojo": 98.0,
                    "estado": "ok",
                }
            ]
        }
        ventana.lecturas_actuales = {"cpu_load": (74.0, "%")}
        valor = FakeWidget()
        barra = FakeWidget()
        pie = FakeWidget()
        ventana.tarjetas = {
            "cpu_load": {"valor": valor, "barra": barra, "pie": pie}
        }

        ventana._pintar_tarjetas()

        self.assertEqual(valor.options["text"], "74 %")
        self.assertAlmostEqual(barra.progress, 74.0 / 98.0)
        self.assertIn("en vivo", pie.options["text"])


if __name__ == "__main__":
    unittest.main()
