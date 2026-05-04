"""Puerto para RW Helisa, creación de BD particular y rutas."""

from typing import Any, Protocol, TypeAlias

UiLoader: TypeAlias = Any
UiPage: TypeAlias = Any


class HelisaSesionPort(Protocol):
    """Comprueba productos, crea BD empresa y expone rutas de almacenamiento."""

    def producto_tiene_rw(self, producto: str) -> bool:
        """True si existe configuración RW para el código de producto."""

    def crear_bd_particular(
        self,
        codigo: int,
        producto: str,
        loader: UiLoader,
        page: UiPage,
    ) -> None:
        """Materializa la base EXOGENA de la empresa (puede lanzar)."""

    def ruta_directorio_exogena(self) -> str:
        """Directorio base donde viven las BD .EXG (producto EX)."""
