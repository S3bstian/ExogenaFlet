"""Puerto para bootstrap de BD global EX y lectura de tablas de traducción (catálogos)."""

from typing import Any, List, Optional, Protocol, Tuple, TypeAlias

FilaTraduccionCruda: TypeAlias = Tuple[Any, ...]
FilasTraduccionCrudas: TypeAlias = List[FilaTraduccionCruda]
ResultadoFilasTraduccion: TypeAlias = Optional[FilasTraduccionCrudas]


class CatalogosMaestrosPort(Protocol):
    """Asegura llave/BD global y devuelve filas de tablas maestras (PAIS, etc.)."""

    def asegurar_bd_global(self) -> None:
        """Crea llave y materializa BD global si hace falta."""

    def obtener_filas_traduccion(
        self,
        tabla: str,
        producto: str = "EX",
        codigo_empresa: int = -2,
    ) -> ResultadoFilasTraduccion:
        """Filas crudas para armar PAISES, DEPARTAMENTOS, etc."""
