"""
Aviso visual del prefijo (Ctrl/Alt + dígitos) en AppBar o diálogo.
Buffers y debounce: `paginas.utils.paginacion`.
"""
from __future__ import annotations

from typing import Any

import flet as ft

from ui.colors import PINK_200, PINK_50, PINK_600


def crear_banner_prefijo_ctrl(*, expand: bool = False) -> tuple[ft.Container, ft.Text]:
    """Devuelve (contenedor, texto) para insertar en la barra o en un diálogo."""
    txt = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=PINK_600)
    inner = ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.DIALPAD, size=15, color=PINK_600), txt],
            spacing=4,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=PINK_50,
        padding=ft.padding.symmetric(horizontal=6, vertical=5),
        border_radius=8,
        border=ft.border.all(1.5, PINK_200),
    )
    outer = ft.Container(
        content=inner,
        alignment=ft.Alignment.CENTER,
        expand=expand,
        visible=False,
    )
    return outer, txt


def _montado(ctrl: ft.Control) -> bool:
    try:
        _ = ctrl.page
        return True
    except RuntimeError:
        return False


def sync_banner_prefijo(
    page: ft.Page,
    *,
    app: Any | None = None,
    prefix_ctrl: str = "",
    prefix_alt: str = "",
    txt: ft.Text | None = None,
    outer: ft.Container | None = None,
) -> None:
    """
    Actualiza el aviso "Alt + …" o "Ctrl + …" según los buffers.
    O bien `app` (barra principal), o bien `txt` + `outer` (diálogo).
    """
    if app is not None:
        txt = app._txt_banner_prefijo_appbar
        outer = app._outer_banner_prefijo_appbar
    elif txt is None or outer is None:
        return

    texto_alt = (prefix_alt or "").strip()
    texto_ctrl = (prefix_ctrl or "").strip()
    if texto_alt:
        digitos = texto_alt
        rotulo = "Alt"
    elif texto_ctrl:
        digitos = texto_ctrl
        rotulo = "Ctrl"
    else:
        digitos = ""
        rotulo = "Ctrl"

    visible_antes = outer.visible
    if digitos:
        txt.value = f"{rotulo} + {digitos}"
        outer.visible = True
    else:
        txt.value = ""
        outer.visible = False
    if not _montado(outer):
        return

    # Si solo cambia el texto, basta con actualizar el Text; si aparece u oculta el bloque, el contenedor.
    cambia_visibilidad = visible_antes != outer.visible
    control_a_repintar = outer if cambia_visibilidad else txt
    try:
        control_a_repintar.update()
    except Exception:
        try:
            outer.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass
