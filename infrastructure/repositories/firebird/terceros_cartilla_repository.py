"""Adaptador Firebird para terceros en el flujo de cartilla."""

from typing import Tuple, Union
from application.ports.terceros_cartilla_ports import (
    FiltroTerceros,
    ListaTerceros,
    TerceroRegistro,
)

from infrastructure.persistence.firebird.terceros_persistencia import (
    actualizar_tercero as actualizar_tercero_bd,
    crear_tercero as crear_tercero_bd,
    eliminar_tercero as eliminar_tercero_bd,
    obtener_terceros as obtener_terceros_bd,
)
from core import session


class FirebirdTercerosCartillaRepository:
    """Adaptador Firebird: delega en `infrastructure.persistence.firebird.terceros_persistencia`."""

    def obtener_terceros(
        self,
        offset: int = 0,
        limit: int = 10,
        filtro: FiltroTerceros = None,
    ) -> Tuple[ListaTerceros, int]:
        return obtener_terceros_bd(offset=offset, limit=limit, filtro=filtro)

    def eliminar_tercero(self, identidad: str) -> Union[bool, Exception]:
        return eliminar_tercero_bd(identidad)

    def crear_tercero(self, tercero: TerceroRegistro) -> Union[str, bool, int]:
        codigo = (session.EMPRESA_ACTUAL or {}).get("codigo")
        if codigo is None:
            raise ValueError("No hay empresa seleccionada en sesión.")
        return crear_tercero_bd(tercero, codigo)

    def actualizar_tercero(self, tercero: TerceroRegistro) -> Union[str, bool]:
        return actualizar_tercero_bd(tercero)
