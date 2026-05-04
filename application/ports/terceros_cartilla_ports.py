"""Puertos para listado y CRUD de terceros (cartilla)."""

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypeAlias, Union

TerceroRegistro: TypeAlias = Dict[str, Any]
ListaTerceros: TypeAlias = List[TerceroRegistro]
FiltroTerceros: TypeAlias = Optional[Union[str, List[str]]]


class TercerosCartillaPort(Protocol):
    """Contrato de acceso a datos de terceros usado por cartilla y diálogos."""

    def obtener_terceros(
        self,
        offset: int = 0,
        limit: int = 10,
        filtro: FiltroTerceros = None,
    ) -> Tuple[ListaTerceros, int]:
        """Lista paginada de terceros con filtro opcional."""

    def eliminar_tercero(self, identidad: str) -> Union[bool, Exception]:
        """Elimina un tercero por identidad."""

    def crear_tercero(self, tercero: TerceroRegistro) -> Union[str, bool, int]:
        """Alta desde UI (usa empresa de sesión)."""

    def actualizar_tercero(self, tercero: TerceroRegistro) -> Union[str, bool]:
        """Actualiza tercero y reflejos en hoja si aplica."""
