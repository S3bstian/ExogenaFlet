"""Orquestación de consultas y mutaciones de terceros en cartilla."""

from typing import Tuple, Union

from application.ports.terceros_cartilla_ports import (
    FiltroTerceros,
    ListaTerceros,
    TerceroRegistro,
    TercerosCartillaPort,
)


class GestionTercerosCartillaUseCase:
    """Expone operaciones de cartilla sin acoplar la UI a Firebird."""

    def __init__(self, port: TercerosCartillaPort) -> None:
        self._port = port

    def obtener_terceros(
        self,
        offset: int = 0,
        limit: int = 10,
        filtro: FiltroTerceros = None,
    ) -> Tuple[ListaTerceros, int]:
        return self._port.obtener_terceros(
            offset=offset, limit=limit, filtro=filtro
        )

    def eliminar_tercero(self, identidad: str) -> Union[bool, Exception]:
        return self._port.eliminar_tercero(identidad)

    def crear_tercero(self, tercero: TerceroRegistro) -> Union[str, bool, int]:
        return self._port.crear_tercero(tercero)

    def actualizar_tercero(self, tercero: TerceroRegistro) -> Union[str, bool]:
        return self._port.actualizar_tercero(tercero)
