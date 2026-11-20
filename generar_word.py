# -*- coding: utf-8 -*-
"""Genera BITACORA_SaludPC.docx a partir de BITACORA.md usando Word."""

import html
import re
import sys
from pathlib import Path

import pythoncom
import win32com.client as win32

BASE = Path(r"C:\Users\INFO\Desktop\pipia")
ORIGEN = BASE / "BITACORA.md"
DESTINO = BASE / "BITACORA_SaludPC.docx"
PDF = BASE / "BITACORA_SaludPC.pdf"
HTML_TMP = BASE / "_bitacora_word.html"


def inline(texto: str) -> str:
    """Convierte el formato en linea de Markdown a HTML."""
    texto = html.escape(texto, quote=False)

    codigos = []

    def guardar(m):
        codigos.append(m.group(1))
        return f"\x00{len(codigos) - 1}\x00"

    texto = re.sub(r"`([^`]+)`", guardar, texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', texto)

    for i, codigo in enumerate(codigos):
        texto = texto.replace(f"\x00{i}\x00", f"<code>{codigo}</code>")
    return texto


def es_tabla(linea: str) -> bool:
    s = linea.strip()
    return s.startswith("|") and s.count("|") >= 2


def es_separador(linea: str) -> bool:
    s = linea.strip()
    if not s.startswith("|"):
        return False
    celdas = [c.strip() for c in s.strip("|").split("|")]
    return bool(celdas) and all(re.fullmatch(r":?-{3,}:?", c) for c in celdas)


def celdas(linea: str):
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def convertir_markdown(md: str) -> str:
    lineas = md.splitlines()
    salida = []
    parrafo = []
    lista = None
    i = 0

    def cerrar_parrafo():
        nonlocal parrafo
        if parrafo:
            salida.append("<p>" + " ".join(inline(x) for x in parrafo) + "</p>")
            parrafo = []

    def cerrar_lista():
        nonlocal lista
        if lista:
            salida.append(f"</{lista}>")
            lista = None

    while i < len(lineas):
        linea = lineas[i]
        limpia = linea.strip()

        # Codigo
        if limpia.startswith("```"):
            cerrar_parrafo()
            cerrar_lista()
            i += 1
            bloque = []
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                bloque.append(lineas[i])
                i += 1
            i += 1
            salida.append("<pre><code>" + html.escape("\n".join(bloque)) + "</code></pre>")
            continue

        # Linea en blanco
        if not limpia:
            cerrar_parrafo()
            cerrar_lista()
            i += 1
            continue

        # Separador
        if re.fullmatch(r"-{3,}", limpia):
            cerrar_parrafo()
            cerrar_lista()
            salida.append("<hr>")
            i += 1
            continue

        # Titulos
        m = re.match(r"^(#{1,4})\s+(.*)$", limpia)
        if m:
            cerrar_parrafo()
            cerrar_lista()
            nivel = len(m.group(1))
            # El documento empieza en ##: se mapea a H1 para que el indice
            # jerarquice bien las secciones y subsecciones.
            nivel_word = max(1, nivel - 1)
            salida.append(f"<h{nivel_word}>{inline(m.group(2))}</h{nivel_word}>")
            i += 1
            continue

        # Cita
        if limpia.startswith("> "):
            cerrar_parrafo()
            cerrar_lista()
            salida.append("<blockquote>" + inline(limpia[2:]) + "</blockquote>")
            i += 1
            continue

        # Tabla
        if es_tabla(linea) and i + 1 < len(lineas) and es_separador(lineas[i + 1]):
            cerrar_parrafo()
            cerrar_lista()
            cabecera = celdas(linea)
            i += 2
            filas = []
            while i < len(lineas) and es_tabla(lineas[i]):
                filas.append(celdas(lineas[i]))
                i += 1
            salida.append("<table>")
            salida.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cabecera) + "</tr></thead>")
            salida.append("<tbody>")
            for fila in filas:
                salida.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in fila) + "</tr>")
            salida.append("</tbody></table>")
            continue

        # Listas
        m = re.match(r"^(\s{2,})-\s+(.*)$", linea)
        if m and lista == "ul":
            salida.append(f'<li class="sub">{inline(m.group(2))}</li>')
            i += 1
            continue

        m = re.match(r"^-\s+(.*)$", linea)
        if m:
            cerrar_parrafo()
            if lista != "ul":
                cerrar_lista()
                salida.append("<ul>")
                lista = "ul"
            salida.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", linea)
        if m:
            cerrar_parrafo()
            cerrar_lista()
            salida.append(
                f'<p class="num"><span class="num-n">{m.group(1)}.</span> '
                f"{inline(m.group(2))}</p>"
            )
            i += 1
            continue

        # Parrafo normal
        if lista:
            cerrar_lista()
        parrafo.append(limpia)
        i += 1

    cerrar_parrafo()
    cerrar_lista()
    return "\n".join(salida)


CSS = """
@page {
    size: A4;
    margin: 2.2cm 2.1cm 2.1cm 2.1cm;
}
body {
    font-family: Calibri, Carlito, sans-serif;
    font-size: 10.5pt;
    line-height: 1.38;
    color: #23302F;
    margin: 0;
}
p { margin: 0 0 8pt 0; text-align: justify; }
h1 {
    font-family: "Calibri Light", Calibri, sans-serif;
    font-size: 17pt;
    color: #0F4C5C;
    margin: 18pt 0 7pt 0;
    padding-bottom: 3pt;
    border-bottom: 1.2pt solid #C9DCDD;
    page-break-after: avoid;
    mso-outline-level: 1;
}
h2 {
    font-family: "Calibri Light", Calibri, sans-serif;
    font-size: 13pt;
    color: #17606F;
    margin: 13pt 0 5pt 0;
    page-break-after: avoid;
    mso-outline-level: 2;
}
h3 {
    font-family: Calibri, sans-serif;
    font-size: 11pt;
    color: #2B4A50;
    margin: 11pt 0 4pt 0;
    page-break-after: avoid;
    mso-outline-level: 3;
}
strong { color: #17383F; }
code {
    font-family: Consolas, "Courier New", monospace;
    font-size: 9pt;
    background: #F1F4F4;
    color: #1E4A54;
    padding: 0 2pt;
}
pre {
    font-family: Consolas, "Courier New", monospace;
    font-size: 9pt;
    background: #F4F6F6;
    border-left: 3pt solid #7FAEB3;
    padding: 6pt 9pt;
    margin: 7pt 0 10pt 0;
    white-space: pre-wrap;
}
pre code { background: transparent; padding: 0; }
blockquote {
    margin: 8pt 0;
    padding: 5pt 10pt;
    border-left: 3pt solid #7FAEB3;
    background: #F4F8F8;
    color: #35575C;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 7pt 0 12pt 0;
    font-size: 9pt;
    page-break-inside: avoid;
    mso-table-lspace: 0pt;
    mso-table-rspace: 0pt;
}
th {
    background: #E4F0F1;
    color: #123E47;
    font-weight: bold;
    text-align: left;
    border: 0.75pt solid #B9CDD0;
    padding: 4pt 5pt;
    vertical-align: top;
}
td {
    border: 0.75pt solid #C9D7D9;
    padding: 3.5pt 5pt;
    vertical-align: top;
}
tr { page-break-inside: avoid; }
ul, ol { margin: 3pt 0 9pt 16pt; padding: 0; }
li { margin: 0 0 3.5pt 0; text-align: justify; }
p.num {
    margin: 0 0 5pt 0;
    padding-left: 20pt;
    text-indent: -20pt;
    text-align: justify;
}
.num-n { font-weight: bold; color: #17606F; }
hr {
    border: none;
    border-top: 0.75pt solid #D6E1E2;
    margin: 14pt 0;
}
a { color: #17606F; text-decoration: none; }
.pagebreak { page-break-before: always; height: 0; line-height: 0; font-size: 1pt; }
li.sub { margin-left: 18pt; list-style-type: circle; }

/* Portada */
.cover { margin-top: 4.2cm; }
.cover-kicker {
    font-size: 9pt;
    letter-spacing: 2.2pt;
    text-transform: uppercase;
    color: #2C7A86;
    margin-bottom: 14pt;
}
.cover-title {
    font-family: "Calibri Light", Calibri, sans-serif;
    font-size: 40pt;
    line-height: 1.02;
    color: #0F4C5C;
    margin: 0 0 8pt 0;
}
.cover-rule {
    width: 90pt;
    height: 4pt;
    background: #2C7A86;
    margin: 14pt 0 16pt 0;
}
.cover-sub {
    font-size: 15pt;
    color: #46666B;
    margin: 0 0 40pt 0;
}
.cover-meta {
    width: 100%;
    font-size: 9.5pt;
    border: none;
    margin-top: 20pt;
}
.cover-meta td {
    border: none;
    border-top: 0.6pt solid #D6E1E2;
    padding: 6pt 4pt 6pt 0;
}
.cover-meta td:first-child {
    width: 32%;
    color: #6B8589;
}
.cover-note {
    margin-top: 60pt;
    font-size: 8.5pt;
    color: #7A9094;
}
.toc-title {
    font-family: "Calibri Light", Calibri, sans-serif;
    font-size: 22pt;
    color: #0F4C5C;
    margin: 0 0 10pt 0;
}
"""


def construir_html(cuerpo: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Bitacora de SaludPC</title>
<style>{CSS}</style>
</head>
<body>

<div class="cover">
  <p class="cover-kicker">Salud preventiva para Windows</p>
  <p class="cover-title">Bitácora<br>SaludPC</p>
  <div class="cover-rule"></div>
  <p class="cover-sub">Historia, versiones, pruebas y próximos pasos</p>
  <table class="cover-meta">
    <tr><td>Documento</td><td>Bitácora del proyecto</td></tr>
    <tr><td>Versión</td><td>1.5</td></tr>
    <tr><td>Fecha</td><td>9 de noviembre de 2026</td></tr>
    <tr><td>Estado</td><td>0.5.3 instalada; Enterprise 1.0.3 probada y pendiente de instalar</td></tr>
    <tr><td>Ámbito</td><td>Edición para usuario final y edición empresarial</td></tr>
  </table>
  <p class="cover-note">Documento de texto · Proyecto SaludPC</p>
</div>

<p class="toc-title">Contenido</p>
<p>[[TOC]]</p>

{cuerpo}

</body>
</html>
"""


def insertar_campo(doc, rango, tipo):
    rango.Collapse(0)  # wdCollapseEnd
    doc.Fields.Add(rango, tipo)


def marcar_salto(doc, texto):
    """Marca el parrafo que contiene `texto` para que empiece en pagina nueva."""
    rango = doc.Content
    rango.Find.ClearFormatting()
    rango.Find.Text = texto
    rango.Find.Forward = True
    rango.Find.Wrap = 1
    rango.Find.MatchCase = False
    if rango.Find.Execute():
        rango.Paragraphs(1).Format.PageBreakBefore = True
        return True
    return False


def formatear_toc(doc):
    """Aplica el formato del indice. Debe llamarse despues de actualizarlo."""
    for toc in doc.TablesOfContents:
        toc.Range.Font.Name = "Calibri"
        toc.Range.Font.Size = 9
        toc.Range.ParagraphFormat.SpaceBefore = 0
        toc.Range.ParagraphFormat.SpaceAfter = 0
        toc.Range.ParagraphFormat.LineSpacingRule = 0  # sencillo


def main():
    if not ORIGEN.is_file():
        print("No se encontro BITACORA.md")
        return 1

    md = ORIGEN.read_text(encoding="utf-8")
    # Quitar el titulo y la ficha inicial: ya estan en la portada.
    md = re.sub(r"\A# Bitácora de SaludPC\s*\n+", "", md)
    md = re.sub(
        r"\*\*Última actualización:\*\*.*?\n\*\*Ámbito:\*\*.*?\n+",
        "",
        md,
        flags=re.S,
    )

    cuerpo = convertir_markdown(md)
    HTML_TMP.write_text(construir_html(cuerpo), encoding="utf-8-sig")

    pythoncom.CoInitialize()
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(str(HTML_TMP), ConfirmConversions=False, ReadOnly=False)
        doc.ActiveWindow.View.Type = 3  # wdPrintView

        # Margenes y tamano de pagina
        sec = doc.Sections(1)
        cm = 28.3464567
        sec.PageSetup.TopMargin = 2.2 * cm
        sec.PageSetup.BottomMargin = 2.1 * cm
        sec.PageSetup.LeftMargin = 2.1 * cm
        sec.PageSetup.RightMargin = 2.1 * cm
        sec.PageSetup.PaperSize = 7  # wdPaperA4
        sec.PageSetup.DifferentFirstPageHeaderFooter = True

        gris = 120 + 120 * 256 + 120 * 65536
        linea = 201 + 215 * 256 + 217 * 65536

        # Encabezado (a partir de la pagina 2)
        hdr = sec.Headers(1)
        hdr.Range.Text = "Bitácora de SaludPC  ·  9 de noviembre de 2026"
        hdr.Range.ParagraphFormat.Alignment = 2  # derecha
        hdr.Range.Font.Name = "Calibri"
        hdr.Range.Font.Size = 8
        hdr.Range.Font.Color = gris
        borde = hdr.Range.ParagraphFormat.Borders(-3)  # borde inferior
        borde.LineStyle = 1
        borde.LineWidth = 4
        borde.Color = linea

        # Pie con numeracion (a partir de la pagina 2)
        ftr = sec.Footers(1)
        ftr.Range.Text = "SaludPC  ·  Bitácora  ·  Página "
        insertar_campo(doc, ftr.Range, 33)  # PAGE
        ftr.Range.InsertAfter(" de ")
        insertar_campo(doc, ftr.Range, 26)  # NUMPAGES
        ftr.Range.ParagraphFormat.Alignment = 1  # centro
        ftr.Range.Font.Name = "Calibri"
        ftr.Range.Font.Size = 8
        ftr.Range.Font.Color = gris

        # La portada y el indice empiezan en pagina nueva; el contenido tambien.
        marcar_salto(doc, "Contenido")
        marcar_salto(doc, "1. Para qué sirve este documento")

        # Indice automatico en el lugar de [[TOC]]
        rango = doc.Content
        rango.Find.ClearFormatting()
        rango.Find.Text = "[[TOC]]"
        rango.Find.Forward = True
        rango.Find.Wrap = 1
        if rango.Find.Execute():
            rango.Text = ""
            toc = doc.TablesOfContents.Add(rango, True, 1, 2)

        doc.Repaginate()
        doc.Fields.Update()
        for toc in doc.TablesOfContents:
            toc.Update()
        doc.Repaginate()

        # Formatear despues de actualizar: Word reconstruye las entradas del
        # indice al actualizarlo y borra el formato directo anterior.
        formatear_toc(doc)
        doc.Repaginate()

        # Evitar que las tablas se partan entre paginas. La primera es la
        # ficha de la portada y la ultima es la lista de archivos, que puede
        # continuar en la pagina siguiente sin dejar una hoja casi vacia.
        total_tablas = doc.Tables.Count
        for indice, tabla in enumerate(doc.Tables, 1):
            if indice == 1:
                continue
            tabla.Rows.AllowBreakAcrossPages = False
            tabla.Rows(1).HeadingFormat = True
            if indice != total_tablas:
                tabla.Range.ParagraphFormat.KeepWithNext = True
                ultimo = tabla.Range.Paragraphs(tabla.Range.Paragraphs.Count)
                ultimo.Format.KeepWithNext = False
        doc.Repaginate()

        # Ultima actualizacion del indice para que las paginas coincidan con
        # la paginacion definitiva.
        for toc in doc.TablesOfContents:
            toc.Update()
        formatear_toc(doc)
        doc.Repaginate()

        # Propiedades del documento
        props = doc.BuiltInDocumentProperties
        try:
            props("Title").Value = "Bitácora de SaludPC"
            props("Subject").Value = "Historia, versiones y próximos pasos"
            props("Author").Value = "Proyecto SaludPC"
            props("Keywords").Value = "SaludPC; bitácora; diagnóstico preventivo"
            props("Comments").Value = "Documento generado a partir de BITACORA.md"
        except Exception:
            pass

        doc.SaveAs2(str(DESTINO), 16)  # wdFormatXMLDocument
        paginas = doc.ComputeStatistics(2)  # wdStatisticPages
        palabras = doc.ComputeStatistics(0)  # wdStatisticWords

        try:
            doc.ExportAsFixedFormat(str(PDF), 17)  # wdExportFormatPDF
        except Exception as exc:
            print(f"Aviso: no se pudo generar el PDF: {exc}")

        # Comprobar que el indice se lleno
        try:
            texto_toc = doc.TablesOfContents(1).Range.Text
            print("Indice con", len(texto_toc.splitlines()), "lineas.")
        except Exception:
            print("Aviso: no se pudo leer el indice.")

        print(f"DOCX: {DESTINO}")
        print(f"Paginas: {paginas} | Palabras: {palabras}")
        print(f"Tamano: {DESTINO.stat().st_size} bytes")
        if PDF.is_file():
            print(f"PDF: {PDF} ({PDF.stat().st_size} bytes)")

    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()
        pythoncom.CoUninitialize()

    return 0


if __name__ == "__main__":
    sys.exit(main())
