"""
Adaptador entre `GenerarXmlPage` y `TrabajoDialog`.

Por qué existe: `TrabajoDialog` espera un "parent" con una interfaz concreta
(`_app`, `_formatos_ui_uc`, `_mutar_hoja_uc`, `cargar_datos`). `GenerarXmlPage`
no expone esos nombres directamente; este bridge evita acoplar el diálogo a una
vista específica y mantiene el contrato explícito.
"""

from __future__ import annotations

from typing import Any


class TrabajoDialogBridgeGenerarXml:
    """Expone el contrato mínimo requerido por `TrabajoDialog`."""

    def __init__(self, generar_xml_page: Any, app: Any):
        self._generar_xml_page = generar_xml_page
        self._app = app
        self._formatos_ui_uc = app.container.formatos_uc
        self._mutar_hoja_uc = app.container.mutar_hoja_uc

    def _forzar_revalidacion_post_correccion(self) -> None:
        """Dispara la revalidación de Generar XML cuando el parent lo soporta."""
        callback = getattr(self._generar_xml_page, "_forzar_revalidacion_post_correccion", None)
        if callable(callback):
            callback()

    def cargar_datos(self) -> None:
        """
        Sincroniza la vista de validación después de guardar desde `TrabajoDialog`.

        En este flujo no hay grilla de hoja de trabajo para recargar; lo correcto es
        forzar una nueva validación en la pantalla actual de Generar XML.
        """
        self._forzar_revalidacion_post_correccion()
