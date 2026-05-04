"""
Estilos de botón.
"""
import flet as ft
from ui.colors import PINK_50, PINK_200, PINK_400, PINK_600, WHITE, BLACK, GREY_700


BOTON_PRINCIPAL = ft.ButtonStyle(
    bgcolor=PINK_600,
    color=PINK_50,
    mouse_cursor=ft.MouseCursor.CLICK,
)

# Hover/foco mucho más marcados para botones secundarios “contenidos”
BOTON_SECUNDARIO = ft.ButtonStyle(
    overlay_color={
        ft.ControlState.HOVERED: ft.Colors.with_opacity(0.18, PINK_200),
        ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.28, PINK_200),
        ft.ControlState.PRESSED: ft.Colors.with_opacity(0.32, PINK_400),
    },
    side=ft.BorderSide(color=PINK_200, width=1),
    color={"default": BLACK, "selected": WHITE},
    bgcolor={"default": ft.Colors.WHITE, "selected": PINK_400},
    icon_color={"default": PINK_400, "selected": WHITE},
    mouse_cursor=ft.MouseCursor.CLICK,
)

BOTON_SECUNDARIO_SIN = ft.ButtonStyle(
    color=PINK_400,
    bgcolor=ft.Colors.TRANSPARENT,
    visual_density=ft.VisualDensity.COMPACT,
    shape=ft.RoundedRectangleBorder(radius=8),
    overlay_color={
        ft.ControlState.HOVERED: ft.Colors.with_opacity(0.20, PINK_200),
        ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.30, PINK_200),
        ft.ControlState.PRESSED: ft.Colors.with_opacity(0.35, PINK_400),
    },
    mouse_cursor=ft.MouseCursor.CLICK,
)

BOTON_LISTA = ft.ButtonStyle(
    alignment=ft.Alignment(0, 0),
    color=BLACK,
    shape=ft.RoundedRectangleBorder(radius=8),
    overlay_color={
        ft.ControlState.HOVERED: ft.Colors.with_opacity(0.22, PINK_200),
        ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.30, PINK_200),
        ft.ControlState.PRESSED: ft.Colors.with_opacity(0.34, PINK_400),
    },
    mouse_cursor=ft.MouseCursor.CLICK,
)

BOTON_SUBLISTA = ft.ButtonStyle(
    icon_color=PINK_200,
    alignment=ft.Alignment(0, 0),
    color=GREY_700,
    shape=ft.RoundedRectangleBorder(radius=8),
    overlay_color={
        ft.ControlState.HOVERED: ft.Colors.with_opacity(0.22, PINK_200),
        ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.30, PINK_200),
        ft.ControlState.PRESSED: ft.Colors.with_opacity(0.34, PINK_400),
    },
    mouse_cursor=ft.MouseCursor.CLICK,
)
