"""
Factores de ProgressRing para carga visual.
Unifica creación de loaders indeterminados y determinados.
"""
import flet as ft
from ui.colors import PINK_200

SIZE_SMALL = 12
SIZE_MEDIUM = 20
SIZE_LARGE = 77


def crear_ring(indeterminado=True, size=None, color=PINK_200) -> ft.ProgressRing:
    """
    Crea un ProgressRing reutilizable.
    indeterminado: sin valor (gira continuamente). False = determinate (value=0.01 visible).
    size: 16, 20, 77 o None (tamaño por defecto).
    """
    kwargs = {"color": color}
    if size:
        kwargs["width"] = size
        kwargs["height"] = size
    if not indeterminado:
        kwargs["value"] = 0.01
    return ft.ProgressRing(**kwargs)


def crear_loader_row(mensaje: str, size=None, determinada=False, color=PINK_200) -> ft.Row:
    """
    Row con ProgressRing + Text para diálogos y loaders inline.
    size: SIZE_SMALL, SIZE_MEDIUM, SIZE_LARGE o None.
    """
    ring = crear_ring(indeterminado=not determinada, size=size, color=color)
    return ft.Row(
        [ring, ft.Text(mensaje)],
        alignment=ft.MainAxisAlignment.CENTER,
    )

