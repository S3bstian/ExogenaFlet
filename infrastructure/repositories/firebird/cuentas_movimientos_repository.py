"""Adaptador: cuentas locales vía persistencia Firebird."""

from typing import Optional, Tuple
from application.ports.cuentas_movimientos_ports import ListaCuentas

from infrastructure.persistence.firebird.cuentas_movimientos_persistencia import (
    obtener_cuentas,
    obtener_subcuentas,
)


class FirebirdCuentasMovimientosRepository:
    """Delega en `infrastructure.persistence.firebird.cuentas_movimientos_persistencia`."""

    def obtener_cuentas(
        self,
        tipo_cuentas: int,
        offset: int = 0,
        limit: int = 50,
        filtro: Optional[str] = None,
    ) -> Tuple[ListaCuentas, int]:
        return obtener_cuentas(
            tipo_cuentas,
            offset=offset,
            limit=limit,
            filtro=filtro,
        )

    def obtener_subcuentas(
        self,
        tipo_cuentas: int,
        prefijo: str,
    ) -> ListaCuentas:
        return obtener_subcuentas(tipo_cuentas, prefijo)
