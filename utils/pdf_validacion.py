from __future__ import annotations

from io import BytesIO
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Tuple

from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
)


# Tonos discretos para jerarquía visual (impresión y pantalla)
_COLOR_FONDO_CAB_REG = colors.HexColor("#F0F0F0")
_COLOR_BORDE_SUAVE = colors.HexColor("#CCCCCC")
_COLOR_TEXTO_ERRORES = colors.HexColor("#8B0000")
_COLOR_TEXTO_AVISOS = colors.HexColor("#8B6914")
_COLOR_ENCABEZADO_TABLA = colors.HexColor("#E8E8E8")
# Separación entre las dos columnas de identidades en el detalle
_GAP_COLUMNAS_DETALLE = 0.32 * cm


class _OutlineDocTemplate(SimpleDocTemplate):
    """Plantilla que agrega marcadores del panel lateral por cada sección."""

    def afterFlowable(self, flowable):
        # Este hook se ejecuta cada vez que se agrega un bloque al PDF.
        # Solo crea marcador cuando el bloque trae un nombre de destino.
        bookmark_name = getattr(flowable, "_bookmark_name", None)
        if not bookmark_name:
            return
        # Registra el punto exacto de salto dentro del documento.
        self.canv.bookmarkPage(bookmark_name)
        # Nivel 0 = marcador principal en el panel lateral.
        level = getattr(flowable, "_outline_level", 0)
        title = getattr(flowable, "_outline_title", bookmark_name)
        # Crea la entrada visible en el panel de marcadores del lector PDF.
        self.canv.addOutlineEntry(title, bookmark_name, level=level, closed=False)


def _registrar_fuente() -> str:
    """Registra una fuente Unicode para acentos y eñe."""
    try:
        fonts_dir = Path(reportlab_file).resolve().parent / "fonts"
        vera_path = fonts_dir / "Vera.ttf"
        pdfmetrics.registerFont(TTFont("Vera", str(vera_path)))
        return "Vera"
    except Exception:
        # Respaldo seguro: si no se encuentra la fuente, usa la base del sistema PDF.
        return "Helvetica"


def _ancho_contenido() -> float:
    """Ancho útil del cuerpo según márgenes usados en el documento."""
    return LETTER[0] - 3.6 * cm


def _texto_parrafo(s: str) -> str:
    """Escapa texto para Paragraph (evita XML roto si el mensaje trae < o &)."""
    return html_escape(str(s), quote=False)


def _ordenar_conceptos(resultado_validacion: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    # Mantiene un orden estable y deja el concepto "0" al final.
    return sorted(resultado_validacion.items(), key=lambda item: (item[0] == "0", item[0]))


def _resumen(resultado_validacion: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
    # Cuenta registros que tengan al menos un error y/o al menos un aviso.
    total_errores = 0
    total_avisos = 0
    for concepto_data in resultado_validacion.values():
        for data in concepto_data.get("registros", {}).values():
            if data.get("errores"):
                total_errores += 1
            if data.get("avisos"):
                total_avisos += 1
    return total_errores, total_avisos


def _conteo_por_concepto(concepto_data: Dict[str, Any]) -> Tuple[int, int]:
    """Cuenta registros con error y con aviso dentro de un concepto (para el índice)."""
    n_err = 0
    n_av = 0
    for data in concepto_data.get("registros", {}).values():
        if data.get("errores"):
            n_err += 1
        if data.get("avisos"):
            n_av += 1
    return n_err, n_av


def _registros_ordenados(registros: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ordena registros con incidencias: primero los que tienen error (bloqueantes),
    luego por identidad alfabética para ubicar rápido en papel o pantalla.
    """
    items: List[Tuple[int, str, Dict[str, Any]]] = []
    for _rk, data in registros.items():
        errores = data.get("errores") or []
        avisos = data.get("avisos") or []
        if not errores and not avisos:
            continue
        identidad = str(data.get("identidad", ""))
        prioridad = 0 if errores else 1
        items.append((prioridad, identidad.lower(), data))
    items.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in items]


def _flowables_leyenda_errores_avisos(styles: dict) -> List[Any]:
    """
    Texto introductorio del informe: qué implica que un registro tenga error frente a aviso.
    Debe coincidir con el criterio de validación XSD del flujo Generar XML.
    """
    titulo = Paragraph("<b>Nota</b>", styles["LeyendaTitulo"])
    p_error = Paragraph(
        "<b>Error</b>: el registro incumple una regla obligatoria del XSD que exige la DIAN "
        "(por ejemplo tipo, longitud, obligatoriedad o valor no permitido). "
        "Debe corregirse para poder informarse",
        styles["LeyendaCuerpo"],
    )
    p_aviso = Paragraph(
        "<b>Aviso</b>: situación informativa que no se puede informar a la DIAN pero el  "
        "aplicativo corrige automaticamente al generar el XML. Por ejemplo:"
        "campos de nombres y apellidos cuando el tipo de documento es 31 (NITs)",
        styles["LeyendaCuerpo"],
    )
    return [
        titulo,
        Spacer(1, 0.08 * cm),
        p_error,
        Spacer(1, 0.12 * cm),
        p_aviso,
        Spacer(1, 0.35 * cm),
    ]


def _tabla_resumen(
    total_errores: int,
    total_avisos: int,
    w: float,
    styles: dict,
) -> Table:
    """Bloque tipo ficha con totales al inicio del informe."""
    datos = [
        [
            Paragraph("<b>Registros con errores</b>", styles["MetaCustom"]),
            Paragraph(str(total_errores), styles["MetaCustom"]),
        ],
        [
            Paragraph("<b>Registros con avisos</b>", styles["MetaCustom"]),
            Paragraph(str(total_avisos), styles["MetaCustom"]),
        ],
    ]
    t = Table(datos, colWidths=[w * 0.55, w * 0.45])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _COLOR_ENCABEZADO_TABLA),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDE_SUAVE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, _COLOR_BORDE_SUAVE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _tabla_indice(
    filas: List[List[Any]],
    w: float,
    styles: dict,
) -> Table:
    """Índice con columnas: orden, código, enlace, resumen de cargas."""
    header = [
        Paragraph("<b>#</b>", styles["IndexCell"]),
        Paragraph("<b>Cód.</b>", styles["IndexCell"]),
        Paragraph("<b>Concepto</b>", styles["IndexCell"]),
        Paragraph("<b>Registros afectados</b>", styles["IndexCell"]),
    ]
    data = [header] + filas
    col_w = [0.9 * cm, 1.35 * cm, w - 0.9 * cm - 1.35 * cm - 3.2 * cm, 3.2 * cm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _COLOR_ENCABEZADO_TABLA),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDE_SUAVE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, _COLOR_BORDE_SUAVE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _bloque_registro_tabla(data: Dict[str, Any], w_cell: float, styles: dict) -> Table:
    """
    Un registro en una sola tabla vertical compacta (sirve como celda en layout de 2 columnas).
    """
    errores = data.get("errores") or []
    avisos = data.get("avisos") or []
    identidad = data.get("identidad", "Sin identidad")

    filas: List[List[Any]] = [
        [Paragraph(f"<b>Identidad</b>: {_texto_parrafo(identidad)}", styles["IdentidadCompact"])],
    ]
    if errores:
        filas.append([Paragraph("<b>Errores</b>", styles["LabelErrorCompact"])])
        for err in errores:
            filas.append([Paragraph(f"• {_texto_parrafo(err)}", styles["BodyIndentCompact"])])
    if avisos:
        filas.append([Paragraph("<b>Avisos</b>", styles["LabelAvisoCompact"])])
        for aviso in avisos:
            filas.append([Paragraph(f"• {_texto_parrafo(aviso)}", styles["BodyIndentCompact"])])

    t = Table(filas, colWidths=[w_cell])
    n = len(filas)
    estilo: List[Tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), _COLOR_FONDO_CAB_REG),
        ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDE_SUAVE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 2),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("LEFTPADDING", (0, 0), (-1, 0), 4),
        ("RIGHTPADDING", (0, 0), (-1, 0), 3),
    ]
    if n > 1:
        estilo.extend(
            [
                ("TOPPADDING", (0, 1), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 1),
                ("LEFTPADDING", (0, 1), (-1, -1), 3),
                ("RIGHTPADDING", (0, 1), (-1, -1), 2),
            ]
        )
    t.setStyle(TableStyle(estilo))
    return t


def _fila_dos_columnas(
    izq: Table,
    der: Any,
    w_mitad: float,
) -> Table:
    """Coloca dos bloques de identidad lado a lado; `der` puede ser tabla vacía si no hay pareja."""
    fila = Table([[izq, der]], colWidths=[w_mitad, w_mitad])
    fila.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("RIGHTPADDING", (0, 0), (0, 0), _GAP_COLUMNAS_DETALLE / 2),
                ("LEFTPADDING", (1, 0), (1, 0), _GAP_COLUMNAS_DETALLE / 2),
            ]
        )
    )
    return fila


def construir_pdf_validacion(resultado_validacion: Dict[str, Dict[str, Any]], titulo_formato: str) -> bytes:
    """
    Construye un PDF de validación con resumen, índice tabular y marcadores por concepto.
    """
    font_name = _registrar_fuente()
    w = _ancho_contenido()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCustom", parent=styles["Title"], fontName=font_name, fontSize=18, leading=22))
    styles.add(
        ParagraphStyle(
            name="H2Custom",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#8B1538"),
            spaceAfter=6,
        )
    )
    styles.add(ParagraphStyle(name="BodyCustom", parent=styles["BodyText"], fontName=font_name, fontSize=9.5, leading=12))
    styles.add(ParagraphStyle(name="MetaCustom", parent=styles["BodyText"], fontName=font_name, fontSize=10, leading=13, textColor=colors.HexColor("#4A4A4A")))
    styles.add(
        ParagraphStyle(
            name="LeyendaTitulo",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#333333"),
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LeyendaCuerpo",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#444444"),
            leftIndent=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="IndexCell",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11,
        )
    )
    # Estilos compactos para el detalle por identidad (dos columnas)
    styles.add(
        ParagraphStyle(
            name="IdentidadCompact",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=10.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyIndentCompact",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=10,
            leftIndent=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LabelErrorCompact",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=10,
            textColor=_COLOR_TEXTO_ERRORES,
            spaceBefore=0,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LabelAvisoCompact",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=10,
            textColor=_COLOR_TEXTO_AVISOS,
            spaceBefore=0,
            spaceAfter=1,
        )
    )

    buffer = BytesIO()
    doc = _OutlineDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Informe de validacion XSD",
    )

    # "story" es la secuencia ordenada de bloques (título, textos, saltos de página, etc).
    story: List[Any] = []
    total_errores, total_avisos = _resumen(resultado_validacion)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conceptos = _ordenar_conceptos(resultado_validacion)

    story.append(Paragraph("Informe de validacion XSD", styles["TitleCustom"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"<b>Formato:</b> {_texto_parrafo(titulo_formato)}", styles["MetaCustom"]))
    story.append(Paragraph(f"<b>Generado:</b> {_texto_parrafo(fecha)}", styles["MetaCustom"]))
    story.append(Spacer(1, 0.3 * cm))
    story.extend(_flowables_leyenda_errores_avisos(styles))
    story.append(_tabla_resumen(total_errores, total_avisos, w, styles))
    story.append(Spacer(1, 0.45 * cm))

    if total_errores == 0 and total_avisos == 0:
        story.append(Paragraph("No se encontraron incidencias en la validacion.", styles["BodyCustom"]))
        doc.build(story)
        return buffer.getvalue()

    story.append(Paragraph("Indice de conceptos", styles["H2Custom"]))
    story.append(Spacer(1, 0.15 * cm))

    conceptos_con_incidencias: List[Tuple[str, str, str, str, Dict[str, Any]]] = []
    filas_indice: List[List[Any]] = []

    for concepto_codigo, concepto_data in conceptos:
        registros = concepto_data.get("registros", {})
        tiene_incidencias = any(data.get("errores") or data.get("avisos") for data in registros.values())
        if not tiene_incidencias:
            continue
        descripcion = concepto_data.get("descripcion") or "Sin descripcion"
        nombre = "Sin concepto" if concepto_codigo == "0" else f"Concepto {concepto_codigo}"
        destino = f"concepto_{concepto_codigo}"
        n_err, n_av = _conteo_por_concepto(concepto_data)
        resumen_celda = f"{n_err} err. / {n_av} av."
        conceptos_con_incidencias.append((concepto_codigo, descripcion, nombre, destino, concepto_data))

        idx = len(filas_indice) + 1
        filas_indice.append(
            [
                Paragraph(str(idx), styles["IndexCell"]),
                Paragraph(_texto_parrafo(concepto_codigo), styles["IndexCell"]),
                Paragraph(f'<link href="#{destino}">{_texto_parrafo(nombre)}: {_texto_parrafo(descripcion)}</link>', styles["IndexCell"]),
                Paragraph(resumen_celda, styles["IndexCell"]),
            ]
        )

    story.append(_tabla_indice(filas_indice, w, styles))
    story.append(PageBreak())

    for concepto_codigo, descripcion, nombre, destino, concepto_data in conceptos_con_incidencias:
        heading = Paragraph(f"{nombre} — {_texto_parrafo(descripcion)}", styles["H2Custom"])
        heading._bookmark_name = destino
        heading._outline_level = 0
        heading._outline_title = f"{nombre}: {descripcion}"
        story.append(heading)

        n_err, n_av = _conteo_por_concepto(concepto_data)
        story.append(Spacer(1, 0.12 * cm))

        registros = concepto_data.get("registros", {})
        lista_reg = _registros_ordenados(registros)
        w_mitad = (w - _GAP_COLUMNAS_DETALLE) / 2
        tabla_vacia = None
        for i in range(0, len(lista_reg), 2):
            izq = _bloque_registro_tabla(lista_reg[i], w_mitad, styles)
            if i + 1 < len(lista_reg):
                der = _bloque_registro_tabla(lista_reg[i + 1], w_mitad, styles)
            else:
                if tabla_vacia is None:
                    tabla_vacia = Table([[Paragraph("", styles["BodyCustom"])]], colWidths=[w_mitad])
                der = tabla_vacia
            story.append(KeepTogether(_fila_dos_columnas(izq, der, w_mitad)))
            story.append(Spacer(1, 0.12 * cm))

        story.append(Spacer(1, 0.2 * cm))

    doc.build(story)
    return buffer.getvalue()
