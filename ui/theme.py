"""
Tema global Material de la aplicación (`page.theme`).

Un solo lugar para menús desplegables, diálogos modales y snackbars por defecto.
Los controles que fijen `bgcolor`, `style`, etc. explícitamente siguen ganando al tema.
"""
import flet as ft

from ui.colors import FONDO_PAGINA, GREY_700, PINK_100, PINK_50, PINK_200, PINK_400, PINK_600, PINK_800, WHITE, BLACK

# Fuente base de la app (coincide con lo que antes estaba en main).
_FONT_FAMILY = "Hind"


def _superficie_menu():
    """Forma, sombra y relleno compartidos entre PopupMenuTheme y Dropdown.menu_style."""
    shape = ft.RoundedRectangleBorder(radius=8, side=ft.BorderSide(1, PINK_200))
    shadow = ft.Colors.with_opacity(0.22, PINK_600)
    pad = ft.padding.all(4)
    return shape, shadow, pad


def _superficie_snackbar():
    """SnackBar: más contraste que el fondo de página (PINK_50 ~ FONDO_PAGINA) y que menús ligeros."""
    shape = ft.RoundedRectangleBorder(radius=10, side=ft.BorderSide(1.5, PINK_400))
    return shape


# Elevación unificada con `ui/snackbars.py` cuando el control fija `elevation`.
SNACKBAR_ELEVATION = 6


def tema_aplicacion() -> ft.Theme:
    """
    Construye el `ft.Theme` asignado a `page.theme` al iniciar la app.

    Incluye:
    - Menús popup / contextuales (`popup_menu_theme`)
    - Paneles de `ft.Dropdown` (`dropdown_theme.menu_style`)
    - `AlertDialog` por defecto (`dialog_theme`)
    - `SnackBar` por defecto (`snackbar_theme`)
    """
    m_shape, m_shadow, m_pad = _superficie_menu()

    return ft.Theme(
        font_family=_FONT_FAMILY,
        popup_menu_theme=ft.PopupMenuTheme(
            color=PINK_50,
            shadow_color=m_shadow,
            elevation=3,
            shape=m_shape,
            menu_padding=m_pad,
        ),
        dropdown_theme=ft.DropdownTheme(
            menu_style=ft.MenuStyle(
                bgcolor=PINK_50,
                shadow_color=m_shadow,
                elevation=3,
                shape=m_shape,
                padding=m_pad,
            ),
        ),
        dialog_theme=ft.DialogTheme(
            bgcolor=WHITE,
            elevation=8,
            shadow_color=ft.Colors.with_opacity(0.15, PINK_600),
            shape=ft.RoundedRectangleBorder(
                radius=12,
                side=ft.BorderSide(1, PINK_200),
            ),
            title_text_style=ft.TextStyle(
                size=18,
                weight=ft.FontWeight.W_600,
                color=BLACK,
            ),
            content_text_style=ft.TextStyle(size=14, color=GREY_700),
        ),
        # Superficie propia: blanco + borde teal más marcado y más sombra que menús/dropdowns.
        snackbar_theme=ft.SnackBarTheme(
            bgcolor=PINK_50,
            elevation=SNACKBAR_ELEVATION,
            shape=_superficie_snackbar(),
            behavior=ft.SnackBarBehavior.FLOATING,
            content_text_style=ft.TextStyle(
                color=PINK_800,
                size=14,
                weight=ft.FontWeight.W_600,
            ),
            action_text_color=PINK_600,
        ),
    )
