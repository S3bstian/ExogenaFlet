"""
Utilidades reutilizables para mostrar texto de paginación (Página X de Y)
arriba y abajo a la derecha, con mínimo espacio.
"""
import flet as ft
from ui.colors import GREY_700

from paginas.utils.tooltips import TooltipId, tooltip


def pagination_text_value(
    pagina_actual: int,
    total_paginas: int = 1,
    total_registros: int | None = None,
) -> str:
    """
    Devuelve el texto de paginación como string: 'Página X de Y'.
    Solo muestra página actual y total de páginas; total_registros no se muestra.
    """
    p = max(1, int(pagina_actual))
    t = max(1, int(total_paginas))
    return f"Página {p} de {t}"


def build_pagination_label(
    pagina_actual: int,
    total_paginas: int = 1,
    total_registros: int | None = None,
    *,
    tooltip_alt_pagina: str | None = None,
) -> ft.Text:
    """
    Construye el texto de paginación a partir de `pagination_text_value`.
    Si `tooltip_alt_pagina` es None, usa el mensaje estándar de Alt+dígitos
    (pasar cadena vacía para no mostrar tooltip).
    """
    msg = tooltip(TooltipId.PAGINA_ALT_DIGITOS) if tooltip_alt_pagina is None else tooltip_alt_pagina
    return ft.Text(
        pagination_text_value(pagina_actual, total_paginas, total_registros),
        size=12,
        color=GREY_700,
        text_align=ft.TextAlign.RIGHT,
        tooltip=msg if msg else None,
    )


# Valores típicos de `KeyboardEvent.key` para Re Pág / Av Pág (según plataforma).
_KEYS_RE_PAG = frozenset(
    ("Page Up", "PageUp", "Prior", "Numpad Page Up", "Numpad PageUp", "Page_Up")
)
_KEYS_AV_PAG = frozenset(
    ("Page Down", "PageDown", "Next", "Numpad Page Down", "Numpad PageDown", "Page_Down")
)


def tecla_es_repag(key: str | None) -> bool:
    """Re Pág (Page Up): en listas paginadas equivale a página anterior."""
    if not key:
        return False
    return str(key).strip() in _KEYS_RE_PAG


def tecla_es_avpag(key: str | None) -> bool:
    """Av Pág (Page Down): en listas paginadas equivale a página siguiente."""
    if not key:
        return False
    return str(key).strip() in _KEYS_AV_PAG

DEBOUNCE_PREFIJOS_SEC = 0.8


def tecla_es_solo_modificador(key: str | None) -> bool:
    """True si la tecla es solo Ctrl/Alt/Shift/Meta (no debe vaciar buffers de prefijo)."""
    if not key:
        return False
    k = str(key).lower().strip()
    nombres = (
        "ctrl",
        "control",
        "control left",
        "control right",
        "alt",
        "alt left",
        "alt right",
        "altgraph",
        "shift",
        "shift left",
        "shift right",
        "meta",
        "meta left",
        "meta right",
        "os",
        "super",
        "context menu",
        "menu",
    )
    if k in nombres:
        return True
    if k.startswith("control ") or k.startswith("alt ") or k.startswith("shift "):
        return True
    return False


def normalize_digit_key(key: str | None) -> str | None:
    """
    Normaliza una tecla a un dígito ('0'..'9'), soportando
    tanto la fila superior como el teclado numérico derecho.
    """
    if key in "0123456789":
        return key
    if not key:
        return None
    k = str(key).lower().strip()
    # Variantes típicas: 'numpad 1', 'numpad1', 'num 1'
    if k.startswith("numpad") or k.startswith("num "):
        last_char = k[-1]
        if last_char in "0123456789":
            return last_char
    return None


def reset_prefix_buffer(owner, buffer_attr: str = "_prefix_buffer", timer_attr: str = "_prefix_buffer_timer") -> None:
    """
    Limpia un buffer de prefijo y cancela su temporizador asociado.
    `owner` es el objeto que contiene ambos atributos.
    """
    try:
        setattr(owner, buffer_attr, "")
        timer = getattr(owner, timer_attr, None)
        if timer:
            try:
                timer.cancel()
            except Exception:
                pass
        setattr(owner, timer_attr, None)
    except Exception:
        # Si por cualquier motivo no existen los atributos, se ignora el error.
        pass


def reset_page_prefix_buffer(owner) -> None:
    """Limpia buffer Alt+dígitos (salto a página) y su temporizador."""
    reset_prefix_buffer(owner, buffer_attr="_page_prefix_buffer", timer_attr="_page_prefix_timer")
