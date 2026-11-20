# -*- coding: utf-8 -*-
"""Genera MANUAL_DE_USO_SaludPC.docx y su PDF a partir de MANUAL_DE_USO.md."""

import re
import sys
from pathlib import Path

import pythoncom
import win32com.client as win32

from generar_word import (
    CSS,
    convertir_markdown,
    formatear_toc,
    insertar_campo,
    marcar_salto,
)

BASE = Path(r"C:\Users\INFO\Desktop\pipia")
ORIGEN = BASE / "MANUAL_DE_USO.md"
DESTINO = BASE / "MANUAL_DE_USO_SaludPC.docx"
PDF = BASE / "MANUAL_DE_USO_SaludPC.pdf"
HTML_TMP = BASE / "_manual_word.html"


def construir_html(cuerpo: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Manual de uso de SaludPC</title>
<style>{CSS}</style>
</head>
<body>

<div class="cover">
  <p class="cover-kicker">Diagnóstico preventivo para Windows</p>
  <p class="cover-title">Manual<br>de uso</p>
  <div class="cover-rule"></div>
  <p class="cover-sub">Instalación, operación, búsqueda, informes y solución de problemas</p>
  <table class="cover-meta">
    <tr><td>Documento</td><td>Manual de uso</td></tr>
    <tr><td>Versión</td><td>1.0</td></tr>
    <tr><td>Fecha</td><td>9 de noviembre de 2026</td></tr>
    <tr><td>Estado</td><td>Local 0.5.3 · Servidor 1.0.3 · Cliente 1.0.2</td></tr>
    <tr><td>Ámbito</td><td>Usuario final y personal de TI</td></tr>
  </table>
  <p class="cover-note">Documento de texto · Proyecto SaludPC</p>
</div>

<p class="toc-title">Contenido</p>
<p>[[TOC]]</p>

{cuerpo}

</body>
</html>
"""


def main():
    if not ORIGEN.is_file():
        print("No se encontro MANUAL_DE_USO.md")
        return 1

    md = ORIGEN.read_text(encoding="utf-8")
    md = re.sub(r"\A# Manual de uso de SaludPC\s*\n+", "", md)
    md = re.sub(
        r"\*\*Versión del manual:\*\*.*?\n"
        r"\*\*Última actualización:\*\*.*?\n"
        r"\*\*Ámbito:\*\*.*?\n+",
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

        hdr = sec.Headers(1)
        hdr.Range.Text = "Manual de uso de SaludPC  ·  9 de noviembre de 2026"
        hdr.Range.ParagraphFormat.Alignment = 2
        hdr.Range.Font.Name = "Calibri"
        hdr.Range.Font.Size = 8
        hdr.Range.Font.Color = gris
        borde = hdr.Range.ParagraphFormat.Borders(-3)
        borde.LineStyle = 1
        borde.LineWidth = 4
        borde.Color = linea

        ftr = sec.Footers(1)
        ftr.Range.Text = "SaludPC  ·  Manual de uso  ·  Página "
        insertar_campo(doc, ftr.Range, 33)
        ftr.Range.InsertAfter(" de ")
        insertar_campo(doc, ftr.Range, 26)
        ftr.Range.ParagraphFormat.Alignment = 1
        ftr.Range.Font.Name = "Calibri"
        ftr.Range.Font.Size = 8
        ftr.Range.Font.Color = gris

        marcar_salto(doc, "Contenido")
        marcar_salto(doc, "1. Qué es SaludPC")

        rango = doc.Content
        rango.Find.ClearFormatting()
        rango.Find.Text = "[[TOC]]"
        rango.Find.Forward = True
        rango.Find.Wrap = 1
        if rango.Find.Execute():
            rango.Text = ""
            doc.TablesOfContents.Add(rango, True, 1, 2)

        doc.Repaginate()
        doc.Fields.Update()
        for toc in doc.TablesOfContents:
            toc.Update()
        doc.Repaginate()

        formatear_toc(doc)
        doc.Repaginate()

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

        for toc in doc.TablesOfContents:
            toc.Update()
        formatear_toc(doc)
        doc.Repaginate()

        props = doc.BuiltInDocumentProperties
        try:
            props("Title").Value = "Manual de uso de SaludPC"
            props("Subject").Value = "Instalación, operación, búsqueda e informes"
            props("Author").Value = "Proyecto SaludPC"
            props("Keywords").Value = "SaludPC; manual; servidor; cliente; informes"
            props("Comments").Value = "Documento generado a partir de MANUAL_DE_USO.md"
        except Exception:
            pass

        doc.SaveAs2(str(DESTINO), 16)  # wdFormatXMLDocument
        paginas = doc.ComputeStatistics(2)
        palabras = doc.ComputeStatistics(0)

        try:
            doc.ExportAsFixedFormat(str(PDF), 17)  # wdExportFormatPDF
        except Exception as exc:
            print(f"Aviso: no se pudo generar el PDF: {exc}")

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
