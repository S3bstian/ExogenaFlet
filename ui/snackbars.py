"""
Snackbars centralizados: un solo lugar para estilo (tema `snackbar_theme`), diálogo u overlay.

Los SnackBar sin `bgcolor` heredan blanco, borde y elevación del tema (ver `ui/theme.py`).
"""
import flet as ft
from ui.colors import PINK_600, PINK_800, WHITE
from ui.theme import SNACKBAR_ELEVATION


def construir_snackbar_texto(
    texto: str,
    duration: int,
    *,
    size: int = 17,
    bgcolor=None,
    mensaje_peligro: bool = False,
) -> ft.SnackBar:
    """
    SnackBar de una sola línea de texto: elevación y comportamiento unificados.
    - Por defecto: texto oscuro, sin bgcolor (aplica el tema).
    - `mensaje_peligro`: fondo rojo de confirmación (texto blanco).
    - `bgcolor`: fondo sólido (texto blanco), p. ej. avisos con marca de color.
    """
    if mensaje_peligro:
        txt, bg = WHITE, ft.Colors.RED_300
    elif bgcolor is not None:
        txt, bg = WHITE, bgcolor
    else:
        txt, bg = PINK_800, None  # Alineado con `snackbar_theme.content_text_style`
    return ft.SnackBar(
        content=ft.Text(texto, color=txt, size=size),
        bgcolor=bg,
        duration=duration,
        behavior=ft.SnackBarBehavior.FLOATING,
        elevation=SNACKBAR_ELEVATION,
    )


def snackbar_invisible_para_cerrar(page: ft.Page) -> None:
    """Abre snackbar invisible vía show_dialog para que la UI procese el cierre del overlay."""
    cerrar = ft.SnackBar(content=ft.Text(""), bgcolor=ft.Colors.TRANSPARENT, duration=1, elevation=0)
    page.show_dialog(cerrar)
    page.update()


def crear_snackbar(
    contenido,
    duration: int = 999999999,
    action_text: str = None,
    on_action=None,
    show_close: bool = False,
) -> ft.SnackBar:
    """SnackBar con contenido custom (herramientas, columnas); hereda tema salvo elevación/márgenes."""
    snackbar = ft.SnackBar(
        content=contenido,
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=duration,
        margin=ft.margin.only(bottom=45, left=88, right=88),
        elevation=SNACKBAR_ELEVATION,
    )
    if show_close:
        snackbar.show_close_icon = True
    if action_text and on_action:
        snackbar.action = action_text
        snackbar.action_color = PINK_600
        snackbar.on_action = on_action
    return snackbar


def mostrar_mensaje(
    page: ft.Page,
    texto: str,
    duration: int = 5555,
    color=None,
    on_dismiss=None,
    action_text: str = None,
    on_action=None,
) -> None:
    """
    Mensaje vía `show_dialog` (flujo principal de la app).
    - `color`: fondo sólido (texto blanco), p. ej. alertas con color corporativo.
    - `action_text` + `on_action`: confirmación en rojo; `on_action` tras cerrar el diálogo del snack.
    """
    tiene_accion = bool(action_text and on_action)
    if tiene_accion:
        snackbar = construir_snackbar_texto(texto, duration, mensaje_peligro=True)
    elif color:
        snackbar = construir_snackbar_texto(texto, duration, bgcolor=color)
    else:
        snackbar = construir_snackbar_texto(texto, duration)

    def _al_cerrar(e=None):
        page.pop_dialog()
        page.update()
        if on_dismiss:
            on_dismiss(e)

    snackbar.on_dismiss = _al_cerrar
    if tiene_accion:

        def _on_action(e):
            _al_cerrar()
            on_action(e)

        snackbar.action = action_text
        snackbar.action_color = WHITE
        snackbar.on_action = _on_action

    page.show_dialog(snackbar)
    page.update()


def mostrar_mensaje_overlay(
    page: ft.Page,
    texto: str,
    duration: int = 5555,
    *,
    size: int = 17,
    color=None,
    mensaje_peligro: bool = False,
) -> None:
    """
    Mensaje en `page.overlay` (sin `show_dialog`). Útil con otros diálogos abiertos o hilos.
    """
    snackbar = construir_snackbar_texto(
        texto,
        duration,
        size=size,
        bgcolor=color,
        mensaje_peligro=mensaje_peligro,
    )

    def _al_cerrar(e=None):
        if snackbar in page.overlay:
            page.overlay.remove(snackbar)
        page.update()

    snackbar.on_dismiss = _al_cerrar
    page.overlay.append(snackbar)
    snackbar.open = True
    page.update()


def actualizar_mensaje_en_control(texto: str, mensaje_control, color=None) -> None:
    """Actualiza un control de texto (mensaje en diálogo) con texto y color."""
    if color is None:
        color = ft.Colors.RED
    mensaje_control.value = texto
    if hasattr(mensaje_control, "color"):
        mensaje_control.color = color
    if hasattr(mensaje_control, "visible"):
        mensaje_control.visible = True
    mensaje_control.update()
