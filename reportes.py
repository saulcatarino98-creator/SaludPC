"""Reporte de la semana: un HTML simple de leer, imprimir o guardar en PDF."""

import html
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import almacen
import eventos
import metricas
import rutas
import vigilante

DIAS = 7
REPORTES_A_GUARDAR = 8

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

ETIQUETAS = {
    "ok": "Normal",
    "atencion": "Atención",
    "accion": "Revisar",
    "aprendiendo": "Aprendiendo",
    "sin_datos": "Sin datos",
}

NOMBRES = {
    "cpu_load": "Uso del procesador",
    "cpu_temp": "Temperatura del procesador",
    "ram_load": "Memoria en uso",
    "disk_used_pct": "Espacio del disco",
    "disk_temp": "Temperatura del disco",
    "gpu_temp": "Temperatura de la tarjeta gráfica",
    "gpu_load": "Uso de la tarjeta gráfica",
}

COLORES = {
    "ok": "#12805C",
    "atencion": "#B54708",
    "accion": "#B42318",
    "neutral": "#667085",
}

ORDEN = {"ok": 0, "aprendiendo": 1, "sin_datos": 1, "atencion": 2, "accion": 3}


def fecha_larga(momento):
    return (
        f"{DIAS_SEMANA[momento.weekday()]} {momento.day} de "
        f"{MESES[momento.month - 1]}"
    )


def numero(valor, unidad="", decimales=0):
    if valor is None:
        return "—"
    texto = f"{valor:.{decimales}f}"
    return f"{texto} {unidad}".strip()


def leer_muestras(desde):
    filas = almacen.leer(desde=desde.isoformat(timespec="seconds"))
    por_metrica = {}
    for ts, metrica, valor, unidad in filas:
        try:
            momento = datetime.fromisoformat(ts)
            numero_valor = float(valor)
        except (TypeError, ValueError):
            continue
        por_metrica.setdefault(metrica, []).append((momento, numero_valor, unidad))
    return por_metrica


def limites_para(entrada, metrica, momento):
    """Umbrales del baseline; si el equipo todavía no tiene, usa los generales."""
    if not entrada:
        return metricas.PISOS_AVISO[metrica], metricas.TECHOS_ROJO[metrica]
    try:
        return vigilante.limite_para(entrada, momento.astimezone())
    except (KeyError, TypeError):
        return metricas.PISOS_AVISO[metrica], metricas.TECHOS_ROJO[metrica]


def analizar(por_metrica, baseline):
    """Devuelve el resumen por métrica y el estado global minuto a minuto."""
    resumen = []
    estado_por_momento = {}

    for metrica, lista in por_metrica.items():
        if metrica not in metricas.UNIDADES:
            continue

        entrada = (baseline.get("metricas") or {}).get(metrica, {})
        valores = [valor for _momento, valor, _unidad in lista]
        unidad = metricas.UNIDADES[metrica]

        estados = []
        por_dia = {}
        for momento, valor, _ in lista:
            aviso, rojo = limites_para(entrada, metrica, momento)
            if valor >= rojo:
                estado = "accion"
            elif valor >= aviso:
                estado = "atencion"
            else:
                estado = "ok"
            estados.append((momento, estado))

            dia = momento.astimezone().date().isoformat()
            por_dia.setdefault(dia, []).append(valor)

            anterior = estado_por_momento.get(momento)
            if anterior is None or ORDEN[estado] > ORDEN[anterior]:
                estado_por_momento[momento] = estado

        avisos = sum(1 for _m, estado in estados if estado == "atencion")
        rojos = sum(1 for _m, estado in estados if estado == "accion")
        aviso, rojo = limites_para(entrada, metrica, datetime.now().astimezone())

        resumen.append(
            {
                "metrica": metrica,
                "nombre": NOMBRES.get(metrica, metricas.NOMBRES[metrica]),
                "unidad": unidad,
                "n": len(valores),
                "promedio": sum(valores) / len(valores),
                "minimo": min(valores),
                "maximo": max(valores),
                "limite_aviso": aviso,
                "limite_rojo": rojo,
                "avisos": avisos,
                "rojos": rojos,
                "pct_aviso": 100 * avisos / len(valores),
                "estado": "accion" if rojos else ("atencion" if avisos else "ok"),
                "por_dia": por_dia,
            }
        )

    resumen.sort(key=lambda fila: ORDEN[fila["estado"]], reverse=True)
    return resumen, estado_por_momento


def segmentos(estado_por_momento):
    total = len(estado_por_momento) or 1
    cuenta = {"ok": 0, "atencion": 0, "accion": 0}
    for estado in estado_por_momento.values():
        if estado in cuenta:
            cuenta[estado] += 1
    return {clave: 100 * valor / total for clave, valor in cuenta.items()}, total


def chispa(por_dia, dias):
    """Línea simple con el promedio de cada día, para ver la tendencia."""
    valores = []
    for dia in dias:
        lista = por_dia.get(dia)
        if lista:
            valores.append(sum(lista) / len(lista))
        else:
            valores.append(None)

    puntos = []
    presentes = [valor for valor in valores if valor is not None]
    if len(presentes) < 2:
        return ""
    minimo, maximo = min(presentes), max(presentes)
    rango = (maximo - minimo) or 1
    ancho = 100.0 / max(1, len(valores) - 1)
    for indice, valor in enumerate(valores):
        if valor is None:
            continue
        x = indice * ancho
        y = 26 - (valor - minimo) / rango * 20
        puntos.append(f"{x:.1f},{y:.1f}")
    if len(puntos) < 2:
        return ""
    return " ".join(puntos)


def texto_interpretacion(resumen, porcentajes, eventos_semana, horas):
    frases = []

    if horas < 1:
        frases.append(
            "Casi no hay mediciones esta semana: el equipo estuvo apagado o el "
            "programa no llegó a funcionar."
        )
        return frases

    if porcentajes["ok"] >= 95:
        frases.append(
            "El equipo estuvo prácticamente todo el tiempo dentro de lo normal."
        )
    elif porcentajes["ok"] >= 80:
        frases.append(
            "El equipo estuvo bien la mayor parte del tiempo, con algunos "
            "momentos de atención."
        )
    else:
        frases.append(
            "Hubo varios momentos fuera de lo normal. Conviene mirar el detalle "
            "de abajo para ver qué fue lo que más se movió."
        )

    peor = next(
        (fila for fila in resumen if fila["estado"] != "ok"),
        resumen[0] if resumen else None,
    )
    if peor:
        nombre = metricas.NOMBRES.get(peor["metrica"], peor["nombre"])
        frases.append(
            f"Lo que más se movió fue {nombre}: llegó a "
            f"{numero(peor['maximo'], peor['unidad'])} y el límite para este "
            f"equipo está en {numero(peor['limite_aviso'], peor['unidad'])}."
        )

    disco = next((fila for fila in resumen if fila["metrica"] == "disk_used_pct"), None)
    if disco:
        if disco["promedio"] >= 90:
            frases.append(
                f"El disco está al {numero(disco['promedio'], '%', 1)}: queda "
                "poco espacio libre."
            )
        elif disco["promedio"] >= 75:
            frases.append(
                f"El disco está al {numero(disco['promedio'], '%', 1)}: conviene "
                "ir liberando espacio."
            )
        else:
            frases.append(
                f"El disco está al {numero(disco['promedio'], '%', 1)}: hay "
                "espacio de sobra."
            )

    suspensiones = sum(1 for evento in eventos_semana if evento[1] == "suspension")
    apagados = sum(1 for evento in eventos_semana if evento[1] == "apagado")
    if suspensiones:
        frases.append(
            f"El equipo se suspendió {suspensiones} "
            f"{'vez' if suspensiones == 1 else 'veces'}. Es normal si lo dejás "
            "en reposo o cerrás la tapa."
        )
    if apagados:
        frases.append(
            f"Se apagó o reinició {apagados} "
            f"{'vez' if apagados == 1 else 'veces'}."
        )
    if not suspensiones and not apagados:
        frases.append("No hubo interrupciones: el equipo estuvo encendido de corrido.")

    amarillos = sum(1 for evento in eventos_semana if evento[1] == "estado")
    if amarillos:
        verbo = "registró" if amarillos == 1 else "registraron"
        frases.append(
            f"Se {verbo} {amarillos} "
            f"{'aviso' if amarillos == 1 else 'avisos'} al salir de lo habitual."
        )
    else:
        frases.append("No hubo avisos: todo se mantuvo dentro de lo esperado.")

    return frases


def tarjeta(fila, dias):
    puntos = chispa(fila["por_dia"], dias)
    color = COLORES.get(fila["estado"], COLORES["neutral"])
    linea = (
        f'<polyline points="{puntos}" fill="none" stroke="{color}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        if puntos
        else ""
    )
    return f"""
    <article class="card">
      <div class="card-head">
        <h3>{html.escape(fila['nombre'][0].upper() + fila['nombre'][1:])}</h3>
        <span class="tag" style="--tag:{color}">{ETIQUETAS[fila['estado']]}</span>
      </div>
      <div class="card-value">{numero(fila['promedio'], fila['unidad'], 1)}</div>
      <div class="card-sub">promedio de la semana</div>
      <svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none">{linea}</svg>
      <dl class="card-stats">
        <div><dt>Máximo</dt><dd>{numero(fila['maximo'], fila['unidad'])}</dd></div>
        <div><dt>Normal hasta</dt><dd>{numero(fila['limite_aviso'], fila['unidad'])}</dd></div>
        <div><dt>Fuera de rango</dt><dd>{fila['pct_aviso']:.1f} %</dd></div>
      </dl>
    </article>
    """


def lista_eventos(eventos_semana):
    if not eventos_semana:
        return (
            '<p class="empty">Todavía no hay eventos guardados. La próxima '
            "semana va a aparecer lo que pase con el equipo.</p>"
        )

    filas = []
    for ts, tipo, detalle, valor in eventos_semana:
        try:
            momento = datetime.fromisoformat(ts).astimezone()
        except (TypeError, ValueError):
            continue
        titulo, texto, tono = eventos.describir(ts, tipo, detalle, valor)
        color = COLORES.get(tono, COLORES["neutral"])
        filas.append(
            f"""
        <li>
          <span class="dot" style="--dot:{color}"></span>
          <div>
            <strong>{html.escape(titulo)}</strong>
            <span class="when">{momento:%d/%m %H:%M}</span>
            <p>{html.escape(texto)}</p>
          </div>
        </li>"""
        )
    return '<ul class="events">' + "".join(filas) + "</ul>"


def construir(ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)

    desde = ahora - timedelta(days=DIAS)
    baseline = vigilante.cargar_baseline() or {}
    por_metrica = leer_muestras(desde)
    resumen, estado_por_momento = analizar(por_metrica, baseline)
    porcentajes, minutos = segmentos(estado_por_momento)
    horas = minutos / 60

    eventos_semana = almacen.leer_eventos(
        desde=desde.isoformat(timespec="seconds"), limite=200
    )

    dias = [
        (desde + timedelta(days=indice)).astimezone().date().isoformat()
        for indice in range(DIAS + 1)
    ][-DIAS:]

    frases = texto_interpretacion(resumen, porcentajes, eventos_semana, horas)

    local_ahora = ahora.astimezone()
    local_desde = desde.astimezone()
    generado = datetime.now().astimezone()

    tarjetas = "".join(tarjeta(fila, dias) for fila in resumen) or (
        '<p class="empty">No hay mediciones suficientes todavía.</p>'
    )

    return {
        "generado": generado,
        "desde": local_desde,
        "hasta": local_ahora,
        "equipo": socket.gethostname(),
        "porcentajes": porcentajes,
        "horas": horas,
        "mediciones": minutos,
        "tarjetas": tarjetas,
        "eventos": lista_eventos(eventos_semana),
        "frases": frases,
        "aprendiendo": bool(baseline.get("aprendiendo")),
    }


def renderizar(datos):
    ancho_ok = max(0.0, min(100.0, datos["porcentajes"]["ok"]))
    ancho_atencion = max(0.0, min(100.0 - ancho_ok, datos["porcentajes"]["atencion"]))
    ancho_accion = max(0.0, 100.0 - ancho_ok - ancho_atencion)

    frases = "".join(f"<p>{html.escape(frase)}</p>" for frase in datos["frases"])
    aviso_aprendizaje = (
        '<p class="note">Todavía estamos conociendo este equipo. Cuando juntemos '
        "tres días de datos, los límites van a ser propios y no generales.</p>"
        if datos["aprendiendo"]
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salud de mi equipo — reporte semanal</title>
<style>
  :root {{
    --bg: #F4F6F9;
    --card: #FFFFFF;
    --ink: #101828;
    --muted: #667085;
    --line: #E4E7EC;
    --ok: #12805C;
    --warn: #B54708;
    --bad: #B42318;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.55;
  }}
  .wrap {{ max-width: 940px; margin: 0 auto; padding: 40px 24px 56px; }}
  header {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-end; margin-bottom: 24px; }}
  header h1 {{ margin: 0; font-size: 26px; letter-spacing: -0.02em; }}
  header p {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; }}
  .equipo {{ text-align: right; color: var(--muted); font-size: 13px; }}
  .hero {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 28px;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 32px;
    align-items: center;
    margin-bottom: 28px;
  }}
  .big {{ font-size: 54px; font-weight: 600; letter-spacing: -0.04em; line-height: 1; }}
  .big small {{ display: block; font-size: 13px; font-weight: 400; color: var(--muted); letter-spacing: 0; margin-top: 6px; }}
  .bar {{ display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: var(--line); }}
  .bar span {{ display: block; height: 100%; }}
  .legend {{ display: flex; gap: 18px; margin-top: 12px; font-size: 13px; color: var(--muted); flex-wrap: wrap; }}
  .legend i {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }}
  h2 {{ font-size: 17px; margin: 36px 0 14px; letter-spacing: -0.01em; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
  .card h3 {{ margin: 0; font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .tag {{ font-size: 11px; font-weight: 600; color: var(--tag); border: 1px solid color-mix(in srgb, var(--tag) 30%, transparent); background: color-mix(in srgb, var(--tag) 8%, transparent); padding: 2px 8px; border-radius: 999px; white-space: nowrap; }}
  .card-value {{ font-size: 30px; font-weight: 600; letter-spacing: -0.03em; margin-top: 10px; }}
  .card-sub {{ color: var(--muted); font-size: 12px; }}
  .spark {{ width: 100%; height: 34px; margin: 10px 0 4px; }}
  .card-stats {{ display: flex; gap: 16px; margin: 6px 0 0; flex-wrap: wrap; }}
  .card-stats div {{ margin: 0; }}
  .card-stats dt {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .card-stats dd {{ margin: 0; font-size: 14px; font-weight: 600; }}
  .events {{ list-style: none; margin: 0; padding: 0; background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }}
  .events li {{ display: flex; gap: 12px; padding: 14px 18px; border-bottom: 1px solid var(--line); }}
  .events li:last-child {{ border-bottom: 0; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--dot); margin-top: 8px; flex: none; }}
  .when {{ color: var(--muted); font-size: 12px; margin-left: 8px; }}
  .events p {{ margin: 2px 0 0; color: var(--muted); font-size: 13px; }}
  .note {{ background: #FFFAEB; border: 1px solid #FEDF89; border-radius: 12px; padding: 14px 18px; font-size: 14px; }}
  .why {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 6px 22px 18px; }}
  .why p {{ color: #344054; }}
  footer {{ margin-top: 36px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); padding-top: 16px; }}
  .empty {{ color: var(--muted); font-size: 14px; }}
  @media print {{
    body {{ background: #fff; font-size: 12px; }}
    .wrap {{ padding: 0; max-width: none; }}
    .card, .hero, .events, .why {{ break-inside: avoid; }}
    .spark {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Salud de mi equipo</h1>
      <p>Reporte de la semana · del {fecha_larga(datos['desde'])} al {fecha_larga(datos['hasta'])}</p>
    </div>
    <div class="equipo">
      {html.escape(datos['equipo'])}<br>
      {datos['horas']:.1f} horas con datos
    </div>
  </header>

  <section class="hero">
    <div class="big">
      {datos['porcentajes']['ok']:.0f} %
      <small>del tiempo dentro de lo normal</small>
    </div>
    <div>
      <div class="bar">
        <span style="width:{ancho_ok:.1f}%;background:var(--ok)"></span>
        <span style="width:{ancho_atencion:.1f}%;background:var(--warn)"></span>
        <span style="width:{ancho_accion:.1f}%;background:var(--bad)"></span>
      </div>
      <div class="legend">
        <span><i style="background:var(--ok)"></i>Normal {datos['porcentajes']['ok']:.0f} %</span>
        <span><i style="background:var(--warn)"></i>Atención {datos['porcentajes']['atencion']:.1f} %</span>
        <span><i style="background:var(--bad)"></i>Revisar {datos['porcentajes']['accion']:.1f} %</span>
      </div>
    </div>
  </section>

  {aviso_aprendizaje}

  <h2>Cómo estuvo cada cosa</h2>
  <div class="grid">{datos['tarjetas']}</div>

  <h2>Qué pasó esta semana</h2>
  {datos['eventos']}

  <h2>Qué significa</h2>
  <section class="why">{frases}</section>

  <footer>
    Generado el {datos['generado']:%d/%m/%Y a las %H:%M} por Salud de mi equipo.
    Las mediciones son de este equipo y se guardan en la computadora: no se envía
    nada a internet.
  </footer>
</div>
</body>
</html>
"""


def generar(dias=DIAS, ahora=None):
    """Crea el HTML y devuelve la ruta del archivo."""
    datos = construir(ahora)
    contenido = renderizar(datos)
    carpeta = rutas.carpeta_reportes()
    ruta = carpeta / f"reporte_{datetime.now():%Y-%m-%d}.html"
    ruta.write_text(contenido, encoding="utf-8")

    # Se conservan los últimos reportes; los viejos se descartan solos.
    anteriores = sorted(carpeta.glob("reporte_*.html"))
    for viejo in anteriores[:-REPORTES_A_GUARDAR]:
        try:
            viejo.unlink()
        except OSError:
            pass
    return ruta


def abrir(ruta):
    try:
        os.startfile(str(ruta))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    return True


if __name__ == "__main__":
    print(generar())
