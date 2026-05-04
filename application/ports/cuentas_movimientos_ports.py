"""Puerto para listado paginado de cuentas y subcuentas (catálogo en diálogos)."""

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypeAlias

CuentaCatalogo: TypeAlias = Dict[str, Any]
ListaCuentas: TypeAlias = List[CuentaCatalogo]


class CuentasMovimientosPort(Protocol):
    """Consultas sobre tablas locales de cuentas tributarias/contables."""

    def obtener_cuentas(
        self,
        tipo_cuentas: int,
        offset: int = 0,
        limit: int = 50,
        filtro: Optional[str] = None,
    ) -> Tuple[ListaCuentas, int]:
        """Página de cuentas y total bajo el mismo criterio de filtro."""

    def obtener_subcuentas(
        self,
        tipo_cuentas: int,
        prefijo: str,
    ) -> ListaCuentas:
        """Subcuentas bajo un prefijo (excluye la cuenta exacta del prefijo)."""
