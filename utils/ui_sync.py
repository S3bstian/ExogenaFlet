"""
Sincronización UI desde threads.
Actualiza controles Flet (ProgressRing, Text) de forma segura desde hilos secundarios.
"""
from typing import Any, Optional


def loader_row_trabajo(
    page: Any,
    loader_row: Any,
    mensaje_estado: Optional[Any] = None,
    texto: str = "Cargando conceptos...",
) -> None:
    """
    Muestra el Row de `crear_loader_row` (índice 1 = texto).
    Si `mensaje_estado` se pasa, lo oculta (mensaje inline bajo la tabla, etc.).
    """
    loader_row.controls[1].value = texto
    loader_row.visible = True
    if mensaje_estado is not None:
        mensaje_estado.visible = False
    page.update()


def loader_row_fin(page: Any, loader_row: Any) -> None:
    """Oculta el loader inline y refresca la página."""
    loader_row.visible = False
    page.update()


def loader_row_fin_y_error(page: Any, loader_row: Any, mensaje_estado: Any, texto: str) -> None:
    """Cierra el loader y muestra el mensaje de error (p. ej. dentro de ejecutar_en_ui)."""
    loader_row.visible = False
    mensaje_estado.value = texto
    mensaje_estado.visible = True
    page.update()


def loader_row_visibilidad(
    page: Any,
    loader_row: Any,
    visible: bool,
    texto: Optional[str] = None,
) -> None:
    """
    Muestra u oculta el Row del loader; si `texto` no es None, actualiza `controls[1]` (Text).
    Útil cuando no hay mensaje de estado que ocultar o solo se alterna visible.
    """
    if texto is not None:
        loader_row.controls[1].value = texto
    loader_row.visible = visible
    page.update()


def actualizar_progreso_ui(
    loader: Any,
    valor: Optional[float] = None,
    page: Optional[Any] = None,
    texto_control: Optional[Any] = None,
    texto_valor: Optional[str] = None,
) -> None:
    """
    Actualiza loader.value y opcionalmente texto_control.value de forma thread-safe.
    valor: 0.0–1.0 (se clampa a 0.01–1.0 para ProgressRing determinate).
    """
    def _hacer():
        if valor is not None:
            loader.value = max(0.01, min(1.0, valor))
        if texto_control is not None and texto_valor is not None:
            texto_control.value = texto_valor
            texto_control.update()
        loader.update()
        if page:
            page.update()

    try:
        if page and getattr(page, "session", None) and getattr(page.session, "connection", None):
            page.session.connection.loop.call_soon_threadsafe(_hacer)
        else:
            _hacer()
    except Exception:
        _hacer()


def ejecutar_en_ui(page: Any, fn) -> None:
    """Ejecuta fn() en el hilo de la UI (para actualizaciones desde workers)."""
    def _hacer():
        fn()
        if page:
            page.update()
    try:
        if page and getattr(page, "session", None) and getattr(page.session, "connection", None):
            page.session.connection.loop.call_soon_threadsafe(_hacer)
        else:
            _hacer()
    except Exception:
        _hacer()
