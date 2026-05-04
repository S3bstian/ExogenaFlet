"""
Tooltips centralizados: cada mensaje se resuelve con `tooltip(TooltipId.xxx, ...)`.
Los ids documentan pantalla y control; un id inválido lanza KeyError para detectarlo en desarrollo.
"""
from __future__ import annotations

from typing import Any, Callable


def _pagina_alt_digitos(**_: Any) -> str:
    return "Alt + dígitos → ir a esa página"


def _pagina_btn_anterior(**_: Any) -> str:
    return "Re Pág → página anterior"


def _pagina_btn_siguiente(**_: Any) -> str:
    return "Av Pág → página siguiente"


def _pagina_btn_solo_anterior(**_: Any) -> str:
    return "Página anterior de resultados"


def _pagina_btn_solo_siguiente(**_: Any) -> str:
    return "Página siguiente de resultados"


def _pagina_texto_resultados(**_: Any) -> str:
    return "Página dentro de los resultados (Anterior / Siguiente)"


def _hoja_concepto(**_: Any) -> str:
    return "Concepto y formato de la hoja"


def _ctrl_mas_prefijo_fila(**kw: Any) -> str:
    """Atajo Ctrl+dígitos: muestra el prefijo concreto de la fila (NIT, código cuenta, etc.)."""
    for clave in ("identidad", "codigo", "valor"):
        v = kw.get(clave)
        if v is not None and str(v).strip():
            return f"Ctrl + {str(v).strip()}"
    return "Ctrl + prefijo"


def _toma_seleccionar_todos(**_: Any) -> str:
    return "Marca o desmarca la página visible"


def _toma_acumular(**_: Any) -> str:
    return "Pasa la selección a la hoja de trabajo"


class TooltipId:
    """Identificador obligatorio al pedir un tooltip (origen = pantalla.control)."""

    PAGINA_ALT_DIGITOS = "pagina.alt_digitos"
    PAGINA_BTN_ANTERIOR = "pagina.btn_anterior"
    PAGINA_BTN_SIGUIENTE = "pagina.btn_siguiente"
    PAGINA_BTN_SOLO_ANTERIOR = "pagina.btn_solo_anterior"
    PAGINA_BTN_SOLO_SIGUIENTE = "pagina.btn_solo_siguiente"
    PAGINA_TEXTO_RESULTADOS = "pagina.texto_resultados"

    HOJA_CONCEPTO = "hoja_trabajo.concepto"
    HOJA_CTRL_IDENTIDAD = "hoja_trabajo.ctrl_identidad"

    CARTILLA_CTRL_IDENTIDAD = "cartilla_terceros.ctrl_identidad"
    CUENTAS_CTRL_CODIGO = "cuentas.ctrl_codigo"

    TOMA_SELECCIONAR_TODOS = "toma_informacion.seleccionar_todos"
    TOMA_ACUMULAR = "toma_informacion.acumular"


def _build_registry() -> dict[str, Callable[..., str]]:
    return {
        TooltipId.PAGINA_ALT_DIGITOS: _pagina_alt_digitos,
        TooltipId.PAGINA_BTN_ANTERIOR: _pagina_btn_anterior,
        TooltipId.PAGINA_BTN_SIGUIENTE: _pagina_btn_siguiente,
        TooltipId.PAGINA_BTN_SOLO_ANTERIOR: _pagina_btn_solo_anterior,
        TooltipId.PAGINA_BTN_SOLO_SIGUIENTE: _pagina_btn_solo_siguiente,
        TooltipId.PAGINA_TEXTO_RESULTADOS: _pagina_texto_resultados,
        TooltipId.HOJA_CONCEPTO: _hoja_concepto,
        TooltipId.HOJA_CTRL_IDENTIDAD: _ctrl_mas_prefijo_fila,
        TooltipId.CARTILLA_CTRL_IDENTIDAD: _ctrl_mas_prefijo_fila,
        TooltipId.CUENTAS_CTRL_CODIGO: _ctrl_mas_prefijo_fila,
        TooltipId.TOMA_SELECCIONAR_TODOS: _toma_seleccionar_todos,
        TooltipId.TOMA_ACUMULAR: _toma_acumular,
    }


_REGISTRY = _build_registry()


def tooltip(message_id: str, **kwargs: Any) -> str:
    """
    Devuelve el texto del tooltip para `message_id` (usar constantes `TooltipId.*`).
    Parámetros extra: HOJA_CTRL_IDENTIDAD / CARTILLA_CTRL_IDENTIDAD → `identidad=`;
    CUENTAS_CTRL_CODIGO → `codigo=` (o `identidad=` como alias).
    """
    try:
        fn = _REGISTRY[message_id]
    except KeyError as e:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"TooltipId desconocido: {message_id!r}. Válidos: {known}") from e
    return fn(**kwargs)
