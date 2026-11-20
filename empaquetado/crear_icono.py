"""Genera el icono del instalador (semáforo)."""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).with_name("icono.ico")

imagen = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
dibujo = ImageDraw.Draw(imagen)
dibujo.rounded_rectangle((12, 12, 244, 244), radius=52, fill="#1e3a5f")
for centro, color in ((74, "#e53935"), (128, "#fdd835"), (182, "#43a047")):
    dibujo.ellipse(
        (98, centro - 24, 158, centro + 24),
        fill=color,
        outline="#0f2236",
        width=3,
    )

imagen.save(
    DESTINO,
    sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
)
print(f"Icono generado: {DESTINO}")
