"""Listado y subcuentas para el diálogo de selección de cuentas."""

from typing import Optional, Tuple

from application.ports.cuentas_movimientos_ports import (
    CuentasMovimientosPort,
    ListaCuentas,
)


class GestionCatalogoCuentasUseCase:
    """Expone consultas del catálogo sin acoplar la UI a Firebird."""

    def __init__(self, port: CuentasMovimientosPort) -> None:
        self._port = port

    def obtener_cuentas(
        self,
        tipo_cuentas: int,
        offset: int = 0,
        limit: int = 50,
        filtro: Optional[str] = None,
    ) -> Tuple[ListaCuentas, int]:
        return self._port.obtener_cuentas(
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
        return self._port.obtener_subcuentas(tipo_cuentas, prefijo)
