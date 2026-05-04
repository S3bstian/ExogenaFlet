"""
Creador de campos de texto y kwargs base.
"""
import flet as ft
from ui.colors import PINK_200, GREY_700


def creador_campo_texto(label: str, especificaciones: list) -> ft.TextField:
    """Construye TextField con estilo base. Especificaciones: ['contraseña'], ['focus']."""
    campo_kwargs = {
        "label": label,
        "border_color": PINK_200,
        "label_style": ft.TextStyle(color=GREY_700),
    }
    if especificaciones:
        if "contraseña" in especificaciones:
            campo_kwargs["password"] = True
            campo_kwargs["can_reveal_password"] = True
        if "focus" in especificaciones:
            campo_kwargs["autofocus"] = True
    return ft.TextField(**campo_kwargs)


def textfield_base_kwargs() -> dict:
    """Kwargs base para TextField (border_color, label_style)."""
    return {"border_color": PINK_200, "label_style": ft.TextStyle(color=GREY_700)}
