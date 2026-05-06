"""UI de grilla y esquema de hoja de trabajo. Las funciones que consultan atributos reciben el UC desde `HojaTrabajoPage`."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
import flet as ft
from core.catalogues import obtener_nombre_tipodoc

from ui.colors import PINK_50, PINK_200, PINK_600, PINK_800, GREY_700

from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo

if TYPE_CHECKING:
    from application.use_cases.formatos_conceptos.gestion_formatos_ui import (
        GestionFormatosUIUseCase,
    )
    from domain.entities.concepto_detalle_hoja_trabajo import ConceptoDetalleHojaTrabajo

_PALABRAS_COLUMNA_NUMERICA = ("código", "codigo", "dígito", "digito", "país", "pais")
_NO_VISIBLES_ESQUEMA = {
    "formato",
    "concepto",
    "identidad",
    "identidadtercero",
    "id_concepto",
    "número de identificación",
    "número de identificación del beneficiario",
    "número de identificación del tercero",
    "número de documento de identificación",
}
_OCULTAR_SUBSTRINGS_ESQUEMA = (
    "PRIMER APELLIDO",
    "SEGUNDO APELLIDO",
    "PRIMER NOMBRE",
    "SEGUNDO NOMBRE",
    "OTROS NOMBRES",
)


def _concepto_a_dict(concepto: Any) -> dict | None:
    """Unifica dict legacy `{codigo, formato}` y entidad `ConceptoHojaTrabajo` para consultas de atributos."""
    if not concepto:
        return None
    if isinstance(concepto, dict) and "codigo" in concepto and "formato" in concepto:
        return concepto
    if isinstance(concepto, ConceptoHojaTrabajo):
        return concepto.as_dict()
    return None


# ==================== Formato y esquema ====================

def formatear_pesos(valor) -> str:
    """Formatea un valor como pesos colombianos (miles con punto, decimales con coma)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "" if valor is None else str(valor)  # Mantener vacío / string original sin tocar
    s = str(valor).strip()
    try:
        n = float(s)
    except ValueError:
        # Manejar formato tipo "1.234.567,89" (puntos miles, coma decimal)
        s = s.replace(".", "").replace(",", ".")
        try:
            n = float(s)
        except ValueError:
            return str(valor)  # Si tampoco se puede, devolver tal cual
    neg = n < 0
    n = abs(n)
    if n == int(n):
        out = f"{int(n):,}".replace(",", ".")  # Solo miles
    else:
        # Formato colombiano: 1.234.567,89 (puntos miles, coma decimal)
        out = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" + out) if neg else out


def es_columna_numerica(nombre: str) -> bool:
    """
    Indica si una columna es "numérica" por convención del nombre
    (códigos, dígitos de verificación, país, etc.) y por tanto debe alinearse a la derecha.
    """
    if not nombre:
        return False
    n = nombre.strip().lower()
    return any(k in n for k in _PALABRAS_COLUMNA_NUMERICA)


def es_columna_correo_o_email(nombre: str) -> bool:
    """
    True si el título de columna sugiere correo electrónico.
    Usado para no forzar alineación numérica a la derecha en columnas CLASE=3 de valor.
    """
    if not nombre:
        return False
    x = nombre.strip().lower()
    return "correo" in x or "email" in x


def columnas_valor_concepto(
    formatos_uc: GestionFormatosUIUseCase,
    concepto: Any,
    clases: tuple[int, ...] = (1,),
) -> set:
    """
    Nombres de columna (descripción visible) para las clases indicadas.
    Por defecto incluye solo CLASE=1 (valor/monto).
    """
    c = _concepto_a_dict(concepto)
    if not c:
        return set()
    out = set()
    for a in formatos_uc.obtener_atributos_por_concepto(
        {"codigo": str(c["codigo"]), "formato": str(c["formato"])}
    ):
        if len(a) < 4:
            continue
        try:
            clase = int(a[3]) if a[3] is not None and str(a[3]).strip() != "" else None
        except (TypeError, ValueError):
            clase = None
        if clase not in clases:
            continue
        d = (a[2] or "").strip()
        if d:
            out.add(d)
    return out


def _titulo_normalizado(titulo: str) -> str:
    return (titulo or "").strip().lower()


def _titulo_en_columnas_valor(titulo: str, columnas_valor: set) -> bool:
    t = _titulo_normalizado(titulo)
    return bool(t and any(_titulo_normalizado(c) == t for c in columnas_valor))


def indices_columnas_numericas(encabezados: list, columnas_valor: set) -> set:
    """
    Devuelve índices de columnas que se alinean a la derecha en la tabla:
    - Por nombre "numérico" (código, país...).
    - O porque pertenecen al set de columnas CLASE=1 (`columnas_valor_concepto`),
      salvo títulos de correo/email (texto, no alineación tipo monto).
    """
    indices = set()
    for i, h in enumerate(encabezados):
        # Columnas 0 y 1 no son numéricas (Acciones, Identidad)
        if i <= 1:
            continue
        n = (h or "").strip()
        if es_columna_correo_o_email(n):
            continue
        # Combinamos heurística por nombre + pertenencia explícita al set de columnas de valor
        if es_columna_numerica(n) or _titulo_en_columnas_valor(n, columnas_valor):
            indices.add(i)
    return indices


def calcular_anchos_columnas(
    formatos_uc: GestionFormatosUIUseCase,
    encabezados: list,
    columnas_valor: set,
    concepto_actual: Any = None,
) -> list[float]:
    """
    Calcula anchos fijos de columnas según semántica:
    - Identidad / códigos cortos.
    - Textos largos (razón social, dirección, nombres).
    - Columnas de valor.
    """
    if not encabezados:
        return []
    columnas_clase2 = columnas_valor_concepto(formatos_uc, concepto_actual, (2,))
    anchos = []
    for idx, titulo in enumerate(encabezados):
        # Columnas 0=Acciones, 1=Identidad; resto por semántica
        if idx == 0:
            anchos.append(65)
        elif idx == 1:
            anchos.append(82)
        else:
            n = (titulo or "").strip().upper()
            # Atributos CLASE=2 tienen prioridad para evitar choques con reglas genéricas (ej. "TIPO").
            if _titulo_en_columnas_valor(titulo, columnas_clase2):
                anchos.append(55)
            elif "IDENTIFICACIÓN" in n or "IDENTIFICACION" in n:
                anchos.append(82)
            elif "RAZÓN SOCIAL" in n or "RAZON SOCIAL" in n:
                anchos.append(282)
            elif "DIRECCIÓN" in n or "DIRECCION" in n:
                anchos.append(155)
            elif "APELLIDO" in n or "NOMBRE" in n or "OTROS NOMBRES" in n:
                anchos.append(111)
            elif "TIPO" in n:
                anchos.append(151)
            elif "CÓDIGO" in n or "CODIGO" in n:
                anchos.append(55)
            # Si el encabezado coincide con alguna columna de valor, usamos ancho "de montos".
            elif _titulo_en_columnas_valor(titulo, columnas_valor):
                anchos.append(111)
            else:
                anchos.append(66)
    return anchos


def construir_esquema(
    formatos_uc: GestionFormatosUIUseCase,
    concepto_actual,
    datos: dict,
) -> tuple[list, list, set]:
    """
    Crea el esquema de la tabla a partir del concepto y los datos actuales.

    Retorna:
    - lista de atributos visibles (en orden),
    - encabezado completo (Acciones, Identidad, ...),
    - set de columnas CLASE=1 (alineación y formato monetario de celda).
    """
    presentes = set()
    for r in datos.values():
        presentes.update(
            k
            for k in r.keys()
            if k.lower() not in _NO_VISIBLES_ESQUEMA
            and not any(s in str(k or "").upper() for s in _OCULTAR_SUBSTRINGS_ESQUEMA)
        )

    ordenadas = []
    attrs = []
    c_payload = _concepto_a_dict(concepto_actual)
    if c_payload:
        c = {"codigo": str(c_payload["codigo"]), "formato": str(c_payload["formato"])}
        # Ordenamos atributos por ID (a[0]) para respetar el orden definido en la matriz del concepto
        attrs = sorted(
            formatos_uc.obtener_atributos_por_concepto(c),
            key=lambda a: int(a[0]) if isinstance(a[0], (int, float)) or str(a[0]).isdigit() else 0,
        )
        for a in attrs:
            d = (a[2] or "").strip()  # DESCRIPCION visible de la columna en hoja de trabajo
            if d and d in presentes:  # Solo incluimos columnas que realmente existen en los datos cargados
                ordenadas.append(d)

    if not ordenadas:
        ordenadas = sorted(presentes)  # Fallback: si no hay definición de concepto, usar orden alfabético
    encabezado = ["Acciones", "Identidad"] + ordenadas  # Cabecera completa que consumirá la DataTable2
    col_valor = columnas_valor_concepto(formatos_uc, concepto_actual)
    return ordenadas, encabezado, col_valor


def construir_matriz_filas(datos: dict, encabezado: list, atributos: list) -> list:
    """
    Construye matriz [encabezado] + filas a partir de datos y esquema.
    Retorna lista de listas para la tabla.
    """
    if not datos:
        return [["Vacío"]]
    filas = [encabezado]
    # clave = id_concepto|identidad; atributos en orden del esquema
    for clave in sorted(datos.keys()):
        registro = datos[clave]
        fila = ["ACCIONES", clave] + [registro.get(campo, "") for campo in atributos]
        filas.append(fila)
    return filas


def identidad_desde_clave(clave: str, rows_bd: dict, clave_a_identidad: dict | None = None) -> str | None:
    """
    Obtiene la identidad (Número de Identificación) para una clave de fila.
    Usa clave_a_identidad si está disponible, sino extrae de rows_bd.
    """
    cache = clave_a_identidad or {}
    identidad = cache.get(clave)
    if not identidad and clave in rows_bd:
        identidad = rows_bd[clave].get(
            "Número de Identificación",
            clave.split("|", 1)[-1] if "|" in clave else clave,
        )
    return str(identidad).strip() if identidad else None


def concepto_tiene_cc_mm(concepto: Any) -> bool:
    """True si el concepto tiene configurado agrupar cuantías menores."""
    if not concepto:
        return False
    if hasattr(concepto, "tiene_cc_mm"):
        return bool(getattr(concepto, "tiene_cc_mm"))
    if isinstance(concepto, dict):
        return bool(
            concepto.get("cc_mm_identidad")
            and concepto.get("cc_mm_nombre")
            and concepto.get("cc_mm_valor")
        )
    return False


def concepto_tiene_exterior(concepto: Any) -> bool:
    """True si el concepto tiene configurado numerar NITs extranjeros."""
    if not concepto:
        return False
    if hasattr(concepto, "tiene_exterior"):
        return bool(getattr(concepto, "tiene_exterior"))
    if isinstance(concepto, dict):
        return bool(concepto.get("exterior_identidad") and concepto.get("exterior_nombre"))
    return False


def _codigo_formato(concepto: Any) -> tuple[str, str]:
    """Normaliza un concepto (entidad o dict) a `(codigo, formato)`."""
    if isinstance(concepto, dict):
        return str(concepto.get("codigo") or "").strip(), str(concepto.get("formato") or "").strip()
    codigo = str(getattr(concepto, "codigo", "") or "").strip()
    formato = str(getattr(concepto, "formato", "") or "").strip()
    return codigo, formato


def concepto_tiene_tipo_fideicomiso(formatos_uc: GestionFormatosUIUseCase, concepto: Any) -> bool:
    """
    True si el concepto contiene el atributo con descripción 'TIPO DE FIDEICOMISO'.
    Reusa la misma fuente de atributos que usa la hoja de trabajo.
    """
    if not concepto:
        return False
    codigo, formato = _codigo_formato(concepto)
    if not codigo or not formato:
        return False
    c = {"codigo": codigo, "formato": formato}
    for a in formatos_uc.obtener_atributos_por_concepto(c):
        if len(a) < 3:
            continue
        desc = str(a[2] or "").strip().upper()
        if desc == "TIPO DE FIDEICOMISO":
            return True
    return False


# ==================== UI: columnas, filas, snackbars ====================

def texto_celda_dato(
    valor, nombre_col: str, col_idx: int, indices_valor: set, columnas_valor: set
) -> tuple[str, ft.TextAlign]:
    """
    Devuelve texto formateado y alineación para una celda de datos (columna >= 2).
    - Mapea tipo de documento a su descripción.
    - Formatea montos con `formatear_pesos` solo para columnas CLASE=1.
    - Decide alineación izquierda/derecha combinando índice + heurística de nombre.
    """
    n = nombre_col or ""
    es_columna_valor = _titulo_en_columnas_valor(n, columnas_valor)
    if "tipo" in n.lower() and "documento" in n.lower():
        texto = obtener_nombre_tipodoc(valor) or (str(valor) if valor else "")
    elif es_columna_valor:
        texto = formatear_pesos(valor) if valor else ""
    else:
        texto = str(valor) if valor else ""
    # Consideramos "numérico" tanto por índice de columna de valor como por nombre de la columna
    derecha = col_idx in indices_valor or es_columna_numerica(n)
    return texto, ft.TextAlign.END if derecha else ft.TextAlign.START


def label_columna(idx: int, titulo: str) -> ft.Container:
    """
    Construye la cabecera visual de una columna:
    - Texto centrado, con wrap controlado.
    - Borde superior/inferior y borde derecho para columna Identidad.
    """
    contenido = ft.Text(
        titulo or "",
        text_align=ft.TextAlign.CENTER,
        max_lines=2,
        no_wrap=False,
        overflow=ft.TextOverflow.CLIP,
    )
    borde = ft.border.only(top=ft.border.BorderSide(1.5, PINK_200), bottom=ft.border.BorderSide(0.9, PINK_200))
    if idx == 1:
        borde = ft.border.only(top=ft.border.BorderSide(1.5, PINK_200), right=ft.border.BorderSide(0.65, GREY_700), bottom=ft.border.BorderSide(0.9, PINK_200))
    return ft.Container(content=contenido, bgcolor=PINK_50, border=borde, alignment=ft.Alignment(0, 0), tooltip=titulo or "")


def fila_identidades(
    identidades: list[str],
    verbo: str,
    prefijo: str,
    page: ft.Page,
    on_copy: Callable[[], None],
    copy_on_click: bool = False,
) -> ft.Row | None:
    """
    Fila del snackbar de herramientas:
    - Muestra "Ver N identidad(es) a <verbo>" subrayado.
    - Si `copy_on_click` es True, copia todas las identidades al portapapeles.
    - Si es False, muestra un tooltip con cuadrícula de identidades.
    """
    ids = [str(i).strip() for i in identidades if str(i).strip()]  # Limpiar vacíos / espacios
    if not ids:
        return None
    n = len(ids)
    texto = f"Ver {n} identidad(es) a {verbo}"
    estilo = ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE, decoration_color=PINK_600)

    if copy_on_click:
        async def _tap(_e):
            await page.clipboard.set("\n".join(ids))  # Copiar una por línea
            on_copy()  # Permite mostrar mensaje o side-effect desde HojaTrabajoPage
        control = ft.GestureDetector(
            content=ft.Text(texto, color=PINK_800, size=11, weight=ft.FontWeight.BOLD, style=estilo),
            on_tap=_tap,
        )
    else:
        # Tooltip: cuadrícula de identidades (máx max_rows filas x n_cols columnas)
        max_rows, col_w = 10, 18
        n_cols = max(1, (n + max_rows - 1) // max_rows)
        to_show = ids[: max_rows * n_cols]
        grid = [to_show[i:i + n_cols] for i in range(0, len(to_show), n_cols)]
        msg = f"{prefijo} ({n}):\n" + "\n".join("  ".join(c.ljust(col_w) for c in row) for row in grid)
        if n - len(to_show) > 0:
            msg += f"\n... y {n - len(to_show)} más"
        control = ft.Text(
            texto,
            color=PINK_800,
            size=13,
            weight=ft.FontWeight.BOLD,
            tooltip=ft.Tooltip(message=msg, prefer_below=False),
            style=estilo,
        )

    return ft.Row(controls=[ft.Text("• ", color=PINK_800, size=13), control], spacing=0)


def cabecera_snackbar_herramienta(icono, texto: ft.Control, botones: list) -> ft.Row:
    """
    Cabecera genérica para snackbars de herramientas:
    - Icono a la izquierda.
    - Contenido flexible en el centro.
    - Grupo de botones a la derecha (Cancelar / Aceptar).
    """
    return ft.Row(
        controls=[ft.Icon(icono, color=PINK_600, size=20), ft.Container(texto, expand=True), ft.Row(controls=botones, spacing=8)],
        spacing=10,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )


# ==================== Estado del panel de herramientas ====================

def estado_panel_herramientas(abierto: bool) -> dict:
    """
    Retorna width, opacity, visible, icon, text y tooltip según si el panel está abierto o cerrado.
    visible=False cuando cerrado evita que los botones reciban foco con Tab.
    """
    if abierto:
        return {
            "width": 300,
            "opacity": 1,
            "visible": True,
            "icon": ft.Icons.KEYBOARD_DOUBLE_ARROW_RIGHT,
            "text": "Cerrar",
            "tooltip": "Cerrar herramientas",
        }
    return {
        "width": 0,
        "opacity": 0,
        "visible": False,
        "icon": ft.Icons.KEYBOARD_DOUBLE_ARROW_LEFT_SHARP,
        "text": "Herramientas",
        "tooltip": "Desplegar herramientas",
    }


def remover_snackbar_overlay(page: ft.Page, snackbar) -> None:
    """
    Quita un snackbar del overlay y dispara un snackbar "invisible"
    para que Flet procese correctamente el cierre en la UI.
    """
    if snackbar is not None:
        snackbar.open = False
        if snackbar in page.overlay:
            page.overlay.remove(snackbar)
    from ui.snackbars import snackbar_invisible_para_cerrar
    snackbar_invisible_para_cerrar(page)
